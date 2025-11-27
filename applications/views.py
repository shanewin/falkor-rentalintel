from users.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .forms import ApplicationForm, ApplicantCompletionForm, PersonalInfoForm, PreviousAddressForm, IncomeForm
from .models import (
    UploadedFile, Application, ApplicationActivity, ApplicationSection, 
    PersonalInfoData, PreviousAddress, SectionStatus, IncomeData
)
from applicants.models import Applicant
from apartments.models import Apartment
import cloudinary.uploader
# Import activity tracking
from applicants.signals import trigger_document_uploaded
from django.contrib import messages 
from django.contrib.auth.models import AnonymousUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.db import transaction
from functools import wraps

def hybrid_csrf_protect(view_func):
    """
    Apply CSRF protection for authenticated users,
    skip for valid token-based access
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        # Check for token-based access
        token = request.GET.get('token')
        if token:
            # For token access, bypass CSRF
            return csrf_exempt(view_func)(request, *args, **kwargs)
        else:
            # For authenticated access, enforce CSRF
            return csrf_protect(view_func)(request, *args, **kwargs)
    
    wrapped_view.csrf_exempt = False
    return wrapped_view
from django.db.models import Max
import os
import requests
import tempfile
import json
from django.utils import timezone
from doc_analysis.utils import extract_text_and_metadata, analyze_bank_statement, analyze_pay_stub, detect_pdf_modifications, analyze_tax_return


import logging
logging.basicConfig(level=logging.DEBUG)


@login_required
def application(request):
    if not request.user.is_broker and not request.user.is_superuser:
        messages.error(request, "You are not authorized to create applications.")
        return redirect("applications_list")  # Redirect non-brokers

    # ✅ Get applicant if broker pre-selects one
    applicant_id = request.GET.get("applicant_id")  
    apartment_id = request.GET.get("apartment_id")  # Optional apartment pre-selection
    
    applicant = None
    apartment = None
    
    if applicant_id:
        try:
            applicant = Applicant.objects.get(id=applicant_id)
        except Applicant.DoesNotExist:
            messages.error(request, "The selected applicant does not exist.")
            return redirect("applications_list")  # Redirect if invalid applicant

    if apartment_id:
        try:
            apartment = Apartment.objects.get(id=apartment_id)
        except Apartment.DoesNotExist:
            messages.error(request, "The selected apartment does not exist.")
            return redirect("applications_list")

    if request.method == "POST":
        application_form = ApplicationForm(request.POST, applicant=applicant, apartment=apartment, user=request.user)  # ✅ Pass user for context

        if application_form.is_valid():
            application = application_form.save(commit=False)
            
            # ✅ Get applicant if selected (now optional)
            applicant = application_form.cleaned_data.get("applicant") or applicant
            if applicant:
                application.applicant = applicant
                
                # Update applicant profile with any new data from form
                from .services import ApplicationDataService
                ApplicationDataService.update_applicant_from_application(
                    applicant, application_form.cleaned_data
                )
            
            application.broker = request.user
            application.required_documents = application_form.cleaned_data.get("required_documents", [])
            application.save()  # ✅ Save once instead of twice

            # Log appropriate activity based on what information is available
            if application.apartment:
                location = f"{application.apartment.building.name} Unit {application.apartment.unit_number}"
            elif application.manual_building_address:
                location = f"{application.manual_building_address} Unit {application.manual_unit_number}"
            else:
                location = "property (details to be added)"
                
            if application.applicant:
                log_activity(application, f"Broker {request.user.email} created an application for {application.applicant.first_name} {application.applicant.last_name} at {location}.")
            else:
                log_activity(application, f"Broker {request.user.email} created an application for {location} (applicant to be added).")

            messages.success(request, "Application created successfully!")
            return redirect("application_detail", uuid=application.unique_link)

    else:
        application_form = ApplicationForm(applicant=applicant, apartment=apartment, user=request.user)  # ✅ Pre-fill form with data if provided

    return render(
        request,
        "applications/application_form.html",
        {"application_form": application_form, "applicant": applicant, "apartment": apartment},
    )



# ✅ DISPLAY APPLICATION DETAILS FOR BROKER/APPLICANT
import json

def application_detail(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    uploaded_files = application.uploaded_files.all()

    # ✅ Convert JSON string to dictionary
    for file in uploaded_files:
        if file.analysis_results:
            try:
                file.analysis_results = json.loads(file.analysis_results)
            except json.JSONDecodeError:
                file.analysis_results = None  # Handle invalid JSON gracefully

    return render(request, "applications/application_detail.html", {
        "application": application,
        "uploaded_files": uploaded_files,
    })



def applicant_complete(request, uuid):
    """
    Applicant completes application via unique link.
    Redirects to the full 5-section application (same as broker preview).
    """
    application = get_object_or_404(Application, unique_link=uuid)

    # ✅ Allow access via unique link instead of requiring login
    if not isinstance(request.user, AnonymousUser):
        # Check if the logged-in user is the applicant for this application
        if hasattr(request.user, 'applicant_profile'):
            if request.user.applicant_profile != application.applicant:
                messages.error(request, "You are not authorized to complete this application.")
                return redirect("application_detail", application_id=application.id)
        else:
            # User is logged in but doesn't have an applicant profile
            messages.error(request, "You are not authorized to complete this application.")
            return redirect("application_detail", application_id=application.id)
    else:
        token = request.GET.get("token")
        if token != str(application.unique_link):
            messages.error(request, "Invalid or missing access token.")
            return redirect("application_detail", application_id=application.id)

    # Log that applicant accessed the application
    log_activity(application, f"Applicant accessed the application via unique link.")
    
    # Redirect applicants to the full 5-section application overview with token
    # This ensures applicants get the complete application experience that brokers see in preview
    return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={uuid}")



# ✅ BROKER LISTS ALL APPLICATIONS
@login_required
def application_list(request):
    if request.user.is_superuser:
        applications = Application.objects.all().select_related('applicant', 'apartment__building', 'broker').order_by('-created_at')  # ✅ Superuser sees ALL applications
    elif request.user.is_broker:
        # Import necessary models
        from django.db import models
        from buildings.models import Building
        from apartments.models import Apartment
        
        # Get all buildings assigned to this broker
        broker_buildings = Building.objects.filter(brokers=request.user)
        
        # Get all apartments in those buildings
        broker_apartments = Apartment.objects.filter(building__in=broker_buildings)
        
        # Show applications for broker's apartments OR applications created by the broker
        applications = Application.objects.filter(
            models.Q(apartment__in=broker_apartments) | models.Q(broker=request.user)
        ).select_related('applicant', 'apartment__building', 'broker').order_by('-created_at')
    elif request.user.is_applicant:
        # Get the applicant profile for the current user
        if hasattr(request.user, 'applicant_profile'):
            # Show all applications for this applicant (including NEW applications created by brokers)
            applications = Application.objects.filter(
                applicant=request.user.applicant_profile
            ).select_related('applicant', 'apartment__building', 'broker').order_by('-created_at')
        else:
            applications = Application.objects.none()  # No applicant profile, no applications
    else:
        messages.error(request, "You are not authorized to view applications.")
        return redirect("home")

    # Calculate dashboard statistics
    total_applications = applications.count()
    new_applications = applications.filter(status='new').count()
    pending_applications = applications.filter(status='pending').count()
    approved_applications = applications.filter(status='approved').count()
    unique_properties = len(set(
        f"{app.apartment.building.name} - {app.apartment.unit_number}" if app.apartment 
        else f"{app.get_building_display()} - {app.get_unit_display()}"
        for app in applications
    ))

    context = {
        'applications': applications,
        'total_applications': total_applications,
        'new_applications': new_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'unique_properties': unique_properties,
    }

    return render(request, "applications/application_list.html", context)




def delete_uploaded_file(request, file_id):
    uploaded_file = get_object_or_404(UploadedFile, id=file_id)

    # ✅ Superusers, Brokers, and Applicants can delete files
    if not (request.user.is_superuser or 
            request.user == uploaded_file.application.broker or 
            request.user == uploaded_file.application.applicant):
        messages.error(request, "You are not authorized to delete this file.")
        return redirect("application_detail", application_id=uploaded_file.application.id)

    try:
        # ✅ Delete from Cloudinary first
        if uploaded_file.file:
            # Extract the public_id from the Cloudinary URL
            cloudinary_url = uploaded_file.file.url
            # For raw files, the public_id includes the file extension
            public_id = cloudinary_url.split("/")[-1]  # Keep the full filename with extension
            
            # Delete from Cloudinary
            response = cloudinary.uploader.destroy(public_id, resource_type="raw")
            
            if response.get("result") not in ["ok", "not found"]:
                messages.warning(request, f"Warning: Cloudinary deletion returned: {response.get('result')}")
        
        # Track document deletion for audit trail
        if uploaded_file.application.applicant:
            from applicants.activity_tracker import ActivityTracker
            ActivityTracker.track_activity(
                applicant=uploaded_file.application.applicant,
                activity_type='document_deleted',
                description=f"Deleted {uploaded_file.document_type or 'document'}",
                triggered_by=request.user,
                metadata={
                    'document_type': uploaded_file.document_type,
                    'deleted_by': request.user.email if hasattr(request.user, 'email') else str(request.user)
                },
                request=request
            )
        
        # ✅ Delete from database regardless of Cloudinary result
        # (file might not exist in Cloudinary anymore, but we should clean up DB)
        uploaded_file.delete()
        messages.success(request, "File deleted successfully.")
        
    except Exception as e:
        messages.error(request, f"Error deleting file: {str(e)}")

    return redirect("application_detail", application_id=uploaded_file.application.id)





def application_edit(request, application_id):
    application = get_object_or_404(Application, id=application_id)

    # Check if user has access to edit this application
    can_edit = False
    if request.user.is_superuser:
        can_edit = True
    elif request.user.is_broker:
        # Broker can edit if they created it OR if it's for their assigned apartment
        from buildings.models import Building
        broker_buildings = Building.objects.filter(brokers=request.user)
        if application.broker == request.user or (application.apartment and application.apartment.building in broker_buildings):
            can_edit = True
    elif hasattr(request.user, 'applicant_profile') and application.applicant == request.user.applicant_profile:
        can_edit = True
    
    if not can_edit:
        messages.error(request, "You are not authorized to edit this application.")
        return redirect("application_detail", application_id=application.id)

    if request.method == 'POST':
        form = ApplicationForm(request.POST, instance=application)

        if form.is_valid():
            form.save()
            messages.success(request, "Application updated successfully!")
            return redirect("application_detail", application_id=application.id)

    else:
        form = ApplicationForm(instance=application)

    return render(
        request,
        "applications/application_edit.html",
        {"form": form, "application": application}
    )




def log_activity(application, description):
    ApplicationActivity.objects.create(application=application, description=description)




@login_required
def send_application_link(request, application_id):
    """Send application link to applicant"""
    application = get_object_or_404(Application, id=application_id)
    
    # FIX: Check permissions - broker must own the application or be superuser
    if not request.user.is_superuser:
        # Check if user is the broker who created this application
        if application.broker != request.user:
            messages.error(request, "You are not authorized to send this application. Only the creating broker can send links.")
            return redirect('application_detail', application_id=application.id)
    
    # Check if applicant exists and has email
    if not application.applicant or not application.applicant.email:
        messages.error(request, "Cannot send application - no applicant email found.")
        return redirect('application_detail', application_id=application.id)
    
    # Send email
    from .email_utils import send_application_link_email
    
    email_sent = send_application_link_email(application, request)
    if email_sent:
        messages.success(request, f"Application link sent to {application.applicant.email}")
        log_activity(application, f"Application link re-sent to {application.applicant.email} by {request.user.email}")
    else:
        messages.error(request, "Failed to send email. Please try again later.")
    
    return redirect('application_detail', application_id=application.id)


@login_required
def revoke_application(request, application_id):
    """Revoke application access by replacing UUID with a revoked token"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check permissions
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to revoke this application.")
        return redirect('broker_application_management', application_id=application.id)
    
    # Check if already revoked
    if application.is_revoked:
        messages.warning(request, "This application has already been revoked.")
        return redirect('broker_application_management', application_id=application.id)
    
    if request.method == 'POST':
        revoke_reason = request.POST.get('revoke_reason')
        other_reason_text = request.POST.get('other_reason_text')
        
        if not revoke_reason:
            messages.error(request, "Please select a reason for revoking the application.")
            return redirect('broker_application_management', application_id=application.id)
        
        # If "Other" is selected, use the custom text
        if revoke_reason == 'Other':
            if not other_reason_text:
                messages.error(request, "Please provide a reason when selecting 'Other'.")
                return redirect('broker_application_management', application_id=application.id)
            final_reason = other_reason_text
        else:
            final_reason = revoke_reason
        
        # Store original UUID for logging
        original_uuid = str(application.unique_link)
        
        # Revoke the application
        application.is_revoked = True
        application.revoked_at = timezone.now()
        application.revoked_by = request.user
        application.revocation_reason = revoke_reason
        application.revocation_notes = other_reason_text if revoke_reason == 'Other' else None
        
        # Generate new "revoked" UUID to maintain unique constraint
        import uuid
        application.unique_link = uuid.uuid4()  # New UUID that won't match any tokens
        application.save()
        
        # Log the activity with original UUID for audit trail
        log_activity(application, f"Application access revoked by {request.user.email}. Reason: {final_reason}. Original UUID: {original_uuid}")
        
        messages.success(request, f"Application access has been revoked. Reason: {final_reason}")
        
    return redirect('broker_application_management', application_id=application.id)


