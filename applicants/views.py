from django.shortcuts import render, get_object_or_404, redirect
from .models import Applicant, ApplicantPhoto, PetPhoto, ApplicantCRM, ApplicationHistory, InteractionLog, SavedApartment
from .forms import ApplicantForm, ApplicantPhotoForm, PetForm, PetPhotoForm
from applications.models import Application
from apartments.models import Apartment, ApartmentAmenity
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q

from .forms import InteractionLogForm
from django.utils.timezone import now
from applicants.models import Applicant, Amenity, Neighborhood
from applications.nudge_service import NudgeService

import random

# Permission Helper
def user_is_broker_or_admin(user):
    return user.is_authenticated and (
        user.is_superuser or 
        user.is_staff or 
        getattr(user, 'is_broker', False) or 
        getattr(user, 'is_owner', False)
    )

@login_required
@user_passes_test(user_is_broker_or_admin)
def delete_applicant_photo(request, photo_id):
    photo = get_object_or_404(ApplicantPhoto, id=photo_id)
    # Security check: Ensure user has access to this applicant
    applicant = photo.applicant
    if not (request.user.is_superuser or request.user.is_staff or 
            applicant.assigned_broker == request.user or 
            applicant.applications.filter(building__brokers=request.user).exists()):
         messages.error(request, "You do not have permission to modify this applicant.")
         return redirect('applicant_overview', applicant_id=applicant.id)

    applicant_id = photo.applicant.id
    photo.delete()
    messages.success(request, "Applicant photo deleted successfully!")
    return redirect('applicant_overview', applicant_id=applicant_id)


@login_required
@user_passes_test(user_is_broker_or_admin)
def delete_pet_photo(request, photo_id):
    photo = get_object_or_404(PetPhoto, id=photo_id)
    # Security check
    applicant = photo.pet.applicant
    if not (request.user.is_superuser or request.user.is_staff or 
            applicant.assigned_broker == request.user or 
            applicant.applications.filter(building__brokers=request.user).exists()):
         messages.error(request, "You do not have permission to modify this applicant.")
         return redirect('applicant_overview', applicant_id=applicant.id)

    applicant_id = photo.pet.applicant.id
    photo.delete()
    messages.success(request, "Pet photo deleted successfully!")
    return redirect('applicant_overview', applicant_id=applicant_id)


@login_required
@user_passes_test(user_is_broker_or_admin)
def applicant_overview(request, applicant_id):
    applicant = get_object_or_404(Applicant, id=applicant_id)

    # Permission Check: Broker can only view assigned or relevant applicants
    if not (request.user.is_superuser or request.user.is_staff):
        has_access = (
            applicant.assigned_broker == request.user or
            applicant.applications.filter(building__brokers=request.user).exists()
        )
        if not has_access:
            messages.error(request, "You do not have permission to view this applicant.")
            return redirect('applicants_list')

    # Get the first submitted application (if it exists)
    application = applicant.applications.filter(submitted_by_applicant=True).first()
    
    # Get matching apartments using the apartment matching service
    matching_apartments = []
    try:
        from applicants.apartment_matching import ApartmentMatchingService
        matching_service = ApartmentMatchingService(applicant)
        matching_apartments = matching_service.get_apartment_matches(limit=10)
    except Exception as e:
        # Log error but don't break the page
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error finding matching apartments for applicant {applicant_id}: {str(e)}")

    # Restrict AI insights to business users only (redundant with decorator but good for safety)
    smart_insights = None
    try:
        from applicants.smart_insights import SmartInsights
        smart_insights = SmartInsights.analyze_applicant(applicant)
    except Exception as e:
        # Log error but don't break the page
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating smart insights for applicant {applicant_id}: {str(e)}")

    return render(request, 'applicants/applicant_overview.html', {
        'applicant': applicant,
        'application': application,
        'matching_apartments': matching_apartments,
        'smart_insights': smart_insights,
    })


