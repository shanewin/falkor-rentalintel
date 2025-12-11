from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from .models import Apartment, ApartmentImage
from buildings.models import Building, Amenity
from applicants.models import Neighborhood
from .forms import (
    ApartmentForm, ApartmentImageForm, ApartmentBasicForm, 
    ApartmentAmenitiesForm, ApartmentDetailsForm, BrokerContactForm
)
from django.http import JsonResponse
from datetime import datetime, date, timedelta
import logging
from . import services

logger = logging.getLogger(__name__)

def apartments_list(request):
    """
    Main apartment search and listing view.
    Refactored to use services for filtering logic.
    """
    # Use service to get filtered apartments
    apartments, filters, auto_applied_preferences = services.get_filtered_apartments(request, request.user)
    
    # Business Feature: Smart Matching Algorithm
    smart_matches = []
    is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.user.is_authenticated and hasattr(request.user, 'applicant_profile') and not is_ajax_request:
        try:
            from applicants.apartment_matching import get_apartment_matches_for_applicant
            applicant = request.user.applicant_profile
            smart_matches = get_apartment_matches_for_applicant(applicant, limit=6)  # Show top 6 matches
        except ImportError as e:
            logger.warning(f"Smart matching module not available: {e}")
            smart_matches = []
        except Exception as e:
            logger.error(f"Error getting smart matches: {e}")
            smart_matches = []

    # Handle AJAX requests for filtering
    if is_ajax_request:
        try:
            apartments_data = services.serialize_apartments_for_map(apartments)
            
            return JsonResponse({
                'apartments': apartments_data,
                'total_results': apartments.count(),
                'active_filters': filters,
                'sort_by': request.GET.get('sort'),
                'selected_neighborhoods': request.GET.getlist('neighborhoods'),
                'selected_amenities': request.GET.getlist('amenities'),
                'pets_allowed_checked': request.GET.get('pets_allowed') == '1'
            })
        except Exception as e:
            logger.error(f"Error in AJAX apartment filtering: {e}")
            return JsonResponse({
                'error': 'An error occurred while filtering apartments',
                'apartments': [],
                'total_results': 0,
                'active_filters': {}
            }, status=500)
    
    # Context setup
    all_amenities = Amenity.objects.all().order_by('name')
    neighborhood_choices = [choice for choice in Building.NEIGHBORHOOD_CHOICES if choice[0]]
    neighborhood_values = request.GET.getlist('neighborhoods')
    amenity_ids = request.GET.getlist('amenities')
    sort_by = request.GET.get('sort')

    context = {
        'sort_by': sort_by,
        'apartments': apartments,
        'all_amenities': all_amenities,
        'neighborhood_choices': neighborhood_choices,
        'active_filters': filters,
        'total_results': apartments.count(),
        'auto_applied_preferences': auto_applied_preferences,
        'smart_matches': smart_matches,
        'mapbox_token': getattr(settings, 'MAPBOX_API_TOKEN', ''),
        'selected_neighborhoods': neighborhood_values,
        'selected_amenities': amenity_ids,
        'pets_allowed_checked': request.GET.get('pets_allowed') == '1',
        # Pre-calculated values for JS to avoid template syntax errors
        'selected_neighborhoods_count': len(neighborhood_values) if neighborhood_values else 0,
        'selected_amenities_count': len(amenity_ids) if amenity_ids else 0,
        'pets_allowed_int': 1 if request.GET.get('pets_allowed') == '1' else 0,
        # Sort booleans to avoid template operator spacing issues
        'is_sort_relevant': sort_by == 'relevant',
        'is_sort_price_asc': sort_by == 'price_asc',
        'is_sort_price_desc': sort_by == 'price_desc',
        'is_sort_newest': sort_by == 'newest',
    }
    
    return render(request, 'apartments/apartments_list.html', context)


def apartment_edit(request, apartment_id=None, building_id=None):
    """
    Apartment editing interface.
    Renamed from 'apartment_detail' to better reflect purpose.
    """
    apartment = None
    building = None

    if apartment_id:
        apartment = get_object_or_404(Apartment, id=apartment_id)
        building = apartment.building
    elif building_id:
        building = get_object_or_404(Building, id=building_id)

    if request.method == 'POST':
        if 'apartment_submit' in request.POST:
            apartment_form = ApartmentForm(request.POST, instance=apartment)
            if apartment_form.is_valid():
                apartment = apartment_form.save()
                messages.success(request, 'Apartment details saved successfully.')
                return redirect('apartment_edit', apartment_id=apartment.id)

        elif 'image_submit' in request.POST and apartment:
            image_form = ApartmentImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.apartment = apartment
                image.save()
                messages.success(request, 'Image uploaded successfully.')
                return redirect('apartment_edit', apartment_id=apartment.id)

    else:
        apartment_form = ApartmentForm(instance=apartment, initial={'building': building})
        image_form = ApartmentImageForm()

    return render(request, 'apartments/apartment_detail.html', {
        'apartment': apartment,
        'apartment_form': apartment_form,
        'image_form': image_form,
        'building': building,
    })


def apartment_overview(request, apartment_id):
    """
    Public-facing apartment details page for prospective tenants.
    """
    apartment = get_object_or_404(
        Apartment.objects.select_related('building')
        .prefetch_related('building__brokers__broker_profile'),
        id=apartment_id
    )
    
    
    # Track apartment view activity for applicants
    if request.user.is_authenticated and hasattr(request.user, 'applicant_profile'):
        try:
            from applicants.activity_tracker import ActivityTracker
            ActivityTracker.track_apartment_view(
                applicant=request.user.applicant_profile,
                apartment=apartment,
                request=request
            )
        except Exception as e:
            logger.error(f"Failed to track apartment view: {e}")
    
    return render(request, 'apartments/apartment_overview.html', {'apartment': apartment})