@login_required
def test_email_send(request):
    """Admin test email functionality"""
    if not request.user.is_superuser:
        messages.error(request, "Only administrators can test email functionality.")
        return redirect('applications_list')
    
    if request.method == 'POST':
        test_email = request.POST.get('test_email')
        if test_email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                
                # Send test email
                send_mail(
                    subject='DoorWay Email Test',
                    message='This is a test email from DoorWay. If you received this, email is working!',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[test_email],
                    fail_silently=False,
                )
                messages.success(request, f"Test email sent successfully to {test_email}")
            except Exception as e:
                messages.error(request, f"Email sending failed: {str(e)}")
        else:
            messages.error(request, "Please provide a test email address.")
    
    return redirect('applications_list')


@login_required
def test_sms_send(request):
    """Admin test SMS functionality"""
    if not request.user.is_superuser:
        messages.error(request, "Only administrators can test SMS functionality.")
        return redirect('applications_list')
    
    if request.method == 'POST':
        test_phone = request.POST.get('test_phone')
        if test_phone:
            try:
                from .sms_utils import send_test_sms, validate_phone_number
                
                # Validate phone number
                is_valid, formatted_phone = validate_phone_number(test_phone)
                if not is_valid:
                    messages.error(request, f"Invalid phone number format: {formatted_phone}")
                    return redirect('applications_list')
                
                # Send test SMS
                success, result = send_test_sms(formatted_phone)
                if success:
                    messages.success(request, f"Test SMS sent successfully to {formatted_phone}! Message ID: {result}")
                else:
                    messages.error(request, f"SMS sending failed: {result}")
                    
            except Exception as e:
                messages.error(request, f"SMS testing failed: {str(e)}")
        else:
            messages.error(request, "Please provide a test phone number.")
    
    return redirect('applications_list')


def analyze_uploaded_file(request, file_id):
    uploaded_file = get_object_or_404(UploadedFile, id=file_id)
    application = uploaded_file.application

    # ✅ Ensure only brokers or superusers can analyze files
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to analyze this file.")
        return redirect("application_detail", application_id=application.id)

    try:
        # Import the Celery task
        from .tasks import analyze_document_async
        
        # Clear any previous analysis results to allow re-analysis
        uploaded_file.analysis_results = None
        uploaded_file.celery_task_id = None
        uploaded_file.save()
        
        # Start the asynchronous analysis task
        task = analyze_document_async.delay(file_id)
        
        # Store the new task ID
        uploaded_file.celery_task_id = task.id
        uploaded_file.save()
        
        messages.success(request, f"🔄 Document analysis started! The AI is processing '{uploaded_file.document_type}' in the background. Results will appear automatically when complete.")
        messages.info(request, "⏱️ This process may take several minutes. You can refresh the page to check for updates.")
        
    except Exception as e:
        messages.error(request, f"❌ Error starting document analysis: {str(e)}")

    return redirect("application_detail", application_id=application.id)


