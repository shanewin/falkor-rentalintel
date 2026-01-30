from users.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .forms import PersonalInfoForm, PreviousAddressForm, IncomeForm
from .models import (
    UploadedFile, Application, ApplicationActivity, ApplicationSection, 
    PersonalInfoData, PreviousAddress, SectionStatus, IncomeData,
    Pet, PetPhoto
)
from django.core.files.base import ContentFile
import base64
from applicants.models import Applicant, SavedApartment
from apartments.models import Apartment
from applicants.apartment_matching import ApartmentMatchingService
from applicants.smart_insights import SmartInsights
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





# ✅ DISPLAY APPLICATION DETAILS FOR BROKER/APPLICANT
import json

def application_detail(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    uploaded_files = application.uploaded_files.all()

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
        
        # Show applications assigned to the broker OR unassigned applications for their apartments
        applications = Application.objects.filter(
            models.Q(broker=request.user) | 
            (models.Q(apartment__in=broker_apartments) & models.Q(broker__isnull=True))
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
    """Step 1: Applicant Selection (Refactored)"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Handle pre-selected applicant from GET parameters (e.g. from profile page)
    preselected_applicant_id = request.GET.get('applicant_id')
    if preselected_applicant_id:
        try:
            applicant = Applicant.objects.get(id=preselected_applicant_id)
            set_broker_session_data(request, 'applicant_type', 'existing')
            set_broker_session_data(request, 'applicant_id', preselected_applicant_id)
            # If coming from profile, we can skip to step 2 directly if desired, 
            # but let's show step 1 with it selected for clarity.
        except Applicant.DoesNotExist:
            pass

    if request.method == 'POST':
        # Store step 1 data in session
        applicant_type = request.POST.get('applicant_type')
        set_broker_session_data(request, 'applicant_type', applicant_type)
        
        if applicant_type == 'existing':
            applicant_id = request.POST.get('applicant')
            if not applicant_id:
                messages.error(request, "Please select an existing applicant.")
                return redirect('broker_create_step1')
            set_broker_session_data(request, 'applicant_id', applicant_id)
        elif applicant_type == 'new':
            first_name = request.POST.get('new_applicant_first_name', '').strip()
            last_name = request.POST.get('new_applicant_last_name', '').strip()
            email = request.POST.get('new_applicant_email', '').strip()
            phone = request.POST.get('new_applicant_phone', '').strip()
            
            # Strict validation for new prospects
            if not all([first_name, last_name, email]):
                messages.error(request, "First Name, Last Name, and Email are required for new prospects.")
                # Store whatever they entered so far
                set_broker_session_data(request, 'new_applicant_first_name', first_name)
                set_broker_session_data(request, 'new_applicant_last_name', last_name)
                set_broker_session_data(request, 'new_applicant_email', email)
                set_broker_session_data(request, 'new_applicant_phone', phone)
                return redirect('broker_create_step1')

            set_broker_session_data(request, 'new_applicant_email', email)
            set_broker_session_data(request, 'new_applicant_phone', phone)
            set_broker_session_data(request, 'new_applicant_first_name', first_name)
            set_broker_session_data(request, 'new_applicant_last_name', last_name)
            # Clear existing applicant_id if switching to new
            set_broker_session_data(request, 'applicant_id', None)
        
        return redirect('broker_create_step2')
    
    # Get available applicants for selection - filter by assigned broker if not superuser
    if request.user.is_superuser:
        applicants = Applicant.objects.all().order_by('_first_name', '_last_name')
    else:
        from django.db.models import Q
        applicants = Applicant.objects.filter(
            Q(assigned_broker=request.user) |
            Q(applications__apartment__building__brokers=request.user)
        ).distinct().order_by('_first_name', '_last_name')
    
    # Prefetch data for preview card and pre-calculate simplified scores
    from applicants.smart_insights import SmartInsights
    applicants = applicants.prefetch_related('photos', 'jobs', 'income_sources', 'previous_addresses')
    
    # Add temporary score attribute for template
    for applicant in applicants:
        # We only need the overall_score for the list view to keep it fast
        analysis = SmartInsights.analyze_applicant(applicant)
        applicant.smart_score = analysis['overall_score']
    
    context = {
        'applicants': applicants,
        'current_step': 1,
        'session_data': get_broker_session_data(request),
    }
    return render(request, 'applications/broker_create_step1.html', context)

@login_required
def broker_create_step2(request):
    """Step 2: Property Selection (Refactored)"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Check if applicant was selected in Step 1
    applicant_id = get_broker_session_data(request, 'applicant_id')
    applicant_type = get_broker_session_data(request, 'applicant_type')
    
    if not applicant_type:
        messages.warning(request, "Please complete step 1 first.")
        return redirect('broker_create_step1')
    
    applicant = None
    if applicant_id:
        try:
            applicant = Applicant.objects.get(id=applicant_id)
        except Applicant.DoesNotExist:
            pass

    if request.method == 'POST':
        # Store step 2 data in session
        property_type = request.POST.get('property_type')
        
        # Enforce restriction: only superusers can enter property manually
        if property_type == 'manual' and not request.user.is_superuser:
            messages.error(request, "You are not authorized to enter properties manually. Please select an existing property.")
            return redirect('broker_create_step2')
        
        set_broker_session_data(request, 'property_type', property_type)
        
        if property_type == 'existing':
            apartment_id = request.POST.get('apartment')
            set_broker_session_data(request, 'apartment_id', apartment_id)
        elif property_type == 'manual' and request.user.is_superuser:
            set_broker_session_data(request, 'manual_building_name', request.POST.get('manual_building_name', ''))
            set_broker_session_data(request, 'manual_building_address', request.POST.get('manual_building_address', ''))
            set_broker_session_data(request, 'manual_unit_number', request.POST.get('manual_unit_number', ''))
        
        return redirect('broker_create_step3')
    
    # --- Apartment Prioritization Logic ---
    saved_apartments = []
    smart_matches = []
    other_apartments = []
    
    already_listed_ids = set()
    
    if applicant:
        # 1. Saved Apartments
        saved_qs = SavedApartment.objects.filter(applicant=applicant).select_related('apartment', 'apartment__building')
        for sa in saved_qs:
            if sa.apartment.id not in already_listed_ids:
                saved_apartments.append(sa.apartment)
                already_listed_ids.add(sa.apartment.id)
        
        # 2. Smart Matches
        try:
            matching_service = ApartmentMatchingService(applicant)
            matches = matching_service.get_apartment_matches(limit=15)
            for match in matches:
                apt = match['apartment']
                if apt.id not in already_listed_ids:
                    # Add match percentage for display
                    apt.match_percentage = match['match_percentage']
                    smart_matches.append(apt)
                    already_listed_ids.add(apt.id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting smart matches in broker_create_step2: {e}")
    
    # 3. All Other Available Apartments
    others_qs = Apartment.objects.filter(status='available').exclude(id__in=already_listed_ids).select_related('building').prefetch_related('images', 'amenities').order_by('building__name', 'unit_number')
    other_apartments = list(others_qs)
    
    context = {
        'applicant': applicant,
        'saved_apartments': saved_apartments,
        'smart_matches': smart_matches,
        'other_apartments': other_apartments,
        'current_step': 2,
        'session_data': get_broker_session_data(request),
    }
    return render(request, 'applications/broker_create_step2.html', context)

@login_required
def broker_create_step3(request):
    """Step 3: Application Settings & Review (Consolidated)"""
    if not (request.user.is_broker or request.user.is_superuser):
        messages.error(request, "You are not authorized to create applications.")
        return redirect('applications_list')
    
    # Check if this step is allowed
    session_data = get_broker_session_data(request)
    if not session_data.get('property_type') or not session_data.get('applicant_type'):
        messages.warning(request, "Please complete previous steps first.")
        return redirect('broker_create_step1')
    
    if request.method == 'POST':
        try:
            # Store final settings
            application_fee = request.POST.get('application_fee', '50.00')
            set_broker_session_data(request, 'application_fee', application_fee)
            
            # Refresh session data to include the fee we just set
            final_session_data = get_broker_session_data(request)

            # Create the application directly (Merged from Step 4)
            application = create_application_from_session(request, final_session_data)
            
            # Clear session data
            clear_broker_session_data(request)
            
            messages.success(request, "Application created successfully!")
            return redirect('broker_confirmation', application_id=application.id)
            
        except Exception as e:
            messages.error(request, f"Error creating application: {str(e)}")
            return redirect('broker_create_step3')
    
    # Fetch objects for display
    applicant = None
    if session_data.get('applicant_id'):
        # KEY FIX: Query Applicant model, not User model. 
        # Also prefetch photos and calculate score for the rich summary card
        try:
            from applicants.smart_insights import SmartInsights
            applicant = Applicant.objects.select_related('user').prefetch_related('photos').filter(id=session_data.get('applicant_id')).first()
            if applicant:
                analysis = SmartInsights.analyze_applicant(applicant)
                applicant.smart_score = analysis['overall_score']
        except ImportError:
            # Fallback if SmartInsights not available or circular import
            applicant = Applicant.objects.filter(id=session_data.get('applicant_id')).first()
        
    apartment = None
    if session_data.get('apartment_id'):
        # Prefetch amenities and images for rich summary card
        apartment = Apartment.objects.select_related('building').prefetch_related('amenities').filter(id=session_data.get('apartment_id')).first()

    context = {
        'current_step': 3,
        'session_data': session_data,
        'applicant': applicant,
        'apartment': apartment,
        'is_last_step': True
    }
    return render(request, 'applications/broker_create_step3.html', context)



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


def process_cropped_image(crop_data_json, original_file):
    if crop_data_json:
        try:
            crop_info = json.loads(crop_data_json)
            if crop_info.get('cropped') and crop_info.get('croppedImage'):
                # Extract base64 image data
                image_data = crop_info['croppedImage']
                if 'base64,' in image_data:
                    format, imgstr = image_data.split('base64,')
                    ext = format.split('/')[-1].split(';')[0]
                    # Create a ContentFile from the base64 data
                    return ContentFile(base64.b64decode(imgstr), name=f'cropped.{ext}')
        except Exception as e:
            print(f"Error processing crop data: {e}")
    return original_file


@hybrid_csrf_protect
def v2_section1_personal_info(request, application_id):
    """Section 1 - Personal Information"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    # Validate access: valid token OR authenticated as the correct applicant
    if token and token == str(application.unique_link):
        is_applicant_access = True
    elif request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        is_applicant_access = True
    elif not is_preview:
        # Regular broker/staff access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
        # (Implicitly allows access if authenticated and not applicant, assuming broker permission checked elsewhere or allowed)
    
    # Get or create PersonalInfoData
    personal_info, created = PersonalInfoData.objects.get_or_create(
        application=application
    )
    
    # Pre-fill with applicant profile data
    if application.applicant:
        from .services import ApplicationDataService
        prefill_data = ApplicationDataService.get_prefill_data_for_applicant(application.applicant)
        
        # Map prefill data to PersonalInfoData fields
        field_mapping = {
            'first_name': 'first_name',
            'middle_name': 'middle_name',
            'last_name': 'last_name', 
            'suffix': 'suffix',
            'email': 'email',
            'phone_cell': 'phone_cell',
            'date_of_birth': 'date_of_birth',
            'street_address_1': 'street_address_1',
            'street_address_2': 'street_address_2',
            'city': 'city',
            'state': 'state',
            'zip_code': 'zip_code',
            'current_address_years': 'current_address_years',
            'current_address_months': 'current_address_months',
            'housing_status': 'housing_status',
            'current_monthly_rent': 'current_monthly_rent',
            'is_rental_property': 'is_rental_property',
            'landlord_name': 'landlord_name',
            'landlord_phone': 'landlord_phone',
            'landlord_email': 'landlord_email',
            'reason_for_moving': 'reason_for_moving',
            'desired_move_in_date': 'desired_move_in_date',
            'has_pets': 'has_pets',
        }
        
        # Apply prefill data to personal_info instance ONLY if the field is currently empty
        for profile_field, app_field in field_mapping.items():
            if profile_field in prefill_data and prefill_data[profile_field]:
                if not getattr(personal_info, app_field):
                    setattr(personal_info, app_field, prefill_data[profile_field])
        
        # Always save to ensure consistency (idempotent if no changes)
        personal_info.save()

        # Clone Previous Addresses if they don't exist yet
        if not personal_info.previous_addresses.exists() and 'previous_addresses' in prefill_data:
            for i, addr_data in enumerate(prefill_data['previous_addresses'], 1):
                PreviousAddress.objects.create(
                    personal_info=personal_info,
                    street_address_1=addr_data.get('street_address_1'),
                    street_address_2=addr_data.get('street_address_2'),
                    city=addr_data.get('city'),
                    state=addr_data.get('state'),
                    zip_code=addr_data.get('zip_code'),
                    housing_status=addr_data.get('housing_status'),
                    years=addr_data.get('years', 0),
                    months=addr_data.get('months', 0),
                    monthly_rent=addr_data.get('monthly_rent'),
                    landlord_name=addr_data.get('landlord_name'),
                    landlord_phone=addr_data.get('landlord_phone'),
                    landlord_email=addr_data.get('landlord_email'),
                    order=i
                )
        
        # Clone Pets if they don't exist yet
        if not personal_info.pets.exists() and 'pets' in prefill_data:
            for pet_data in prefill_data['pets']:
                Pet.objects.create(
                    personal_info=personal_info,
                    name=pet_data.get('name'),
                    pet_type=pet_data.get('pet_type'),
                    quantity=pet_data.get('quantity', 1),
                    description=pet_data.get('description'),
                )
                # Note: We're not cloning photos by URL here because it requires re-uploading
                # In a real sync, we might copy Cloudinary assets. For now, we clone the metadata.
    
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
                
                # Handle Previous Addresses
                # Remove existing ones to rebuild (simplest sync strategy for now)
                personal_info.previous_addresses.all().delete()
                
                for i in range(1, 5):  # Max 4 addresses as per frontend logic
                    street1 = request.POST.get(f'prev_street_address_1_{i}')
                    if street1:
                        housing_status = request.POST.get(f'prev_housing_status_{i}', '').lower()
                        PreviousAddress.objects.create(
                            personal_info=personal_info,
                            street_address_1=street1,
                            street_address_2=request.POST.get(f'prev_street_address_2_{i}', ''),
                            city=request.POST.get(f'prev_city_{i}', ''),
                            state=request.POST.get(f'prev_state_{i}', ''),
                            zip_code=request.POST.get(f'prev_zip_code_{i}', ''),
                            years=int(request.POST.get(f'prev_address_years_{i}', 0) or 0),
                            months=int(request.POST.get(f'prev_address_months_{i}', 0) or 0),
                            monthly_rent=request.POST.get(f'prev_monthly_rent_{i}') or None,
                            housing_status=housing_status if housing_status in ['rent', 'own', 'other'] else 'own',
                            landlord_name=request.POST.get(f'prev_landlord_name_{i}', ''),
                            landlord_phone=request.POST.get(f'prev_landlord_phone_{i}', ''),
                            landlord_email=request.POST.get(f'prev_landlord_email_{i}', ''),
                            order=i
                        )
                
                # Handle Pets
                personal_info.pets.all().delete()
                has_pets = request.POST.get('has_pets') == 'on'
                if has_pets:
                    for i in range(1, 6):
                        pet_type = request.POST.get(f'pet_type_{i}')
                        pet_name = request.POST.get(f'pet_name_{i}')
                        if pet_type:
                            pet = Pet.objects.create(
                                personal_info=personal_info,
                                name=pet_name or None,
                                pet_type=pet_type,
                                quantity=1,
                                description=request.POST.get(f'pet_description_{i}') or None
                            )
                            # Handle Pet Photos
                            for photo_num in range(1, 4):
                                photo_field = f'pet_photo_{i}_{photo_num}'
                                crop_data_field = f'crop_data_pet_{i}_{photo_num}'
                                if photo_field in request.FILES:
                                    crop_data = request.POST.get(crop_data_field, '')
                                    image_file = process_cropped_image(crop_data, request.FILES[photo_field])
                                    PetPhoto.objects.create(
                                        pet=pet,
                                        image=image_file
                                    )
                
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
    previous_addresses_qs = PreviousAddress.objects.filter(
        personal_info=personal_info
    ).order_by('order')
    
    previous_addresses_list = []
    for addr in previous_addresses_qs:
        previous_addresses_list.append({
            'street_address_1': addr.street_address_1 or '',
            'street_address_2': addr.street_address_2 or '',
            'city': addr.city or '',
            'state': addr.state or '',
            'zip_code': addr.zip_code or '',
            'years': addr.years or 0,
            'months': addr.months or 0,
            'monthly_rent': str(addr.monthly_rent) if addr.monthly_rent else '',
            'housing_status': addr.housing_status or 'own',
            'landlord_name': addr.landlord_name or '',
            'landlord_phone': addr.landlord_phone or '',
            'landlord_email': addr.landlord_email or '',
        })
    
    # Get Pets data
    pets_list = []
    for pet in personal_info.pets.all():
        pets_list.append({
            'name': pet.name or '',
            'pet_type': pet.pet_type,
            'description': pet.description or '',
            'photos': [photo.image.url for photo in pet.photos.all()]
        })
    
    # Check if this is a preview request
    is_preview = request.GET.get('preview') == 'true'
    
    context = {
        'application': application,
        'form': form,
        'section': section,
        'previous_addresses_data': previous_addresses_list,
        'pets_data': pets_list,
        'current_section': 1,
        'section_title': 'Personal Information',
        'progress_percent': application.get_total_progress(),
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
    
    # Check if this is an authenticated applicant viewing their own application
    if request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        return applicant_application_interface(request, application_id)
    
    # No token and not the applicant - redirect to broker management interface
    return broker_application_management(request, application_id)


def applicant_application_interface(request, application_id):
    """Applicant-focused interface for completing application sections"""
    application = get_object_or_404(Application, id=application_id)
    token = request.GET.get('token')
    
    # Validate access: either valid token OR authenticated as the correct applicant
    is_valid_token = token and token == str(application.unique_link)
    is_authenticated_applicant = request.user.is_authenticated and application.applicant and application.applicant.user == request.user
    
    if not (is_valid_token or is_authenticated_applicant):
        messages.error(request, "You do not have permission to access this application.")
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
        'progress_percent': application.get_total_progress(),
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
    uploaded_files = list(application.uploaded_files.all())
    for f in uploaded_files:
        if f.analysis_results and isinstance(f.analysis_results, str):
            try:
                import json
                f.analysis_results = json.loads(f.analysis_results)
            except json.JSONDecodeError:
                f.analysis_results = {}
    
    # Get application activity log
    activity_log = application.activity_log.all().order_by('-timestamp')[:10]
    
    # Smart Insights Analysis
    insights = {}
    if application.applicant:
        insights = SmartInsights.analyze_applicant(application.applicant)
    
    # Get personal info if available
    personal_info = getattr(application, 'personal_info', None)
    
    # ✅ Income Verification Logic
    income_verification = None
    bank_statement = next((f for f in uploaded_files if f.document_type == 'bank_statement' and f.analysis_results), None)

    if bank_statement and application.applicant and application.applicant.annual_income:
        stated_income = application.applicant.annual_income
        # Try to get extracted income from analysis results (handle various potential keys)
        verified_income = bank_statement.analysis_results.get('extracted_income') or bank_statement.analysis_results.get('annual_income')
        
        if verified_income:
            try:
                # Clean string currency if needed (though it should be a number/decimal from JSON)
                if isinstance(verified_income, str):
                    import re
                    # Remove currency symbols and commas
                    clean_income = re.sub(r'[^\d.]', '', verified_income)
                    verified_income = float(clean_income) if clean_income else 0
                else:
                    verified_income = float(verified_income)
                
                stated_income = float(stated_income)
                
                if stated_income > 0:
                    variance = ((stated_income - verified_income) / stated_income) * 100
                    
                    if variance < 5:
                        status = 'Verified'
                        badge_color = 'success'
                    elif 5 <= variance <= 15:
                        status = 'Review'
                        badge_color = 'warning'
                    else:
                        status = 'Discrepancy'
                        badge_color = 'danger'
                        
                    # Check for fraud/modification
                    if bank_statement.analysis_results.get('tampering_suspected'):
                        status = 'Fraud Alert'
                        badge_color = 'danger'
                        
                    income_verification = {
                        'stated_income': stated_income,
                        'verified_income': verified_income,
                        'variance': round(variance, 1),
                        'status': status,
                        'badge_color': badge_color
                    }
            except (ValueError, TypeError):
                pass  # Handle conversion errors gracefully

    context = {
        'application': application,
        'sections': sections,
        'progress_percent': application.get_total_progress(),
        'completed_sections': completed_sections,
        'total_sections': total_sections,
        'uploaded_files': uploaded_files,
        'activity_log': activity_log,
        'personal_info': personal_info,
        'is_broker_access': True,
        'income_verification': income_verification,
        'insights': insights,
        'current_step': application.current_section,
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
    
    # Validate access: valid token OR authenticated as the correct applicant
    if token and token == str(application.unique_link):
        is_applicant_access = True
    elif request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        is_applicant_access = True
    elif not is_preview:
        # Regular broker/staff access - check authentication
        if not request.user.is_authenticated:
            return redirect('login')
    
    # Get or create IncomeData
    income_data, created = IncomeData.objects.get_or_create(
        application=application,
        defaults={
            'employment_type': 'employed',  # Default choice
            'employer': '',
            'job_title': '',
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
            'employment_type': 'employment_type',
            'employer': 'employer',
            'job_title': 'job_title', 
            'annual_income': 'annual_income',
            'supervisor_name': 'supervisor_name',
            'supervisor_email': 'supervisor_email',
            'supervisor_phone': 'supervisor_phone',
            'currently_employed': 'currently_employed',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'school_name': 'school_name',
            'year_of_graduation': 'year_of_graduation',
            'school_address': 'school_address',
            'school_phone': 'school_phone',
        }
        
        # Mapping photo ID details
        id_field_mapping = {
            'id_type': 'id_type',
            'id_number': 'id_number',
            'id_state': 'id_state',
            'id_front_image': 'id_front_image',
            'id_back_image': 'id_back_image',
        }
        field_mapping.update(id_field_mapping)
        
        # Apply prefill data to income_data instance
        for profile_field, app_field in field_mapping.items():
            if profile_field in prefill_data and prefill_data[profile_field]:
                value = prefill_data[profile_field]
                
                if value:
                    setattr(income_data, app_field, value)
        
        # Save if any data was filled
        if (any(getattr(income_data, field) for field in field_mapping.values() if field)) or created:
            income_data.save()
            
            # Map sub-records from profile to application related models
            from .models import AdditionalEmployment, AdditionalIncome, AssetInfo
            
            # Copy Jobs
            for job in application.applicant.jobs.all():
                AdditionalEmployment.objects.get_or_create(
                    income_data=income_data,
                    company_name=job.company_name,
                    position=job.position,
                    defaults={
                        'annual_income': job.annual_income or 0,
                        'supervisor_name': job.supervisor_name,
                        'supervisor_email': job.supervisor_email,
                        'supervisor_phone': job.supervisor_phone,
                        'currently_employed': job.currently_employed,
                        'start_date': job.employment_start_date,
                        'end_date': job.employment_end_date,
                        'employment_type': job.job_type
                    }
                )
            
            # Copy Income Sources
            for source in application.applicant.income_sources.all():
                AdditionalIncome.objects.get_or_create(
                    income_data=income_data,
                    income_source=source.income_source,
                    defaults={
                        'annual_income': source.average_annual_income or 0,
                        'source_type': source.source_type
                    }
                )
                
            # Copy Assets
            for asset in application.applicant.assets.all():
                AssetInfo.objects.get_or_create(
                    income_data=income_data,
                    asset_name=asset.asset_name,
                    defaults={
                        'account_balance': asset.account_balance or 0,
                        'asset_type': asset.asset_type
                    }
                )
    
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
                
                # Handle dynamic sub-records (additional jobs, income, assets)
                process_app_dynamic_jobs(request, income_data)
                process_app_dynamic_income_sources(request, income_data)
                process_app_dynamic_assets(request, income_data)
                
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
    
    # Get dynamic sub-records for context/pre-fill
    additional_employment = income_data.additional_employment.all()
    additional_income = income_data.additional_income.all()
    assets = income_data.assets.all()
    
    context = {
        'application': application,
        'form': form,
        'section': section,
        'additional_employment': additional_employment,
        'additional_income': additional_income,
        'assets': assets,
        'current_section': 2,
        'section_title': 'Income & Employment',
        'progress_percent': application.get_total_progress(),
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


def process_app_dynamic_jobs(request, income_data):
    """Process additional jobs for an application Section 2"""
    from .models import AdditionalEmployment
    # Clear existing to avoid duplicates on re-save
    income_data.additional_employment.all().delete()
    
    # Same naming convention as Step 3 for "Exact Mirror"
    for key, value in request.POST.items():
        if (key.startswith('job_company_') or key.startswith('employed_job_company_')) and value.strip():
            prefix = 'job_company_' if key.startswith('job_company_') else 'employed_job_company_'
            index = key.replace(prefix, '')
            
            p = 'job_' if prefix == 'job_company_' else 'employed_job_'
            
            company = request.POST.get(f'{p}company_{index}', '').strip()
            position = request.POST.get(f'{p}position_{index}', '').strip()
            income = request.POST.get(f'{p}income_{index}', '')
            supervisor = request.POST.get(f'{p}supervisor_{index}', '').strip()
            supervisor_email = request.POST.get(f'{p}supervisor_email_{index}', '').strip()
            supervisor_phone = request.POST.get(f'{p}supervisor_phone_{index}', '').strip()
            currently_employed = request.POST.get(f'{p}current_{index}') == 'on'
            start_date = request.POST.get(f'{p}start_{index}', '')
            end_date = request.POST.get(f'{p}end_{index}', '')
            
            if company and position:
                AdditionalEmployment.objects.create(
                    income_data=income_data,
                    company_name=company,
                    position=position,
                    annual_income=float(income) if income else 0,
                    supervisor_name=supervisor,
                    supervisor_email=supervisor_email,
                    supervisor_phone=supervisor_phone,
                    currently_employed=currently_employed,
                    start_date=start_date or None,
                    end_date=end_date if not currently_employed and end_date else None,
                    employment_type='student' if prefix == 'job_company_' else 'employed'
                )

def process_app_dynamic_income_sources(request, income_data):
    """Process additional income sources for an application Section 2"""
    from .models import AdditionalIncome
    income_data.additional_income.all().delete()
    
    prefixes = ['income_source_', 'employed_income_source_', 'other_income_source_']
    for pref in prefixes:
        for key, value in request.POST.items():
            if key.startswith(pref) and value.strip():
                index = key.replace(pref, '')
                
                # Determine amount field prefix
                amt_pref = pref.replace('source_', 'amount_')
                
                source = request.POST.get(f'{pref}{index}', '').strip()
                amount = request.POST.get(f'{amt_pref}{index}', '')
                
                source_type = 'other'
                if 'student' in pref or pref == 'income_source_': source_type = 'student'
                if 'employed' in pref: source_type = 'employed'
                
                if source and amount:
                    AdditionalIncome.objects.create(
                        income_data=income_data,
                        income_source=source,
                        annual_income=float(amount),
                        source_type=source_type
                    )

def process_app_dynamic_assets(request, income_data):
    """Process assets for an application Section 2"""
    from .models import AssetInfo
    income_data.assets.all().delete()
    
    prefixes = ['asset_name_', 'employed_asset_name_', 'other_asset_name_']
    for pref in prefixes:
        for key, value in request.POST.items():
            if key.startswith(pref) and value.strip():
                index = key.replace(pref, '')
                
                bal_pref = pref.replace('name_', 'balance_')
                
                name = request.POST.get(f'{pref}{index}', '').strip()
                balance = request.POST.get(f'{bal_pref}{index}', '')
                
                asset_type = 'other'
                if 'student' in pref or pref == 'asset_name_': asset_type = 'student'
                if 'employed' in pref: asset_type = 'employed'
                
                if name and balance:
                    AssetInfo.objects.create(
                        income_data=income_data,
                        asset_name=name,
                        account_balance=float(balance),
                        asset_type=asset_type
                    )


@hybrid_csrf_protect
def v2_section3_legal(request, application_id):
    """Section 3 - Legal Documents with E-signatures"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check access
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    if token and token == str(application.unique_link):
        is_applicant_access = True
    elif request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        is_applicant_access = True
    elif not is_preview:
        if not request.user.is_authenticated:
            return redirect('login')

    # Get or create LegalDocuments record
    legal_docs, created = LegalDocuments.objects.get_or_create(
        application=application
    )
    
    # Get application section
    section, _ = ApplicationSection.objects.get_or_create(
        application=application,
        section_number=3,
        defaults={'status': SectionStatus.IN_PROGRESS}
    )
    
    if request.method == 'POST':
        # Check if they want to save and continue
        if 'save_continue' in request.POST:
            # All required signatures must be present to complete the section
            # For now, we require both NY Discrimination and NY Brokers forms
            if legal_docs.discrimination_form_signed and legal_docs.brokers_form_signed:
                with transaction.atomic():
                    section.status = SectionStatus.COMPLETED
                    section.completed_at = timezone.now()
                    section.save()
                    
                    application.section_statuses[3] = SectionStatus.COMPLETED
                    application.current_section = 4
                    application.section_statuses[4] = SectionStatus.IN_PROGRESS
                    application.save()
                    
                    # Update next section
                    next_section, _ = ApplicationSection.objects.get_or_create(
                        application=application,
                        section_number=4,
                        defaults={'status': SectionStatus.IN_PROGRESS, 'started_at': timezone.now()}
                    )
                    next_section.status = SectionStatus.IN_PROGRESS
                    next_section.started_at = timezone.now()
                    next_section.save()
                    
                    log_activity(application, "Section 3 (Legal) completed")
                    messages.success(request, "Legal documents signed successfully!")
                    
                    if is_applicant_access:
                        return redirect(f"{reverse('v2_section4_review', args=[application.id])}?token={token}")
                    else:
                        return redirect('v2_section4_review', application_id=application.id)
            else:
                messages.error(request, "Please sign all required documents before continuing.")
        
        elif 'save_exit' in request.POST:
            if is_applicant_access:
                return redirect(f"{reverse('v2_application_overview', args=[application.id])}?token={token}")
            else:
                return redirect('application_detail', application_id=application.id)

    # Intro text for Section 3
    intro_text = "The following forms are for the property you are applying for. Please review each form and sign at the bottom where indicated."
    
    context = {
        'application': application,
        'legal_docs': legal_docs,
        'section': section,
        'current_section': 3,
        'section_title': 'Legal',
        'intro_text': intro_text,
        'progress_percent': application.get_total_progress(),
        'is_preview': is_preview,
        'token': token,
        'is_applicant_access': is_applicant_access,
    }
    
    if is_applicant_access:
        template = 'applications/v2/applicant_section3_legal.html'
    else:
        template = 'applications/v2/section3_legal.html'
    
    return render(request, template, context)


@hybrid_csrf_protect
@require_http_methods(["POST"])
def v2_sign_document(request, application_id):
    """AJAX endpoint to record an e-signature"""
    application = get_object_or_404(Application, id=application_id)
    legal_docs = get_object_or_404(LegalDocuments, application=application)
    
    doc_type = request.POST.get('doc_type')
    signature_name = request.POST.get('signature')
    
    if not doc_type or not signature_name:
        return JsonResponse({'success': False, 'error': 'Missing document type or signature name'}, status=400)
    
    # Get client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
        
    if doc_type == 'NY_DISCRIMINATION':
        legal_docs.discrimination_form_signed = True
        legal_docs.discrimination_form_signature = signature_name
        legal_docs.discrimination_form_signed_at = timezone.now()
        legal_docs.discrimination_form_ip = ip
        legal_docs.save()
        
    elif doc_type == 'NY_BROKERS':
        legal_docs.brokers_form_signed = True
        legal_docs.brokers_form_signature = signature_name
        legal_docs.brokers_form_signed_at = timezone.now()
        legal_docs.brokers_form_ip = ip
        legal_docs.save()
    else:
        return JsonResponse({'success': False, 'error': 'Invalid document type'}, status=400)
        
    log_activity(application, f"Document signed: {doc_type} by {signature_name}")
    
    return JsonResponse({
        'success': True,
        'signed_at': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip': ip
    })


@hybrid_csrf_protect
def v2_section4_review(request, application_id):
    """Section 4 - Review all application data before payment"""
    application = get_object_or_404(Application, id=application_id)
    
    # Check if this is token-based access (for applicants via UUID link)
    token = request.GET.get('token')
    is_applicant_access = False
    is_preview = request.GET.get('preview') == 'true'
    
    # Validate access: valid token OR authenticated as the correct applicant
    if token and token == str(application.unique_link):
        is_applicant_access = True
    elif request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        is_applicant_access = True
    elif not is_preview:
        # Regular broker/staff access - check authentication
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
    
    # Validate access: valid token OR authenticated as the correct applicant
    if token and token == str(application.unique_link):
        is_applicant_access = True
    elif request.user.is_authenticated and application.applicant and application.applicant.user == request.user:
        is_applicant_access = True
    else:
        # Regular broker/staff access - check authentication
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
        'progress_percent': application.get_total_progress(),
        'application_fee': application.application_fee_amount,
        'SOLA_SANDBOX_MODE': getattr(settings, 'SOLA_SANDBOX_MODE', True),
    }
    
    # Use different templates based on access type
    if is_applicant_access:
        template = 'applications/v2/applicant_section5_payment.html'
    else:
        template = 'applications/v2/section5_payment.html'
    
    return render(request, template, context)


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