def get_apartment_data(request, apartment_id):
    """
    AJAX endpoint for fetching apartment pricing details.
    """
    try:
        apartment = Apartment.objects.get(id=apartment_id)
        data = {
            "rent_price": str(apartment.rent_price),
            "bedrooms": str(apartment.bedrooms),
            "bathrooms": str(apartment.bathrooms),
        }
        return JsonResponse(data)
    except Apartment.DoesNotExist:
        return JsonResponse({"error": "Apartment not found"}, status=404)


# Multi-step apartment creation workflow
def create_apartment_v2(request, building_id=None):
    """
    Step 1: Basic Apartment Information
    """
    building = None
    if building_id:
        building = get_object_or_404(Building, id=building_id)

    basic_form = ApartmentBasicForm(request.POST or None, initial={'building': building})

    if request.method == 'POST' and 'apartment_submit' in request.POST:
        if basic_form.is_valid():
            apartment = basic_form.save()
            messages.success(request, f'Apartment {apartment.unit_number} created successfully! Now let\'s add images.')
            return redirect('apartment_step2', apartment_id=apartment.id)
        else:
            messages.error(request, "Please correct the errors below and try again.")
    
    # Context variable 'sort_by' was removed as it was undefined here.
    # If needed by template, it should be defined or removed from template.

    context = {
        'basic_form': basic_form,
        'building': building,
        'current_step': 1,
        'step_title': 'Step 1: Basic Information'
    }
    
    return render(request, 'apartments/apartment_step1.html', context)


def apartment_step2(request, apartment_id):
    """
    Step 2: Images Upload
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    image_form = ApartmentImageForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if 'image_submit' in request.POST:
            if image_form.is_valid():
                try:
                    image = image_form.save(commit=False)
                    image.apartment = apartment
                    image.save()
                    messages.success(request, 'Image uploaded successfully.')
                    return redirect('apartment_step2', apartment_id=apartment.id)
                except Exception as e:
                    logger.error(f"Failed to upload image for apartment {apartment.id}: {e}")
                    messages.error(request, "Failed to upload image. Please try again.")
            else:
                messages.error(request, "Invalid image file. Please select a valid image.")
        
        elif 'skip_images' in request.POST:
            messages.info(request, "Skipped image upload. You can add images later.")
            return redirect('apartment_step3', apartment_id=apartment.id)
        
        elif 'next_step' in request.POST:
            return redirect('apartment_step3', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'image_form': image_form,
        'current_step': 2,
        'step_title': 'Step 2: Images'
    }
    
    return render(request, 'apartments/apartment_step2.html', context)


def apartment_step3(request, apartment_id):
    """
    Step 3: Amenities and Features
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    amenities_form = ApartmentAmenitiesForm(request.POST or None, instance=apartment)

    if request.method == 'POST':
        if 'amenities_submit' in request.POST:
            if amenities_form.is_valid():
                try:
                    amenities_form.save()
                    messages.success(request, 'Amenities and features saved successfully.')
                    return redirect('apartment_step4', apartment_id=apartment.id)
                except Exception as e:
                    logger.error(f"Failed to save amenities for apartment {apartment.id}: {e}")
                    messages.error(request, "Failed to save amenities. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_amenities' in request.POST:
            messages.info(request, "Skipped amenities. You can add these later.")
            return redirect('apartment_step4', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'amenities_form': amenities_form,
        'current_step': 3,
        'step_title': 'Step 3: Amenities & Features'
    }
    
    return render(request, 'apartments/apartment_step3.html', context)


def apartment_step4(request, apartment_id):
    """
    Step 4: Additional Details & Completion
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    details_form = ApartmentDetailsForm(request.POST or None, instance=apartment)

    if request.method == 'POST':
        if 'details_submit' in request.POST:
            if details_form.is_valid():
                try:
                    details_form.save()
                    messages.success(request, 'Additional details saved successfully.')
                    return redirect('apartment_complete', apartment_id=apartment.id)
                except Exception as e:
                    logger.error(f"Failed to save details for apartment {apartment.id}: {e}")
                    messages.error(request, "Failed to save details. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_details' in request.POST:
            messages.info(request, "Skipped additional details. You can add these later.")
            return redirect('apartment_complete', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'details_form': details_form,
        'current_step': 4,
        'step_title': 'Step 4: Additional Details'
    }
    
    return render(request, 'apartments/apartment_step4.html', context)


def apartment_complete(request, apartment_id):
    """
    Apartment Creation Complete - Success confirmation page
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    context = {
        'apartment': apartment,
        'current_step': 5,
        'step_title': 'Apartment Setup Complete!'
    }
    
    return render(request, 'apartments/apartment_complete.html', context)


def contact_broker(request, apartment_id):
    """
    Handle broker contact form submission.
    Refactored to use BrokerContactForm and services.
    """
    apartment = get_object_or_404(Apartment, id=apartment_id)
    
    if request.method == 'POST':
        form = BrokerContactForm(request.POST)
        if form.is_valid():
            try:
                success = services.handle_broker_contact(apartment, form.cleaned_data)
                
                if success:
                    messages.success(request, 'Your message has been sent to the broker. You should hear back within 24 hours!')
                else:
                    messages.warning(request, 'Message sent, but no broker contact information is available for this property.')
                
            except Exception as e:
                logger.error(f"Failed to send broker contact message for apartment {apartment_id}: {e}")
                messages.error(request, 'There was an error sending your message. Please try again.')
        else:
            # If form is invalid, show errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    
    return redirect('apartment_overview', apartment_id=apartment_id)