@login_required
@user_passes_test(user_is_broker_or_admin)
def applicants_list(request):
    # Optimize queries for list display
    base_qs = Applicant.objects.select_related(
        'user',
    ).prefetch_related(
        'neighborhood_preferences',
        'applications',
    )
    
    # Filter based on permissions
    if request.user.is_superuser or request.user.is_staff:
        applicants = base_qs.all()
    else:
        # Brokers see assigned applicants OR applicants who applied to their buildings
        applicants = base_qs.filter(
            Q(assigned_broker=request.user) |
            Q(applications__apartment__building__brokers=request.user)
        ).distinct()
    
    # Initialize CRM records for workflow
    for applicant in applicants:
        crm, created = ApplicantCRM.objects.get_or_create(applicant=applicant)
        applicant.crm = crm

    context = {
        "applicants": applicants
    }
    return render(request, "applicants/applicants_list.html", context)


def get_applicant_data(request, applicant_id):
    # API endpoint for applicant data export
    if not request.user.is_authenticated:
         return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        applicant = Applicant.objects.get(id=applicant_id)
        
        # Permission check
        if not (request.user.is_superuser or request.user.is_staff or request.user == applicant.user or 
                applicant.assigned_broker == request.user or 
                applicant.applications.filter(building__brokers=request.user).exists()):
             return JsonResponse({"error": "Permission denied"}, status=403)

        # Get field completion status
        completion_status = applicant.get_field_completion_status()
        
        # Basic data structure for backward compatibility
        basic_data = {
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "date_of_birth": applicant.date_of_birth.strftime("%Y-%m-%d") if applicant.date_of_birth else "",
            "phone_number": applicant.phone_number,
            "email": applicant.email,
            "street_address_1": applicant.street_address_1,
            "street_address_2": applicant.street_address_2,
            "city": applicant.city,
            "state": applicant.state,
            "zip_code": applicant.zip_code,
            "length_at_current_address": applicant.length_at_current_address,
            "housing_status": applicant.housing_status,
            "current_landlord_name": applicant.current_landlord_name,
            "current_landlord_phone": applicant.current_landlord_phone,
            "current_landlord_email": applicant.current_landlord_email,
            "reason_for_moving": applicant.reason_for_moving,
            "monthly_rent": str(applicant.monthly_rent) if applicant.monthly_rent else "",
            "driver_license_number": applicant.driver_license_number,
            "driver_license_state": applicant.driver_license_state,
            # Updated employment fields
            "employment_status": applicant.employment_status,
            "company_name": applicant.company_name,
            "position": applicant.position,
            "annual_income": str(applicant.annual_income) if applicant.annual_income else "",
            "supervisor_name": applicant.supervisor_name,
            "supervisor_email": applicant.supervisor_email,
            "supervisor_phone": applicant.supervisor_phone,
            "currently_employed": applicant.currently_employed,
            "employment_start_date": applicant.employment_start_date.strftime("%Y-%m-%d") if applicant.employment_start_date else "",
            "employment_end_date": applicant.employment_end_date.strftime("%Y-%m-%d") if applicant.employment_end_date else "",
            # Student fields
            "school_name": applicant.school_name,
            "year_of_graduation": applicant.year_of_graduation,
            "school_address": applicant.school_address,
            "school_phone": applicant.school_phone,
            # Housing preferences
            "desired_move_in_date": applicant.desired_move_in_date.strftime("%Y-%m-%d") if applicant.desired_move_in_date else "",
            "min_bedrooms": applicant.min_bedrooms,
            "max_bedrooms": applicant.max_bedrooms,
            "min_bathrooms": applicant.min_bathrooms,
            "max_bathrooms": applicant.max_bathrooms,
            "max_rent_budget": str(applicant.max_rent_budget) if applicant.max_rent_budget else "",
            "open_to_roommates": applicant.open_to_roommates,
            # Emergency contact
            "emergency_contact_name": applicant.emergency_contact_name,
            "emergency_contact_relationship": applicant.emergency_contact_relationship,
            "emergency_contact_phone": applicant.emergency_contact_phone,
            # Rental history
            "previous_landlord_name": applicant.previous_landlord_name,
            "previous_landlord_contact": applicant.previous_landlord_contact,
            "evicted_before": applicant.evicted_before,
            "eviction_explanation": applicant.eviction_explanation,
            # Placement status
            "placement_status": applicant.placement_status,
            "placement_date": applicant.placement_date.strftime("%Y-%m-%d %H:%M:%S") if applicant.placement_date else "",
        }
        
        # Get related model data
        related_data = {
            "jobs": [
                {
                    "id": job.id,
                    "company_name": job.company_name,
                    "position": job.position,
                    "annual_income": str(job.annual_income) if job.annual_income else "",
                    "supervisor_name": job.supervisor_name,
                    "supervisor_email": job.supervisor_email,
                    "supervisor_phone": job.supervisor_phone,
                    "currently_employed": job.currently_employed,
                    "employment_start_date": job.employment_start_date.strftime("%Y-%m-%d") if job.employment_start_date else "",
                    "employment_end_date": job.employment_end_date.strftime("%Y-%m-%d") if job.employment_end_date else "",
                    "job_type": job.job_type,
                }
                for job in applicant.jobs.all()
            ],
            "income_sources": [
                {
                    "id": source.id,
                    "income_source": source.income_source,
                    "average_annual_income": str(source.average_annual_income),
                    "source_type": source.source_type,
                }
                for source in applicant.income_sources.all()
            ],
            "assets": [
                {
                    "id": asset.id,
                    "asset_name": asset.asset_name,
                    "account_balance": str(asset.account_balance),
                    "asset_type": asset.asset_type,
                }
                for asset in applicant.assets.all()
            ],
            "pets": [
                {
                    "id": pet.id,
                    "name": pet.name,
                    "pet_type": pet.pet_type,
                    "quantity": pet.quantity,
                    "description": pet.description,
                    "photos_count": pet.photos.count(),
                }
                for pet in applicant.pets.all()
            ],
            "previous_addresses": [
                {
                    "id": addr.id,
                    "order": addr.order,
                    "street_address_1": addr.street_address_1,
                    "street_address_2": addr.street_address_2,
                    "city": addr.city,
                    "state": addr.state,
                    "zip_code": addr.zip_code,
                    "length_at_address": addr.length_at_address,
                    "housing_status": addr.housing_status,
                    "landlord_name": addr.landlord_name,
                    "landlord_phone": addr.landlord_phone,
                    "landlord_email": addr.landlord_email,
                }
                for addr in applicant.previous_addresses.all()
            ],
            "photos_count": applicant.photos.count(),
            "amenities_count": applicant.amenities.count(),
            "neighborhood_preferences_count": applicant.neighborhood_preferences.count(),
        }
        
        # Comprehensive response
        response_data = {
            "applicant_id": applicant.id,
            "basic_data": basic_data,
            "related_data": related_data,
            "field_completion": completion_status,
            "metadata": {
                "created_at": applicant.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": applicant.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                "assigned_broker": applicant.assigned_broker.username if applicant.assigned_broker else None,
            }
        }
        
        return JsonResponse(response_data)
    except Applicant.DoesNotExist:
        return JsonResponse({"error": "Applicant not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)


@login_required
@user_passes_test(user_is_broker_or_admin)
def applicant_crm(request, applicant_id):
    # Broker communication and activity hub
    applicant = get_object_or_404(Applicant, id=applicant_id)
    
    # Permission Check
    if not (request.user.is_superuser or request.user.is_staff):
        has_access = (
            applicant.assigned_broker == request.user or
            applicant.applications.filter(building__brokers=request.user).exists()
        )
        if not has_access:
            messages.error(request, "You do not have permission to view this applicant's CRM.")
            return redirect('applicants_list')

    crm, created = ApplicantCRM.objects.get_or_create(applicant=applicant)
    history = crm.history.all()
    logs = crm.logs.all().order_by('-created_at')
    
    # Get comprehensive activity feed
    from .activity_tracker import ActivityTracker
    recent_activities = ActivityTracker.get_recent_activities(applicant, limit=50)
    activity_summary = ActivityTracker.get_activity_summary(applicant, days=30)
    
    # Calculate Engagement Score (Simple heuristic)
    # 0-100 score based on activity count
    activity_count = activity_summary.get('total_activities', 0)
    engagement_score = min(100, activity_count * 2) # 50 activities = 100%

    if request.method == "POST":
        if "contact_method" in request.POST:
            # Track outbound communications via NudgeService
            contact_method = request.POST.get("contact_method")
            message = request.POST.get("message", "")

            success, error_msg = NudgeService.send_nudge(
                target=applicant,
                user=request.user,
                nudge_type=contact_method,
                custom_message=message
            )

            if success:
                messages.success(request, f"{contact_method.upper()} sent successfully!")
            else:
                messages.error(request, f"Failed to send {contact_method}: {error_msg}")

            return redirect('applicant_crm', applicant_id=applicant.id)

        else:
            # Standard note logging
            log_form = InteractionLogForm(request.POST, request.FILES)
            if log_form.is_valid():
                new_log = log_form.save(commit=False)
                new_log.broker = request.user if request.user.is_authenticated else None
                new_log.crm = crm
                new_log.save()
                messages.success(request, "Note added successfully.")
                return redirect('applicant_crm', applicant_id=applicant.id)
    else:
        log_form = InteractionLogForm()
    
    # Get Quick Actions
    quick_actions = NudgeService.get_quick_actions(applicant)

    # Get Inquiries & Outreach History
    # Use select_related to optimize query
    inquiries = []
    if applicant.user:
        from apartments.models import BrokerInquiry
        inquiries = BrokerInquiry.objects.filter(applicant=applicant.user).select_related('apartment', 'apartment__building').order_by('-created_at')

    return render(request, 'applicants/applicant_crm.html', {
        'applicant': applicant,
        'crm': crm,
        'history': history,
        'logs': logs,
        'log_form': log_form,
        'recent_activities': recent_activities,
        'activity_summary': activity_summary,
        'quick_actions': quick_actions,
        'engagement_score': engagement_score,
        'inquiries': inquiries,
    })

from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def toggle_saved_apartment(request):
    """
    Toggle the saved status of an apartment for the logged-in applicant.
    Expects JSON payload: {"apartment_id": <int>}
    """
    try:
        data = json.loads(request.body)
        apartment_id = data.get('apartment_id')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not apartment_id:
        return JsonResponse({'error': 'Apartment ID is required'}, status=400)

    # Ensure user is an applicant
    if not getattr(request.user, 'is_applicant', False):
        return JsonResponse({'error': 'Only applicants can save apartments'}, status=403)

    try:
        # Try to get linked applicant profile
        applicant = Applicant.objects.get(user=request.user)
    except Applicant.DoesNotExist:
        # Fallback for legacy users where link might be missing but email matches
        try:
            applicant = Applicant.objects.get(email=request.user.email)
            # Auto-link if found
            if not applicant.user:
                applicant.user = request.user
                applicant.save()
        except Applicant.DoesNotExist:
            return JsonResponse({'error': 'Applicant profile not found'}, status=404)

    apartment = get_object_or_404(Apartment, id=apartment_id)

    # Toggle Logic
    saved_obj, created = SavedApartment.objects.get_or_create(applicant=applicant, apartment=apartment)

    if not created:
        # If it already existed, delete it (Unsave)
        saved_obj.delete()
        is_saved = False
        message = "Apartment removed from saved list"
        
        # Log activity
        from .models import ApplicantActivity
        ApplicantActivity.objects.create(
            applicant=applicant,
            activity_type='apartment_unfavorited',
            description=f"Unfavorited apartment {apartment.unit_number} at {apartment.building.name}"
        )
    else:
        # If created, it's now saved
        is_saved = True
        message = "Apartment saved successfully"
        
        # Log activity
        from .models import ApplicantActivity
        ApplicantActivity.objects.create(
            applicant=applicant,
            activity_type='apartment_favorited',
            description=f"Favorited apartment {apartment.unit_number} at {apartment.building.name}"
        )

    return JsonResponse({
        'success': True,
        'is_saved': is_saved,
        'message': message,
        'apartment_id': apartment.id
    })