# AJAX: Check document analysis status
@login_required
def check_analysis_status(request, file_id):
    """Check Celery task status for document analysis"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests allowed'}, status=405)
    
    try:
        uploaded_file = get_object_or_404(UploadedFile, id=file_id)
        
        # Check if user has permission to view this file
        if not (request.user.is_superuser or request.user == uploaded_file.application.broker):
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        if not uploaded_file.celery_task_id:
            return JsonResponse({
                'status': 'no_task',
                'message': 'No analysis task found'
            })
        
        # Import Celery app to check task status
        from celery.result import AsyncResult
        from realestate.celery import app as celery_app
        
        task_result = AsyncResult(uploaded_file.celery_task_id, app=celery_app)
        
        if task_result.state == 'PENDING':
            return JsonResponse({
                'status': 'pending',
                'message': 'Analysis task is queued...'
            })
        elif task_result.state == 'PROGRESS':
            return JsonResponse({
                'status': 'progress',
                'message': task_result.info.get('status', 'Processing...'),
                'progress': task_result.info.get('progress', 0)
            })
        elif task_result.state == 'SUCCESS':
            # Task completed, check if results are saved
            uploaded_file.refresh_from_db()
            if uploaded_file.analysis_results:
                return JsonResponse({
                    'status': 'completed',
                    'message': 'Analysis completed!',
                    'should_reload': True
                })
            else:
                return JsonResponse({
                    'status': 'completed',
                    'message': 'Analysis completed but no results found'
                })
        elif task_result.state == 'FAILURE':
            return JsonResponse({
                'status': 'failed',
                'message': f'Analysis failed: {str(task_result.info)}'
            })
        else:
            return JsonResponse({
                'status': 'unknown',
                'message': f'Unknown task state: {task_result.state}'
            })
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error checking status: {str(e)}'
        })


# ... existing imports ...
from .nudge_service import NudgeService
from .models import ApplicationStatus

# ... existing code ...

@login_required
@require_http_methods(["POST"])
def nudge_applicant(request, application_id):
    """
    Send a nudge (reminder) to the applicant.
    """
    application = get_object_or_404(Application, id=application_id)
    
    # Permission check
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to nudge this applicant.")
        return redirect('application_detail', application_id=application.id)
        
    custom_message = request.POST.get('custom_message')
    
    if NudgeService.send_nudge(application, request.user, custom_message=custom_message):
        messages.success(request, f"Nudge sent to {application.applicant.first_name}!")
    else:
        messages.error(request, "Failed to send nudge. Ensure applicant has an email address.")
        
    return redirect('application_detail', application_id=application.id)


@login_required
@require_http_methods(["POST"])
def approve_application(request, application_id):
    """
    Approve the application and lock it.
    """
    application = get_object_or_404(Application, id=application_id)
    
    # Permission check
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to approve this application.")
        return redirect('application_detail', application_id=application.id)
    
    if application.status == ApplicationStatus.APPROVED:
        messages.warning(request, "Application is already approved.")
        return redirect('application_detail', application_id=application.id)
        
    # Check if satisfied (optional, but good practice)
    if not application.is_satisfied():
        messages.warning(request, "Warning: Application has missing documents. Approved anyway.")
    
    # Approve and Lock
    application.status = ApplicationStatus.APPROVED
    application.save()
    
    # Log activity
    log_activity(application, f"Application APPROVED by {request.user.email}")
    
    # Send approval email (placeholder for now)
    # send_approval_email(application) 
    
    messages.success(request, "Application approved successfully!")
    return redirect('application_detail', application_id=application.id)

# ===== V2 APPLICATION SYSTEM VIEWS =====

@login_required
def broker_create_application(request):
    """Enhanced broker application creation workflow"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            # Handle temporary application creation for preview
            if action == 'create_temp_preview':
                return handle_temp_application_creation(request)
            
            # Create new applicant if needed
            applicant = None
            applicant_type = request.POST.get('applicant_type')
            
            if applicant_type == 'existing':
                applicant_id = request.POST.get('applicant')
                if applicant_id:
                    try:
                        applicant = Applicant.objects.get(id=applicant_id)
                    except Applicant.DoesNotExist:
                        messages.error(request, "Selected applicant not found.")
                        return redirect('broker_create_application')
                        
            elif applicant_type == 'new':
                # Create new applicant with minimal info
                email = request.POST.get('new_applicant_email')
                phone = request.POST.get('new_applicant_phone')
                first_name = request.POST.get('new_applicant_first_name', '')
                last_name = request.POST.get('new_applicant_last_name', '')
                
                if email:
                    # Check if applicant already exists
                    existing_applicant = Applicant.objects.filter(email=email).first()
                    if existing_applicant:
                        applicant = existing_applicant
                        messages.info(request, f"Using existing applicant: {applicant.email}")
                    else:
                        from datetime import date
                        applicant = Applicant.objects.create(
                            email=email,
                            phone_number=phone or '',
                            first_name=first_name,
                            last_name=last_name,
                            date_of_birth=date(1990, 1, 1),  # Temporary date for broker creation
                            street_address_1='Temporary Address',  # Required field
                            city='New York',  # Required field
                            zip_code='10001'  # Required field
                        )
                        messages.success(request, f"Created new applicant: {applicant.email}")
            
            # Get property information
            apartment = None
            property_type = request.POST.get('property_type')
            
            if property_type == 'existing':
                apartment_id = request.POST.get('apartment')
                if apartment_id:
                    try:
                        apartment = Apartment.objects.get(id=apartment_id)
                    except Apartment.DoesNotExist:
                        messages.error(request, "Selected apartment not found.")
                        return redirect('broker_create_application')
            
            # Create application
            application = Application.objects.create(
                apartment=apartment,
                applicant=applicant,
                broker=request.user,
                application_version='v2',
                current_section=1
            )
            
            # Set manual property fields if needed
            if property_type == 'manual':
                # CRITICAL: Only superusers can create applications for manual properties
                if not request.user.is_superuser:
                    messages.error(request, "Access denied. Only administrators can create applications for properties not in the database.")
                    return redirect('broker_create_application')
                    
                application.manual_building_name = request.POST.get('manual_building_name', '')
                application.manual_building_address = request.POST.get('manual_building_address', '')
                application.manual_unit_number = request.POST.get('manual_unit_number', '')
            
            # Set customization options
            required_documents = request.POST.getlist('required_documents')
            application.required_documents = required_documents
            
            application_fee = request.POST.get('application_fee', '50.00')
            try:
                application.application_fee_amount = float(application_fee)
            except (ValueError, TypeError):
                application.application_fee_amount = 50.00
            
            application.save()
            
            # Initialize V2 section status
            section_statuses = {
                1: SectionStatus.NOT_STARTED,
                2: SectionStatus.NOT_STARTED,
                3: SectionStatus.NOT_STARTED,
                4: SectionStatus.NOT_STARTED,
                5: SectionStatus.NOT_STARTED,
            }
            application.section_statuses = section_statuses
            application.save()
            
            # Create ApplicationSection records
            section_names = {
                1: 'Personal Information',
                2: 'Income',
                3: 'Legal',
                4: 'Review',
                5: 'Payment'
            }
            
            for section_num, section_name in section_names.items():
                ApplicationSection.objects.create(
                    application=application,
                    section_number=section_num,
                    status=SectionStatus.NOT_STARTED
                )
            
            # Log activity
            property_desc = str(apartment) if apartment else f"{application.manual_building_name or 'Property'}"
            applicant_desc = str(applicant) if applicant else "TBD"
            log_activity(application, f"Broker {request.user.email} created application for {applicant_desc} at {property_desc}")
            
            # Handle send action
            if action == 'create_and_send' and applicant:
                from .email_utils import send_application_link_email
                from .sms_utils import send_application_link_sms, validate_phone_number
                
                send_email = request.POST.get('send_email') == 'on'
                send_sms = request.POST.get('send_sms') == 'on'
                
                email_sent = False
                sms_sent = False
                
                # Send email if requested and email available
                if send_email and applicant.email:
                    email_sent = send_application_link_email(application, request)
                    if email_sent:
                        log_activity(application, f"Application link emailed to {applicant.email}")
                    else:
                        messages.warning(request, f"Email sending failed to {applicant.email}")
                
                # Send SMS if requested and phone available
                if send_sms and applicant.phone_number:
                    # Validate phone number first
                    is_valid, formatted_phone = validate_phone_number(applicant.phone_number)
                    if is_valid:
                        sms_success, sms_result = send_application_link_sms(formatted_phone, application)
                        if sms_success:
                            sms_sent = True
                            log_activity(application, f"Application link sent via SMS to {formatted_phone}")
                        else:
                            messages.warning(request, f"SMS sending failed: {sms_result}")
                    else:
                        messages.warning(request, f"Invalid phone number format: {formatted_phone}")
                
                # Success message based on what was sent
                sent_methods = []
                if email_sent:
                    sent_methods.append("email")
                if sms_sent:
                    sent_methods.append("SMS")
                
                if sent_methods:
                    success_msg = f"Application created and sent via {' and '.join(sent_methods)} to {applicant.email or applicant.phone_number}"
                else:
                    success_msg = "Application created successfully"
                    if send_email or send_sms:
                        messages.info(request, "No contact methods were successful. Please send the link manually.")
                
                messages.success(request, success_msg)
            else:
                messages.success(request, "Application created successfully!")
            
            return redirect('broker_confirmation', application_id=application.id)
            
        except Exception as e:
            import traceback
            print(f"ERROR in broker_create_application: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            messages.error(request, f"An error occurred while creating the application: {str(e)}")
            # Don't redirect on error, show the form again
    
    # GET request - show the form
    form = ApplicationForm()
    return render(request, 'applications/broker_create_application.html', {'form': form})


# Progressive Broker Application Creation Utilities
def get_broker_session_data(request, key=None):
    """Get broker application creation data from session"""
    session_key = 'broker_application_creation'
    if session_key not in request.session:
        request.session[session_key] = {}
    
    if key:
        return request.session[session_key].get(key)
    return request.session[session_key]

def set_broker_session_data(request, key, value):
    """Set broker application creation data in session"""
    session_key = 'broker_application_creation'
    if session_key not in request.session:
        request.session[session_key] = {}
    
    request.session[session_key][key] = value
    request.session.modified = True

def clear_broker_session_data(request):
    """Clear broker application creation session data"""
    session_key = 'broker_application_creation'
    if session_key in request.session:
        del request.session[session_key]

# Progressive Broker Application Creation Views
@login_required
def broker_create_step1(request):
    """Step 1: Property Selection"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    if request.method == 'POST':
        # Store step 1 data in session
        property_type = request.POST.get('property_type')
        
        # Enforce restriction: only superusers can enter property manually
        if property_type == 'manual' and not request.user.is_superuser:
            messages.error(request, "You are not authorized to enter properties manually. Please select an existing property.")
            return redirect('broker_create_step1')
        
        set_broker_session_data(request, 'property_type', property_type)
        
        if property_type == 'existing':
            apartment_id = request.POST.get('apartment')
            set_broker_session_data(request, 'apartment_id', apartment_id)
        elif property_type == 'manual' and request.user.is_superuser:
            set_broker_session_data(request, 'manual_building_name', request.POST.get('manual_building_name', ''))
            set_broker_session_data(request, 'manual_building_address', request.POST.get('manual_building_address', ''))
            set_broker_session_data(request, 'manual_unit_number', request.POST.get('manual_unit_number', ''))
        
        return redirect('broker_create_step2')
    
    # Get available apartments for selection
    apartments = Apartment.objects.all().order_by('building__name', 'unit_number')
    
    context = {
        'apartments': apartments,
        'current_step': 1,
        'session_data': get_broker_session_data(request),
    }
    return render(request, 'applications/broker_create_step1.html', context)

@login_required
def broker_create_step2(request):
    """Step 2: Applicant Selection"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Check if step 1 was completed
    if not get_broker_session_data(request, 'property_type'):
        messages.warning(request, "Please complete step 1 first.")
        return redirect('broker_create_step1')
    
    if request.method == 'POST':
        # Store step 2 data in session
        applicant_type = request.POST.get('applicant_type')
        set_broker_session_data(request, 'applicant_type', applicant_type)
        
        if applicant_type == 'existing':
            applicant_id = request.POST.get('applicant')
            set_broker_session_data(request, 'applicant_id', applicant_id)
        elif applicant_type == 'new':
            set_broker_session_data(request, 'new_applicant_email', request.POST.get('new_applicant_email', ''))
            set_broker_session_data(request, 'new_applicant_phone', request.POST.get('new_applicant_phone', ''))
            set_broker_session_data(request, 'new_applicant_first_name', request.POST.get('new_applicant_first_name', ''))
            set_broker_session_data(request, 'new_applicant_last_name', request.POST.get('new_applicant_last_name', ''))
        
        return redirect('broker_create_step3')
    
    # Get available applicants for selection
    applicants = Applicant.objects.all().order_by('first_name', 'last_name')
    
    context = {
        'applicants': applicants,
        'current_step': 2,
        'session_data': get_broker_session_data(request),
    }
    return render(request, 'applications/broker_create_step2.html', context)

@login_required
def broker_create_step3(request):
    """Step 3: Application Settings"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Check if previous steps were completed
    if not get_broker_session_data(request, 'property_type') or not get_broker_session_data(request, 'applicant_type'):
        messages.warning(request, "Please complete previous steps first.")
        return redirect('broker_create_step1')
    
    if request.method == 'POST':
        # Store step 3 data in session
        application_fee = request.POST.get('application_fee', '50.00')
        set_broker_session_data(request, 'application_fee', application_fee)
        
        return redirect('broker_create_step4')
    
    context = {
        'current_step': 3,
        'session_data': get_broker_session_data(request),
    }
    return render(request, 'applications/broker_create_step3.html', context)

@login_required
def broker_create_step4(request):
    """Step 4: Review & Create Application"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Check if all previous steps were completed
    session_data = get_broker_session_data(request)
    required_keys = ['property_type', 'applicant_type']
    
    for key in required_keys:
        if not session_data.get(key):
            messages.warning(request, "Please complete all previous steps first.")
            return redirect('broker_create_step1')
    
    if request.method == 'POST':
        try:
            # Create the application using session data
            application = create_application_from_session(request, session_data)
            
            # Clear session data
            clear_broker_session_data(request)
            
            messages.success(request, "Application created successfully!")
            return redirect('broker_confirmation', application_id=application.id)
            
        except Exception as e:
            messages.error(request, f"Error creating application: {str(e)}")
            return redirect('broker_create_step4')
    
    # Prepare data for review
    context = prepare_review_context(session_data)
    context['current_step'] = 4
    context['session_data'] = session_data
    
    return render(request, 'applications/broker_create_step4.html', context)

def create_application_from_session(request, session_data):
    """Create application from session data"""
    # Get or create applicant
    applicant = None
    if session_data.get('applicant_type') == 'existing':
        applicant_id = session_data.get('applicant_id')
        if applicant_id:
            applicant = Applicant.objects.get(id=applicant_id)
    elif session_data.get('applicant_type') == 'new':
        email = session_data.get('new_applicant_email')
        if email:
            existing_applicant = Applicant.objects.filter(email=email).first()
            if existing_applicant:
                applicant = existing_applicant
            else:
                from datetime import date
                # FIX: Create applicant with proper placeholder data and validation
                first_name = session_data.get('new_applicant_first_name', '').strip()
                last_name = session_data.get('new_applicant_last_name', '').strip()
                phone = session_data.get('new_applicant_phone', '').strip()
                
                # Validate required fields
                if not first_name or not last_name:
                    raise ValueError("Applicant first and last name are required")
                
                applicant = Applicant.objects.create(
                    email=email,
                    phone_number=phone,
                    first_name=first_name,
                    last_name=last_name,
                    # FIX: Use NULL instead of fake data for unknown fields
                    date_of_birth=None,  # Will be collected during application
                    street_address_1='',  # Will be collected during application
                    city='',  # Will be collected during application
                    state='',  # Will be collected during application
                    zip_code='',  # Will be collected during application
                    # Mark profile as incomplete
                    profile_incomplete=True,
                    profile_completion_percentage=0
                )
    
    # Get apartment
    apartment = None
    if session_data.get('property_type') == 'existing':
        apartment_id = session_data.get('apartment_id')
        if apartment_id:
            apartment = Apartment.objects.get(id=apartment_id)
    
    # Create application
    application = Application.objects.create(
        apartment=apartment,
        applicant=applicant,
        broker=request.user,
        application_version='v2',
        current_section=1
    )
    
    # Set manual property fields if needed
    if session_data.get('property_type') == 'manual':
        application.manual_building_name = session_data.get('manual_building_name', '')
        application.manual_building_address = session_data.get('manual_building_address', '')
        application.manual_unit_number = session_data.get('manual_unit_number', '')
    
    # Set application settings
    try:
        application.application_fee_amount = float(session_data.get('application_fee', '50.00'))
    except (ValueError, TypeError):
        application.application_fee_amount = 50.00
    
    application.save()
    
    # Initialize V2 section status
    section_statuses = {
        1: SectionStatus.NOT_STARTED,
        2: SectionStatus.NOT_STARTED,
        3: SectionStatus.NOT_STARTED,
        4: SectionStatus.NOT_STARTED,
        5: SectionStatus.NOT_STARTED,
    }
    
    for section_num, status in section_statuses.items():
        ApplicationSection.objects.create(
            application=application,
            section_number=section_num,
            status=status
        )
    
    return application

def prepare_review_context(session_data):
    """Prepare context data for review step"""
    context = {}
    
    # Property information
    if session_data.get('property_type') == 'existing' and session_data.get('apartment_id'):
        try:
            apartment = Apartment.objects.get(id=session_data.get('apartment_id'))
            context['apartment'] = apartment
        except Apartment.DoesNotExist:
            pass
    
    # Applicant information
    if session_data.get('applicant_type') == 'existing' and session_data.get('applicant_id'):
        try:
            applicant = Applicant.objects.get(id=session_data.get('applicant_id'))
            context['applicant'] = applicant
        except Applicant.DoesNotExist:
            pass
    
    return context

@login_required
def broker_confirmation(request, application_id):
    """Broker confirmation page after creating application"""
    application = get_object_or_404(Application, id=application_id)
    
    # Only allow brokers/superusers who own this application
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to view this application.")
        return redirect('applications_list')
    
    # Get property details
    if application.apartment:
        property_address = f"{application.apartment.building.street_address_1}, {application.apartment.building.city}, {application.apartment.building.state}"
        property_name = f"{application.apartment.building.name} - Unit {application.apartment.unit_number}"
        rent_amount = application.apartment.rent_price
    else:
        property_address = application.manual_building_address or "Address not provided"
        property_name = f"{application.manual_building_name or 'Building'} - Unit {application.manual_unit_number or 'N/A'}"
        rent_amount = None
    
    # Get application status and timestamps
    from django.utils import timezone
    activities = application.activity_log.all().order_by('-timestamp')
    last_activity = activities.first() if activities else None
    
    # Build the full application URL
    if hasattr(request, 'get_host'):
        application_url = request.build_absolute_uri(
            f"/applications/{application.unique_link}/complete/?token={application.unique_link}"
        )
    else:
        application_url = f"https://{request.get_host()}/applications/{application.unique_link}/complete/?token={application.unique_link}"
    
    # Get contact info
    email_address = application.applicant.email if application.applicant else None
    phone_number = application.applicant.phone_number if application.applicant else None
    
    # Parse required documents
    required_docs = []
    if hasattr(application, 'required_documents') and application.required_documents:
        if isinstance(application.required_documents, str):
            try:
                import json
                required_docs = json.loads(application.required_documents)
            except:
                required_docs = [application.required_documents]
        elif isinstance(application.required_documents, list):
            required_docs = application.required_documents
    
    context = {
        'application': application,
        'property_name': property_name,
        'property_address': property_address,
        'rent_amount': rent_amount,
        'email_address': email_address,
        'phone_number': phone_number,
        'application_url': application_url,
        'required_docs': required_docs,
        'last_activity': last_activity,
        'activities': activities[:5],  # Show last 5 activities
    }
    
    return render(request, 'applications/broker_confirmation.html', context)


@login_required
def create_v2_application(request, apartment_id=None):
    """Create a new V2 application and redirect to Section 1"""
    apartment = None
    if apartment_id:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    
    # Check if user can create applications
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('apartments_list')
    
    # Create new V2 application
    application = Application.objects.create(
        apartment=apartment,  # Now optional
        broker=request.user,
        application_version='v2',
        current_section=1
    )
    
    # Initialize section status
    section_statuses = {
        1: SectionStatus.IN_PROGRESS,
        2: SectionStatus.NOT_STARTED,
        3: SectionStatus.NOT_STARTED,
        4: SectionStatus.NOT_STARTED,
        5: SectionStatus.NOT_STARTED,
    }
    application.section_statuses = section_statuses
    application.save()
    
    # Create ApplicationSection records
    section_names = {
        1: 'Personal Information',
        2: 'Income',
        3: 'Legal',
        4: 'Review',
        5: 'Payment'
    }
    
    for section_num, section_name in section_names.items():
        ApplicationSection.objects.create(
            application=application,
            section_number=section_num,
            status=SectionStatus.IN_PROGRESS if section_num == 1 else SectionStatus.NOT_STARTED
        )
    
    # Update success message based on what was provided
    if apartment:
        log_activity(application, f"Broker {request.user.email} created a V2 application for {apartment}")
        messages.success(request, f"New V2 application created for {apartment}")
    else:
        log_activity(application, f"Broker {request.user.email} created a V2 application (no property selected)")
        messages.success(request, "New V2 application created. Please add property details in Section 1.")
    
    return redirect('section1_personal_info', application_id=application.id)


@hybrid_csrf_protect
def v2_section1_personal_info(request, application_id):
    """Section 1 - Personal Information"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    if token:
        # Validate token for applicant access
        if token == str(application.unique_link):
            is_applicant_access = True
            # No additional authentication needed for token access
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    elif not is_preview:
        # Regular broker access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    # Get or create PersonalInfoData
    personal_info, created = PersonalInfoData.objects.get_or_create(
        application=application
    )
    
    # Pre-fill with applicant profile data if this is a newly created personal_info
    if created and application.applicant:
        from .services import ApplicationDataService
        prefill_data = ApplicationDataService.get_prefill_data_for_applicant(application.applicant)
        
        # Map prefill data to PersonalInfoData fields
        field_mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name', 
            'email': 'email',
            'phone_number': 'phone_cell',  # Note: profile has phone_number, form has phone_cell
            'date_of_birth': 'date_of_birth',
            'street_address_1': 'current_address',
            'emergency_contact_name': 'reference1_name',
            'emergency_contact_phone': 'reference1_phone',
        }
        
        # Apply prefill data to personal_info instance
        for profile_field, app_field in field_mapping.items():
            if profile_field in prefill_data and prefill_data[profile_field]:
                setattr(personal_info, app_field, prefill_data[profile_field])
        
        # Save if any data was filled
        if any(getattr(personal_info, field) for field in field_mapping.values()):
            personal_info.save()
    
    # Get application section
    section = ApplicationSection.objects.get(
        application=application,
        section_number=1
    )
    
    if request.method == 'POST':
        form = PersonalInfoForm(request.POST, instance=personal_info)
        
        if form.is_valid():
            with transaction.atomic():
                # Save personal info
                personal_info = form.save()
                
                # Update section status
                section.status = SectionStatus.COMPLETED
                section.completed_at = timezone.now()
                section.is_valid = True
                section.save()
                
                # Update application section status
                application.section_statuses[1] = SectionStatus.COMPLETED
                
                # Move to next section
                application.current_section = 2
                application.section_statuses[2] = SectionStatus.IN_PROGRESS
                application.save()
                
                # Update next section
                next_section = ApplicationSection.objects.get(
                    application=application,
                    section_number=2
                )
                next_section.status = SectionStatus.IN_PROGRESS
                next_section.started_at = timezone.now()
                next_section.save()
                
                log_activity(application, "Section 1 (Personal Information) completed")
                messages.success(request, "Personal information saved successfully!")
                
                # Check if this is a save-and-continue or save-and-exit
                if 'save_continue' in request.POST:
                    if is_applicant_access:
                        return redirect(f"{reverse('section2_income', args=[application.id])}?token={token}")
                    else:
                        return redirect('section2_income', application_id=application.id)
                else:
                    if is_applicant_access:
                        return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
                    else:
                        return redirect('application_detail', application_id=application.id)
        else:
            # Mark section as needs review if validation fails
            section.status = SectionStatus.NEEDS_REVIEW
            section.validation_errors = form.errors
            section.save()
            
            messages.error(request, "Please correct the errors below.")
    else:
        form = PersonalInfoForm(instance=personal_info)
        
        # Pre-fill desired address fields from manual application data if no apartment
        if not application.apartment and application.manual_building_address:
            form.initial['desired_address'] = application.manual_building_address
            form.initial['desired_unit'] = application.manual_unit_number
        
        # Mark section as in progress if not already
        if section.status == SectionStatus.NOT_STARTED:
            section.status = SectionStatus.IN_PROGRESS
            section.started_at = timezone.now()
            section.save()
    
    # Get previous addresses
    previous_addresses = PreviousAddress.objects.filter(
        personal_info=personal_info
    ).order_by('order')
    
    # Check if this is a preview request
    is_preview = request.GET.get('preview') == 'true'
    
    context = {
        'application': application,
        'form': form,
        'section': section,
        'previous_addresses': previous_addresses,
        'current_section': 1,
        'section_title': 'Personal Information',
        'progress_percent': 20,  # 1/5 sections
        'is_preview': is_preview,
        'preview_mode': is_preview,
        'token': token,
        'is_applicant_access': is_applicant_access,
    }
    
    # Use different templates based on access type
    if is_applicant_access:
        # Applicants get the enhanced property-focused template
        template = 'applications/v2/applicant_section1_personal_info.html'
    else:
        # Brokers and preview mode use the standard template
        template = 'applications/v2/section1_personal_info.html'
    
    return render(request, template, context)


@hybrid_csrf_protect
@require_http_methods(["POST"])
def add_previous_address(request, application_id):
    """AJAX endpoint to add a previous address"""
    application = get_object_or_404(Application, id=application_id)
    personal_info = get_object_or_404(PersonalInfoData, application=application)
    
    form = PreviousAddressForm(request.POST)
    
    if form.is_valid():
        previous_address = form.save(commit=False)
        previous_address.personal_info = personal_info
        
        # Set order
        max_order = PreviousAddress.objects.filter(
            personal_info=personal_info
        ).aggregate(max_order=Max('order'))['max_order'] or 0
        previous_address.order = max_order + 1
        
        previous_address.save()
        
        log_activity(application, f"Added previous address: {previous_address.address}")
        
        return JsonResponse({
            'success': True,
            'address_id': previous_address.id,
            'address': previous_address.address,
            'duration': previous_address.duration
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@hybrid_csrf_protect
@require_http_methods(["POST"])
def remove_previous_address(request, application_id, address_id):
    """AJAX endpoint to remove a previous address"""
    application = get_object_or_404(Application, id=application_id)
    personal_info = get_object_or_404(PersonalInfoData, application=application)
    
    try:
        address = PreviousAddress.objects.get(
            id=address_id,
            personal_info=personal_info
        )
        address_text = address.address
        address.delete()
        
        log_activity(application, f"Removed previous address: {address_text}")
        
        return JsonResponse({'success': True})
    except PreviousAddress.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Address not found'
        }, status=404)


def v2_application_overview(request, application_id):
    """Router view that determines appropriate interface based on access type"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    
    if token:
        # Token access - redirect to applicant interface
        if token == str(application.unique_link):
            return applicant_application_interface(request, application_id)
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    else:
        # No token - redirect to broker management interface
        return broker_application_management(request, application_id)


def applicant_application_interface(request, application_id):
    """Applicant-focused interface for completing application sections"""
    application = get_object_or_404(Application, id=application_id)
    token = request.GET.get('token')
    
    # Validate token for applicant access
    if not token or token != str(application.unique_link):
        messages.error(request, "Invalid or missing access token.")
        return redirect('applications_list')
    
    # Handle file upload from applicants
    if request.method == 'POST':
        document_type = request.POST.get('document_type')
        uploaded_file = request.FILES.get('file')
        
        if document_type and uploaded_file:
            try:
                # Create uploaded file record
                file_record = UploadedFile.objects.create(
                    application=application,
                    file=uploaded_file,
                    document_type=document_type
                )
                
                # Log activity (legacy)
                log_activity(application, f"Applicant uploaded document: {document_type}")
                
                # Track document upload for applicant activity tracking
                if application.applicant:
                    trigger_document_uploaded(
                        applicant=application.applicant,
                        document_type=document_type,
                        filename=uploaded_file.name,
                        request=request
                    )
                
                messages.success(request, f"Document '{document_type}' uploaded successfully!")
                
            except Exception as e:
                messages.error(request, f"Error uploading file: {str(e)}")
        else:
            messages.error(request, "Please select a document type and file to upload.")
        
        return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
    
    # Get all sections with their status
    sections = ApplicationSection.objects.filter(
        application=application
    ).order_by('section_number')
    
    # Calculate progress
    completed_sections = sections.filter(status=SectionStatus.COMPLETED).count()
    total_sections = sections.count()
    progress_percent = (completed_sections / total_sections) * 100 if total_sections > 0 else 0
    
    # Get uploaded files
    uploaded_files = application.uploaded_files.all()
    
    context = {
        'application': application,
        'sections': sections,
        'progress_percent': progress_percent,
        'completed_sections': completed_sections,
        'total_sections': total_sections,
        'uploaded_files': uploaded_files,
        'token': token,
        'is_applicant_access': True,
    }
    
    return render(request, 'applications/v2/applicant_application_overview.html', context)


def broker_application_management(request, application_id):
    """Broker-focused management dashboard for application oversight"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check authentication and authorization for broker access
    if not request.user.is_authenticated:
        messages.error(request, "You must be logged in to access this application.")
        return redirect('applications_list')
    
    # Check if user has permission to manage this application
    if not (request.user.is_superuser or 
            request.user == application.broker or 
            (request.user.is_staff and request.user.is_broker)):
        messages.error(request, "You are not authorized to manage this application.")
        return redirect('applications_list')
    
    # Handle file upload/analysis from brokers (brokers upload for analysis, not completion)
    if request.method == 'POST':
        if not (request.user.is_superuser or request.user == application.broker):
            messages.error(request, "You are not authorized to upload files.")
            return redirect('broker_application_management', application_id=application.id)
        
        document_type = request.POST.get('document_type')
        uploaded_file = request.FILES.get('file')
        
        if document_type and uploaded_file:
            try:
                # Create uploaded file record
                file_record = UploadedFile.objects.create(
                    application=application,
                    file=uploaded_file,
                    document_type=document_type
                )
                
                # Log activity (legacy)
                log_activity(application, f"Broker uploaded document for analysis: {document_type}")
                
                # Track document upload for applicant activity tracking
                if application.applicant:
                    # Use activity tracker directly for broker uploads
                    from applicants.activity_tracker import ActivityTracker
                    ActivityTracker.track_activity(
                        applicant=application.applicant,
                        activity_type='document_uploaded',
                        description=f"Broker uploaded {document_type} for verification",
                        triggered_by=request.user,
                        metadata={
                            'document_type': document_type,
                            'uploaded_by': 'broker',
                            'file_name': uploaded_file.name
                        },
                        request=request
                    )
                
                messages.success(request, f"Document '{document_type}' uploaded successfully!")
                
            except Exception as e:
                messages.error(request, f"Error uploading file: {str(e)}")
        else:
            messages.error(request, "Please select a document type and file to upload.")
        
        return redirect('broker_application_management', application_id=application.id)
    
    # Get all sections with their status
    sections = ApplicationSection.objects.filter(
        application=application
    ).order_by('section_number')
    
    # Calculate progress
    completed_sections = sections.filter(status=SectionStatus.COMPLETED).count()
    total_sections = sections.count()
    progress_percent = (completed_sections / total_sections) * 100 if total_sections > 0 else 0
    
    # Get uploaded files with analysis results
    uploaded_files = application.uploaded_files.all()
    
    # Get application activity log
    activity_log = application.activity_log.all().order_by('-timestamp')[:10]
    
    # Get personal info if available
    personal_info = getattr(application, 'personal_info', None)
    
    context = {
        'application': application,
        'sections': sections,
        'progress_percent': progress_percent,
        'completed_sections': completed_sections,
        'total_sections': total_sections,
        'uploaded_files': uploaded_files,
        'activity_log': activity_log,
        'personal_info': personal_info,
        'is_broker_access': True,
    }
    
    return render(request, 'applications/v2/broker_management.html', context)


def v2_section_navigation(request, application_id, section_number):
    """Navigate directly to a specific section"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if user can access this section
    # (You might want to add logic to prevent jumping ahead)
    
    section_views = {
        1: 'v2_section1',
        2: 'v2_section2',
        3: 'v2_section3',
        4: 'v2_section4',
        5: 'v2_section5',
    }
    
    view_name = section_views.get(section_number)
    if view_name:
        return redirect(view_name, application_id=application.id)
    else:
        messages.error(request, "Invalid section number")
        return redirect('application_detail', application_id=application.id)


# Placeholder views for other sections
@hybrid_csrf_protect
def v2_section2_income(request, application_id):
    """Section 2 - Income & Employment"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    if token:
        # Validate token for applicant access
        if token == str(application.unique_link):
            is_applicant_access = True
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    elif not is_preview:
        # Regular broker access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    # Get or create IncomeData
    income_data, created = IncomeData.objects.get_or_create(
        application=application,
        defaults={
            'employment_type': 'employed',  # Default choice
            'company_name': '',
            'position': '',
            'annual_income': 0.00,
            'supervisor_name': '',
            'supervisor_email': '',
            'supervisor_phone': '',
            'start_date': timezone.now().date(),
        }
    )
    
    # Pre-fill with applicant profile data if this is a newly created income_data
    if created and application.applicant:
        from .services import ApplicationDataService
        prefill_data = ApplicationDataService.get_prefill_data_for_applicant(application.applicant)
        
        # Map employment data from applicant profile
        field_mapping = {
            'company_name': 'company_name',
            'position': 'position', 
            'annual_income': 'annual_income',
            'employment_status': 'employment_type',
        }
        
        # Apply prefill data to income_data instance
        for profile_field, app_field in field_mapping.items():
            if profile_field in prefill_data and prefill_data[profile_field]:
                value = prefill_data[profile_field]
                
                # Convert annual to monthly income
                if profile_field == 'annual_income' and value:
                    try:
                        value = float(value) / 12  # Convert annual to monthly
                    except (ValueError, TypeError):
                        value = None
                
                if value:
                    setattr(income_data, app_field, value)
        
        # Save if any data was filled
        if any(getattr(income_data, field) for field in field_mapping.values() if field):
            income_data.save()
    
    # Get application section
    try:
        section = ApplicationSection.objects.get(
            application=application,
            section_number=2
        )
    except ApplicationSection.DoesNotExist:
        # Create section if it doesn't exist
        section = ApplicationSection.objects.create(
            application=application,
            section_number=2,
            status=SectionStatus.NOT_STARTED
        )
    
    if request.method == 'POST':
        form = IncomeForm(request.POST, instance=income_data)
        
        if form.is_valid():
            with transaction.atomic():
                # Save income data
                income_data = form.save()
                
                # Update section status
                section.status = SectionStatus.COMPLETED
                section.completed_at = timezone.now()
                section.is_valid = True
                section.save()
                
                # Update application section status
                application.section_statuses[2] = SectionStatus.COMPLETED
                
                # Move to next section
                application.current_section = 3
                application.section_statuses[3] = SectionStatus.IN_PROGRESS
                application.save()
                
                # Update next section
                next_section, _ = ApplicationSection.objects.get_or_create(
                    application=application,
                    section_number=3,
                    defaults={'status': SectionStatus.IN_PROGRESS, 'started_at': timezone.now()}
                )
                next_section.status = SectionStatus.IN_PROGRESS
                next_section.started_at = timezone.now()
                next_section.save()
                
                log_activity(application, "Section 2 (Income & Employment) completed")
                messages.success(request, "Income information saved successfully!")
                
                # Check if this is a save-and-continue or save-and-exit
                if 'save_continue' in request.POST:
                    if is_applicant_access:
                        return redirect(f"{reverse('section3_legal', args=[application.id])}?token={token}")
                    else:
                        return redirect('section3_legal', application_id=application.id)
                else:
                    if is_applicant_access:
                        return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
                    else:
                        return redirect('application_detail', application_id=application.id)
        else:
            # Mark section as needs review if validation fails
            section.status = SectionStatus.NEEDS_REVIEW
            section.validation_errors = form.errors
            section.save()
            
            messages.error(request, "Please correct the errors below.")
    else:
        form = IncomeForm(instance=income_data)
        
        # Mark section as in progress if not already
        if section.status == SectionStatus.NOT_STARTED:
            section.status = SectionStatus.IN_PROGRESS
            section.started_at = timezone.now()
            section.save()
    
    context = {
        'application': application,
        'form': form,
        'section': section,
        'current_section': 2,
        'section_title': 'Income & Employment',
        'progress_percent': 40,  # 2/5 sections
        'is_preview': is_preview,
        'token': token,
        'is_applicant_access': is_applicant_access,
    }
    
    # Use different templates based on access type
    if is_applicant_access:
        template = 'applications/v2/applicant_section2_income.html'
    else:
        template = 'applications/v2/section2_income.html'
    
    return render(request, template, context)


@hybrid_csrf_protect
def v2_section3_legal(request, application_id):
    """Section 3 - Legal (placeholder)"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    if token:
        # Validate token for applicant access
        if token == str(application.unique_link):
            is_applicant_access = True
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    elif not is_preview:
        # Regular broker access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    messages.info(request, "Section 3 - Legal coming soon!")
    
    if is_applicant_access:
        return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
    else:
        return redirect('application_detail', application_id=application.id)


@hybrid_csrf_protect
def v2_section4_review(request, application_id):
    """Section 4 - Review all application data before payment"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    if token:
        # Validate token for applicant access
        if token == str(application.unique_link):
            is_applicant_access = True
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    elif not is_preview:
        # Regular broker access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    # Gather all application data for review
    personal_info = PersonalInfoData.objects.filter(application=application).first()
    income_data = IncomeData.objects.filter(application=application).first()
    legal_docs = LegalDocuments.objects.filter(application=application).first()
    uploaded_files = application.uploaded_files.all()
    
    # Get or create section tracking
    section, _ = ApplicationSection.objects.get_or_create(
        application=application,
        section_number=4,
        defaults={'status': SectionStatus.IN_PROGRESS}
    )
    
    # Enhanced validation: Check field completeness, not just record existence
    sections_complete = {
        'personal': False,
        'personal_message': '',
        'income': False,
        'income_message': '',
        'legal': legal_docs and legal_docs.discrimination_form_signed and legal_docs.brokers_form_signed,
        'required_docs': False,
        'docs_message': ''
    }
    
    # Validate Personal Information (check required fields)
    if personal_info:
        missing_fields = []
        if not personal_info.first_name:
            missing_fields.append('first name')
        if not personal_info.last_name:
            missing_fields.append('last name')
        if not personal_info.email:
            missing_fields.append('email')
        
        if missing_fields:
            sections_complete['personal_message'] = f"Missing: {', '.join(missing_fields)}"
        else:
            sections_complete['personal'] = True
    else:
        sections_complete['personal_message'] = "Section not started"
    
    # Validate Income Information (check essential fields)
    if income_data:
        missing_fields = []
        if not income_data.company_name:
            missing_fields.append('company name')
        if not income_data.annual_income or income_data.annual_income <= 0:
            missing_fields.append('valid annual income')
        
        if missing_fields:
            sections_complete['income_message'] = f"Missing: {', '.join(missing_fields)}"
        else:
            sections_complete['income'] = True
    else:
        sections_complete['income_message'] = "Section not started"
    
    # Validate Required Documents
    required_documents_list = application.required_documents or []
    required_documents_status = {}
    missing_docs = []
    
    if required_documents_list:
        # Get document type choices for display names
        from .models import RequiredDocumentType
        doc_choices = dict(RequiredDocumentType.choices)
        
        for doc_type in required_documents_list:
            # Check if this document type has been uploaded
            doc_uploaded = uploaded_files.filter(document_type=doc_type).exists()
            required_documents_status[doc_type] = {
                'display_name': doc_choices.get(doc_type, doc_type),
                'uploaded': doc_uploaded
            }
            if not doc_uploaded:
                missing_docs.append(doc_choices.get(doc_type, doc_type))
        
        if missing_docs:
            sections_complete['docs_message'] = f"Missing: {', '.join(missing_docs)}"
        else:
            sections_complete['required_docs'] = True
    else:
        # If no documents are required, mark as complete
        sections_complete['required_docs'] = True
    
    # Check if all validations pass
    all_sections_complete = (
        sections_complete['personal'] and 
        sections_complete['income'] and 
        sections_complete['legal'] and
        sections_complete['required_docs']
    )
    
    # Parse document analysis results for display
    for file in uploaded_files:
        if file.analysis_results:
            try:
                file.analysis_results = json.loads(file.analysis_results)
            except json.JSONDecodeError:
                file.analysis_results = None
    
    # Handle confirmation and proceed to payment
    if request.method == 'POST' and 'confirm_proceed' in request.POST:
        if not all_sections_complete:
            messages.error(request, "Please complete all sections before proceeding to payment.")
        else:
            # Mark review section as complete
            section.status = SectionStatus.COMPLETED
            section.completed_at = timezone.now()
            section.save()
            
            # Update application tracking
            application.current_section = 5
            application.save()
            
            # Create or update payment section
            payment_section, _ = ApplicationSection.objects.get_or_create(
                application=application,
                section_number=5,
                defaults={'status': SectionStatus.IN_PROGRESS, 'started_at': timezone.now()}
            )
            
            log_activity(application, "Section 4 (Review) completed - proceeding to payment")
            messages.success(request, "Review complete! Proceeding to payment...")
            
            if is_applicant_access:
                return redirect(f"{reverse('section5_payment', args=[application.id])}?token={token}")
            else:
                return redirect('section5_payment', application_id=application.id)
    
    # Build context for template
    context = {
        'application': application,
        'personal_info': personal_info,
        'income_data': income_data,
        'legal_docs': legal_docs,
        'uploaded_files': uploaded_files,
        'sections_complete': sections_complete,
        'all_sections_complete': all_sections_complete,
        'required_documents_list': required_documents_list,
        'required_documents_status': required_documents_status,
        'token': token,
        'is_applicant_access': is_applicant_access,
        'is_preview': is_preview,
        
        # Include related data if available
        'previous_addresses': personal_info.previous_addresses.all() if personal_info else [],
        'additional_jobs': income_data.additional_jobs.all() if income_data else [],
        'additional_income': income_data.additional_income.all() if income_data else [],
        'assets': income_data.assets.all() if income_data else [],
        
        # Property details
        'property_display': application.get_building_display() if application else 'Not specified',
        'unit_display': application.get_unit_display() if application else 'Not specified',
    }
    
    # Use the same template for both access types
    template = 'applications/v2/section4_review.html'
    return render(request, template, context)


@hybrid_csrf_protect
def v2_section5_payment(request, application_id):
    """Section 5 - Payment processing"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    
    if token:
        # Validate token for applicant access
        if token == str(application.unique_link):
            is_applicant_access = True
        else:
            messages.error(request, "Invalid access token.")
            return redirect('applications_list')
    else:
        # Regular broker access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    # Check if payment already completed
    from .models import ApplicationPayment, PaymentStatus
    existing_payment = ApplicationPayment.objects.filter(
        application=application,
        status=PaymentStatus.COMPLETED
    ).first()
    
    if existing_payment:
        messages.info(request, "Payment has already been processed for this application.")
        if is_applicant_access:
            return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
        else:
            return redirect('application_detail', application_id=application.id)
    
    # Get or create payment record
    payment, created = ApplicationPayment.objects.get_or_create(
        application=application,
        defaults={
            'amount': application.application_fee_amount,
            'status': PaymentStatus.PENDING
        }
    )
    
    if request.method == 'POST':
        # Extract card data from form
        card_data = {
            'card_number': request.POST.get('card_number', '').replace(' ', ''),
            'exp_month': request.POST.get('exp_month', ''),
            'exp_year': request.POST.get('exp_year', ''),
            'cvv': request.POST.get('cvv', ''),
            'cardholder_name': request.POST.get('cardholder_name', ''),
            'save_card': request.POST.get('save_card') == 'on'
        }
        
        # Validate required fields
        if not all([card_data['card_number'], card_data['exp_month'], 
                   card_data['exp_year'], card_data['cvv'], card_data['cardholder_name']]):
            messages.error(request, "Please fill in all required payment fields.")
        else:
            # Process payment
            from .payment_utils import PaymentProcessor
            processor = PaymentProcessor()
            
            success, message = processor.process_application_payment(
                application=application,
                card_data=card_data
            )
            
            if success:
                # Mark section as complete
                from .models import ApplicationSection, SectionStatus
                section, _ = ApplicationSection.objects.get_or_create(
                    application=application,
                    section_number=5,
                    defaults={'status': SectionStatus.IN_PROGRESS}
                )
                section.status = SectionStatus.COMPLETED
                section.completed_at = timezone.now()
                section.save()
                
                # Update application status
                application.status = 'submitted'
                application.submitted_at = timezone.now()
                application.save()
                
                messages.success(request, message)
                
                # TODO: Send confirmation email
                # from .email_utils import send_payment_confirmation
                # send_payment_confirmation(application)
                
                # Redirect to success page
                if is_applicant_access:
                    return redirect(f"{reverse('application_completion_success', args=[application.unique_link])}")
                else:
                    return redirect('application_detail', application_id=application.id)
            else:
                messages.error(request, f"Payment failed: {message}")
    
    # Prepare context for template
    context = {
        'application': application,
        'payment': payment,
        'token': token,
        'is_applicant_access': is_applicant_access,
        'application_fee': application.application_fee_amount,
        'SOLA_SANDBOX_MODE': getattr(settings, 'SOLA_SANDBOX_MODE', True),
    }
    
    template = 'applications/v2/section5_payment.html'
    return render(request, template, context)


def handle_temp_application_creation(request):
    """Create a temporary application for preview purposes"""
    try:
        # Create new applicant if needed
        applicant = None
        applicant_type = request.POST.get('applicant_type')
        
        if applicant_type == 'existing':
            applicant_id = request.POST.get('applicant')
            if applicant_id:
                try:
                    applicant = Applicant.objects.get(id=applicant_id)
                except Applicant.DoesNotExist:
                    pass
                    
        elif applicant_type == 'new':
            # Create new applicant with minimal info
            email = request.POST.get('new_applicant_email')
            phone = request.POST.get('new_applicant_phone')
            first_name = request.POST.get('new_applicant_first_name', '')
            last_name = request.POST.get('new_applicant_last_name', '')
            
            if email:
                # Check if applicant already exists
                existing_applicant = Applicant.objects.filter(email=email).first()
                if existing_applicant:
                    applicant = existing_applicant
                else:
                    from datetime import date
                    applicant = Applicant.objects.create(
                        email=email,
                        phone_number=phone or '',
                        first_name=first_name,
                        last_name=last_name,
                        date_of_birth=date(1990, 1, 1),  # Temporary date for preview
                        street_address_1='Temporary Address',  # Required field
                        city='New York',  # Required field
                        zip_code='10001'  # Required field
                    )
        
        # Get property information
        apartment = None
        property_type = request.POST.get('property_type')
        
        if property_type == 'existing':
            apartment_id = request.POST.get('apartment')
            if apartment_id:
                try:
                    apartment = Apartment.objects.get(id=apartment_id)
                except Apartment.DoesNotExist:
                    pass
        
        # Create temporary application
        application = Application.objects.create(
            apartment=apartment,
            applicant=applicant,
            broker=request.user,
            application_version='v2',
            current_section=1,
            status='draft'  # Mark as draft
        )
        
        # Set manual property fields if needed
        if property_type == 'manual':
            application.manual_building_name = request.POST.get('manual_building_name', '')
            application.manual_building_address = request.POST.get('manual_building_address', '')
            application.manual_unit_number = request.POST.get('manual_unit_number', '')
        
        # Set customization options
        required_documents = request.POST.getlist('required_documents')
        application.required_documents = required_documents
        
        application_fee = request.POST.get('application_fee', '50.00')
        try:
            application.application_fee_amount = float(application_fee)
        except (ValueError, TypeError):
            application.application_fee_amount = 50.00
        
        application.save()
        
        # Initialize V2 section status
        section_statuses = {
            1: SectionStatus.NOT_STARTED,
            2: SectionStatus.NOT_STARTED,
            3: SectionStatus.NOT_STARTED,
            4: SectionStatus.NOT_STARTED,
            5: SectionStatus.NOT_STARTED,
        }
        application.section_statuses = section_statuses
        application.save()
        
        # Create ApplicationSection records
        section_names = {
            1: 'Personal Information',
            2: 'Income',
            3: 'Legal',
            4: 'Review',
            5: 'Payment'
        }
        
        for section_num, section_name in section_names.items():
            ApplicationSection.objects.create(
                application=application,
                section_number=section_num,
                status=SectionStatus.NOT_STARTED
            )
        
        return JsonResponse({
            'success': True,
            'application_id': application.id,
            'message': 'Temporary application created for preview'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required
def application_preview(request, application_id):
    """Show application preview for brokers - exactly what applicants will see"""
    application = get_object_or_404(Application, id=application_id)
    
    # Only allow brokers/superusers who own this application
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to preview this application.")
        return redirect('applications_list')
    
    # Redirect to Section 1 with preview flag so brokers see the actual application form
    return redirect(f"{reverse('section1_personal_info', args=[application_id])}?preview=true")


@login_required
def broker_prefill_dashboard(request, application_id):
    """Broker pre-fill dashboard showing all sections"""
    application = get_object_or_404(Application, id=application_id)
    
    # Only allow brokers/superusers who own this application
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to pre-fill this application.")
        return redirect('applications_list')
    
    # Get or create data objects to check completion status
    personal_info, _ = PersonalInfoData.objects.get_or_create(application=application)
    
    # Create IncomeData with default values for required fields
    from datetime import date
    from decimal import Decimal
    income_data, _ = IncomeData.objects.get_or_create(
        application=application,
        defaults={
            'employment_type': 'employed',  # Default employment type
            'company_name': '',
            'position': '',
            'annual_income': Decimal('0.00'),  # Default to 0
            'supervisor_name': '',
            'supervisor_email': 'temp@example.com',  # Temporary email
            'supervisor_phone': '',
            'start_date': date.today(),  # Default to today
        }
    )
    # Note: No LegalData model exists yet, using placeholder
    
    # Calculate completion percentages
    def calculate_personal_info_progress(data):
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'date_of_birth', 'current_address']
        completed = sum(1 for field in fields if getattr(data, field, None))
        return (completed / len(fields)) * 100
    
    def calculate_income_progress(data):
        fields = ['company_name', 'position', 'annual_income', 'start_date']
        completed = sum(1 for field in fields if getattr(data, field, None))
        return (completed / len(fields)) * 100
    
    def calculate_legal_progress():
        # Legal section not implemented yet, return 0
        return 0
    
    personal_info_progress = calculate_personal_info_progress(personal_info)
    income_progress = calculate_income_progress(income_data)
    legal_progress = calculate_legal_progress()
    
    # Determine status
    def get_status(progress):
        if progress >= 80:
            return 'completed'
        elif progress > 0:
            return 'partial'
        else:
            return 'not_started'
    
    context = {
        'application': application,
        'personal_info_status': get_status(personal_info_progress),
        'income_status': get_status(income_progress),
        'legal_status': get_status(legal_progress),
        'personal_info_progress': int(personal_info_progress),
        'income_progress': int(income_progress),
        'legal_progress': int(legal_progress),
    }
    
    return render(request, 'applications/broker_prefill_dashboard.html', context)


@login_required
def broker_prefill_section1(request, application_id):
    """Broker pre-fill for Section 1: Personal Information"""
    application = get_object_or_404(Application, id=application_id)
    
    # Only allow brokers/superusers who own this application
    if not (request.user.is_superuser or request.user == application.broker):
        messages.error(request, "You are not authorized to pre-fill this application.")
        return redirect('applications_list')
    
    # Get or create personal info data
    personal_info, created = PersonalInfoData.objects.get_or_create(application=application)
    
    if request.method == 'POST':
        # Process form data
        personal_info.first_name = request.POST.get('first_name', '').strip()
        personal_info.last_name = request.POST.get('last_name', '').strip()
        personal_info.email = request.POST.get('email', '').strip()
        personal_info.phone_number = request.POST.get('phone_number', '').strip()
        personal_info.date_of_birth = request.POST.get('date_of_birth') or None
        personal_info.current_address = request.POST.get('current_address', '').strip()
        personal_info.current_city = request.POST.get('current_city', '').strip()
        personal_info.current_state = request.POST.get('current_state', '').strip()
        personal_info.current_zip = request.POST.get('current_zip', '').strip()
        personal_info.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
        personal_info.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
        personal_info.emergency_contact_relationship = request.POST.get('emergency_contact_relationship', '').strip()
        
        # Add broker note
        personal_info.broker_notes = f"Pre-filled by broker {request.user.email} on {timezone.now().strftime('%m/%d/%Y %H:%M')}"
        personal_info.save()
        
        # Log activity
        log_activity(application, f"Broker {request.user.email} pre-filled personal information")
        
        messages.success(request, "Personal information saved successfully!")
        return redirect('broker_prefill_dashboard', application_id=application.id)
    
    context = {
        'application': application,
        'personal_info': personal_info,
        'is_broker_prefill': True,
    }
    
    return render(request, 'applications/broker_prefill_section1.html', context)


@login_required
def prefill_status_api(request, application_id):
    """API endpoint to get pre-fill status"""
    application = get_object_or_404(Application, id=application_id)
    
    # Only allow brokers/superusers who own this application
    if not (request.user.is_superuser or request.user == application.broker):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    try:
        # Get data objects
        personal_info = PersonalInfoData.objects.filter(application=application).first()
        income_data = IncomeData.objects.filter(application=application).first()
        
        def get_completion_status(data, fields):
            if not data:
                return 'not_started'
            completed = sum(1 for field in fields if getattr(data, field, None))
            if completed == 0:
                return 'not_started'
            elif completed >= len(fields) * 0.8:  # 80% threshold
                return 'completed'
            else:
                return 'partial'
        
        # Check completion status
        status = {
            'section1': get_completion_status(personal_info, ['first_name', 'last_name', 'email', 'phone_number']),
            'section2': get_completion_status(income_data, ['company_name', 'position', 'annual_income']),
            'section3': 'not_started'  # Legal section typically not pre-filled
        }
        
        return JsonResponse({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
