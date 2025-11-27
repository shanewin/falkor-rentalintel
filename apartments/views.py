from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from .models import Apartment, ApartmentImage
from buildings.models import Building, Amenity
from applicants.models import Neighborhood
from .forms import ApartmentForm, ApartmentImageForm, ApartmentBasicForm, ApartmentAmenitiesForm, ApartmentDetailsForm
from django.http import JsonResponse
from datetime import datetime, date, timedelta
import logging

logger = logging.getLogger(__name__)



def apartments_list(request):
    """
    Main apartment search and listing view
    Business Features:
    1. Auto-applies user's saved preferences as filters (improves conversion)
    2. Smart matching algorithm shows personalized recommendations
    3. AJAX filtering for seamless user experience
    """
    # Start with all apartments - optimized query with related data
    apartments = Apartment.objects.all().select_related('building').prefetch_related('images', 'building__amenities')
    
    # Business Logic: Auto-populate filters from applicant preferences
    # Impact: Saves time for returning users, increases engagement
    # Only apply on initial page load (not AJAX requests)
    auto_applied_preferences = False
    is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.user.is_authenticated and not request.GET and hasattr(request.user, 'applicant_profile') and not is_ajax_request:
        try:
            applicant = request.user.applicant_profile
            # Create a mutable copy of GET parameters
            get_params = request.GET.copy()
            
            # Apply applicant's housing preferences as default filters
            if applicant.max_rent_budget:
                get_params['max_price'] = str(int(applicant.max_rent_budget))
            
            if applicant.min_bedrooms:
                get_params['min_bedrooms'] = str(applicant.min_bedrooms)
            if applicant.max_bedrooms:
                get_params['max_bedrooms'] = str(applicant.max_bedrooms)
                
            if applicant.min_bathrooms:
                get_params['min_bathrooms'] = str(applicant.min_bathrooms)
            if applicant.max_bathrooms:
                get_params['max_bathrooms'] = str(applicant.max_bathrooms)
            
            if applicant.desired_move_in_date:
                today = date.today()
                days_until_move = (applicant.desired_move_in_date - today).days
                if days_until_move <= 0:
                    get_params['move_in_date'] = 'available_now'
                elif days_until_move <= 30:
                    get_params['move_in_date'] = 'within_30'
                elif days_until_move <= 60:
                    get_params['move_in_date'] = 'within_60'
            
            # Apply neighborhood preferences  
            if applicant.neighborhood_preferences.exists():
                neighborhood_values = []
                for neighborhood in applicant.neighborhood_preferences.all():
                    # Map applicant neighborhood to building neighborhood choices
                    for choice_value, choice_name in Building.NEIGHBORHOOD_CHOICES:
                        if choice_name.lower() == neighborhood.name.lower() or choice_value.lower() == neighborhood.name.lower():
                            neighborhood_values.append(choice_value)
                            break
                if neighborhood_values:
                    get_params.setlist('neighborhoods', neighborhood_values)
            
            # Apply amenity preferences
            if applicant.amenities.exists():
                amenity_ids = []
                for amenity in applicant.amenities.all():
                    # Map applicant amenities to building amenities by name
                    try:
                        from buildings.models import Amenity as BuildingAmenity
                        building_amenity = BuildingAmenity.objects.filter(name__iexact=amenity.name).first()
                        if building_amenity:
                            amenity_ids.append(str(building_amenity.id))
                    except (ImportError, AttributeError):
                        # Amenity model issues - skip this amenity
                        continue
                if amenity_ids:
                    get_params.setlist('amenities', amenity_ids)
            
            # Update request.GET with the preferences
            if get_params:
                request.GET = get_params
                auto_applied_preferences = True
                
        except Exception as e:
            logger.error(f"Error applying applicant preferences: {e}")
    
    # Apply filters

    # Sorting
    sort_by = request.GET.get('sort')
    if sort_by == 'price_asc':
        apartments = apartments.order_by('rent_price')
    elif sort_by == 'price_desc':
        apartments = apartments.order_by('-rent_price')
    elif sort_by == 'newest':
        apartments = apartments.order_by('-created_at') if hasattr(Apartment, 'created_at') else apartments.order_by('-id')

    filters = {}
    
    # Price filter
    # Business Logic: Price is #1 factor in rental decisions
    # Pre-defined ranges match market segments (budget/mid/luxury)
    price_range = request.GET.get('price')
    if price_range:
        if price_range == 'under_2000':
            apartments = apartments.filter(rent_price__lt=2000)
            filters['price'] = 'Under $2,000'
        elif price_range == '2000_3000':
            apartments = apartments.filter(rent_price__gte=2000, rent_price__lte=3000)
            filters['price'] = '$2,000 - $3,000'
        elif price_range == '3000_4000':
            apartments = apartments.filter(rent_price__gte=3000, rent_price__lte=4000)
            filters['price'] = '$3,000 - $4,000'
        elif price_range == 'over_4000':
            apartments = apartments.filter(rent_price__gt=4000)
            filters['price'] = 'Over $4,000'
    
    # Custom price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        apartments = apartments.filter(rent_price__gte=min_price)
        filters['min_price'] = f'Min: ${min_price}'
    if max_price:
        apartments = apartments.filter(rent_price__lte=max_price)
        filters['max_price'] = f'Max: ${max_price}'
    
    # Bedroom filters  
    # Business Logic: Bedroom count directly correlates with household size
    # Studio handling: Studios (0 BR) grouped with 1 BR for flexibility
    min_bedrooms = request.GET.get('min_bedrooms')
    max_bedrooms = request.GET.get('max_bedrooms')
    if min_bedrooms:
        if min_bedrooms == 'studio':
            # For studio, include studios (0 bedrooms) and 1 bedrooms since user wants studio as minimum
            apartments = apartments.filter(bedrooms__lte=1)
        else:
            apartments = apartments.filter(bedrooms__gte=min_bedrooms)
        filters['min_bedrooms'] = f'Min {min_bedrooms} bed{"" if min_bedrooms == "1" else "s"}'
    if max_bedrooms:
        if max_bedrooms != '5+':
            apartments = apartments.filter(bedrooms__lte=max_bedrooms)
        filters['max_bedrooms'] = f'Max {max_bedrooms} bed{"" if max_bedrooms == "1" else "s"}'
    
    # Bathroom filters
    min_bathrooms = request.GET.get('min_bathrooms')
    max_bathrooms = request.GET.get('max_bathrooms')
    if min_bathrooms:
        apartments = apartments.filter(bathrooms__gte=min_bathrooms)
        filters['min_bathrooms'] = f'Min {min_bathrooms} bath{"" if min_bathrooms == "1" else "s"}'
    if max_bathrooms:
        if max_bathrooms != '5+':
            apartments = apartments.filter(bathrooms__lte=max_bathrooms)
        filters['max_bathrooms'] = f'Max {max_bathrooms} bath{"" if max_bathrooms == "1" else "s"}'
    
    # Move-in date filter - filter by status since we don't have date_available field
    # Business Logic: Timing urgency affects pricing power
    # Immediate availability = higher conversion but potentially lower rent
    move_in_date = request.GET.get('move_in_date')
    if move_in_date:
        if move_in_date in ['available_now', 'within_30', 'within_60']:
            # For now, just filter to available apartments since we don't have date_available
            apartments = apartments.filter(status='available')
            if move_in_date == 'available_now':
                filters['move_in_date'] = 'Available Now'
            elif move_in_date == 'within_30':
                filters['move_in_date'] = 'Within 30 days'
            elif move_in_date == 'within_60':
                filters['move_in_date'] = 'Within 60 days'
    
    # Amenities filter
    amenity_ids = request.GET.getlist('amenities')
    if amenity_ids:
        apartments = apartments.filter(building__amenities__id__in=amenity_ids).distinct()
        selected_amenities = Amenity.objects.filter(id__in=amenity_ids)
        filters['amenities'] = [amenity.name for amenity in selected_amenities]
    
    # Neighborhoods filter
    neighborhood_values = request.GET.getlist('neighborhoods')
    if neighborhood_values:
        apartments = apartments.filter(building__neighborhood__in=neighborhood_values).distinct()
        filters['neighborhoods'] = neighborhood_values
    
    # Pets filter
    # Business Logic: 70% of US households have pets - major decision factor
    # Pet-friendly units command 20-30% premium in many markets
    pets_allowed = request.GET.get('pets_allowed')
    if pets_allowed == '1':
        # Filter buildings that allow pets (exclude 'no_pets' policy)
        apartments = apartments.filter(building__pet_policy__in=['case_by_case', 'pet_fee', 'all_pets', 'small_pets', 'cats_only'])
        filters['pets_allowed'] = 'Pets Allowed'
    
    # Get all amenities and neighborhoods for filter options
    all_amenities = Amenity.objects.all().order_by('name')
    # Get neighborhood choices from Building model
    neighborhood_choices = [choice for choice in Building.NEIGHBORHOOD_CHOICES if choice[0]]
    

    # Business Feature: Smart Matching Algorithm
    # Shows personalized apartment recommendations based on user preferences
    # Impact: Higher conversion rates through better tenant-apartment fit
    smart_matches = []
    if request.user.is_authenticated and hasattr(request.user, 'applicant_profile') and not is_ajax_request:
        try:
            from applicants.apartment_matching import get_apartment_matches_for_applicant
            applicant = request.user.applicant_profile
            smart_matches = get_apartment_matches_for_applicant(applicant, limit=6)  # Show top 6 matches
        except ImportError as e:
            # Module not available - log but don't break
            logger.warning(f"Smart matching module not available: {e}")
            smart_matches = []
        except Exception as e:
            # Other errors - log but continue
            logger.error(f"Error getting smart matches: {e}")
            smart_matches = []
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
    
    # Handle AJAX requests for filtering
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Return only the apartment results as JSON
            apartments_data = []
            for apartment in apartments:
                try:
                    # Create a title from available data
                    title = f"Unit {apartment.unit_number}" if apartment.unit_number else f"{apartment.bedrooms or 0} BR / {apartment.bathrooms or 0} BA"
                    
                    # Collect all images (apartment first, then building)
                    apartment_images = [img.thumbnail_url() for img in apartment.images.all()] if apartment.images.exists() else []
                    building_images = [img.thumbnail_url() for img in apartment.building.images.all()] if apartment.building and apartment.building.images.exists() else []
                    all_images = apartment_images + building_images
                    
                    apartment_data = {
                        'id': apartment.id,
                        'title': title,
                        'rent': float(apartment.rent_price) if apartment.rent_price else 0,
                        'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
                        'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
                        'square_feet': apartment.square_feet if hasattr(apartment, 'square_feet') else 0,
                        'building_name': apartment.building.name if apartment.building else '',
                        'building_address': f"{apartment.building.street_address_1}, {apartment.building.city}, {apartment.building.state}" if apartment.building else '',
                        'neighborhood': apartment.building.get_neighborhood_display() if apartment.building and apartment.building.neighborhood else '',
                        'status': apartment.get_status_display(),
                        'thumbnail_url': apartment.images.first().thumbnail_url() if apartment.images.exists() else '',
                        'all_images': all_images,
                        'detail_url': f'/apartments/{apartment.id}/overview/',
                        'latitude': float(apartment.building.latitude) if apartment.building and apartment.building.latitude else None,
                        'longitude': float(apartment.building.longitude) if apartment.building and apartment.building.longitude else None,
                        'is_new': bool((getattr(apartment, 'created_at', None) or getattr(apartment, 'last_modified', None)) and timezone.now() and (timezone.now() - (apartment.created_at if getattr(apartment, 'created_at', None) else apartment.last_modified)).days <= 7),
                        'has_special': bool(getattr(apartment, 'rent_specials', None) or getattr(apartment, 'free_stuff', None) or (hasattr(apartment, 'concessions') and apartment.concessions.exists())),
                        'pet_policy': apartment.building.get_pet_policy_display() if apartment.building and apartment.building.pet_policy else '',
                    }
                    apartments_data.append(apartment_data)
                except Exception as e:
                    logger.error(f"Error processing apartment {apartment.id}: {e}")
                    continue
            

            return JsonResponse({
                'apartments': apartments_data,
                'total_results': apartments.count(),
                'active_filters': filters,
                'sort_by': sort_by,
                'selected_neighborhoods': neighborhood_values,
                'selected_amenities': amenity_ids,
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
    
    return render(request, 'apartments/apartments_list.html', context)



def create_apartment(request, building_id=None):
    """Redirect to the new multi-step apartment creation workflow"""
    if building_id:
        return redirect('create_apartment_v2_with_building', building_id=building_id)
    else:
        return redirect('create_apartment_v2')




def apartment_detail(request, apartment_id=None, building_id=None):
    """
    Legacy apartment editing interface - kept for backward compatibility
    Business Impact: Allows on-the-fly apartment modifications for rapid inventory updates
    Note: New workflow uses step-by-step creation for better data quality
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
                return redirect('apartment_detail', apartment_id=apartment.id)

        elif 'image_submit' in request.POST and apartment:
            image_form = ApartmentImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.apartment = apartment
                image.save()
                messages.success(request, 'Image uploaded successfully.')
                return redirect('apartment_detail', apartment_id=apartment.id)

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
    Public-facing apartment details page for prospective tenants
    Business Impact: Key conversion page - where users decide to apply or contact broker
    Features:
    - Activity tracking for lead scoring and behavior analysis  
    - Broker contact integration for lead capture
    - Optimized queries to reduce page load time
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
            # Log error but don't break the page
            logger.error(f"Failed to track apartment view: {e}")
    
    return render(request, 'apartments/apartment_overview.html', {'apartment': apartment})



def get_apartment_data(request, apartment_id):
    """
    AJAX endpoint for fetching apartment pricing details
    Business Impact: Enables dynamic price updates without page refresh
    Used by: Application forms, comparison tools, pricing calculators
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
# Business Logic: Breaking creation into steps reduces abandonment rate
# Users can save progress and return later, improving data completeness
def create_apartment_v2(request, building_id=None):
    """
    Step 1: Basic Apartment Information
    Business Impact: Captures essential data first (unit, price, bedrooms)
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

    context = {
        'sort_by': sort_by,
        'basic_form': basic_form,
        'building': building,
        'current_step': 1,
        'step_title': 'Step 1: Basic Information'
    }
    
    return render(request, 'apartments/apartment_step1.html', context)


def apartment_step2(request, apartment_id):
    """
    Step 2: Images Upload
    Business Impact: Quality photos increase inquiry rates by 40-60%
    Features:
    - Optional skip to reduce abandonment
    - Multiple image upload support
    - Cloudinary integration for automatic optimization
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
        'sort_by': sort_by,
        'apartment': apartment,
        'image_form': image_form,
        'current_step': 2,
        'step_title': 'Step 2: Images'
    }
    
    return render(request, 'apartments/apartment_step2.html', context)


def apartment_step3(request, apartment_id):
    """
    Step 3: Amenities and Features
    Business Impact: Detailed amenities help pre-qualify leads
    Strategy: Reduces unnecessary tours by setting clear expectations
    Features:
    - Links apartment-specific amenities
    - Optional skip maintains workflow flexibility
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
        'sort_by': sort_by,
        'apartment': apartment,
        'amenities_form': amenities_form,
        'current_step': 3,
        'step_title': 'Step 3: Amenities & Features'
    }
    
    return render(request, 'apartments/apartment_step3.html', context)


def apartment_step4(request, apartment_id):
    """
    Step 4: Additional Details & Completion
    Business Impact: Captures compliance and leasing requirements
    Features:
    - Lease terms and concessions entry
    - Required documents specification
    - Deposit and fee details
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
        'sort_by': sort_by,
        'apartment': apartment,
        'details_form': details_form,
        'current_step': 4,
        'step_title': 'Step 4: Additional Details'
    }
    
    return render(request, 'apartments/apartment_step4.html', context)


def apartment_complete(request, apartment_id):
    """
    Apartment Creation Complete - Success confirmation page
    Business Impact: Reinforces successful listing creation
    Next Actions: Prompts broker to add more units or review listing
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    context = {
        'sort_by': sort_by,
        'apartment': apartment,
        'current_step': 5,
        'step_title': 'Apartment Setup Complete!'
    }
    
    return render(request, 'apartments/apartment_complete.html', context)


def contact_broker(request, apartment_id):
    """
    Handle broker contact form submission - Primary lead capture mechanism
    Business Impact: Converts website visitors into qualified leads
    Features:
    - Tour scheduling with multiple time preferences
    - Direct Q&A for pre-qualification
    - Dual email notification (broker + prospect)
    - Lead tracking integration for ROI measurement
    """
    apartment = get_object_or_404(Apartment, id=apartment_id)
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            contact_type = request.POST.get('contact_type')
            
            # Prepare email content based on contact type
            if contact_type == 'request_tour':
                tour_type = request.POST.get('tour_type')
                datetime_1 = request.POST.get('preferred_datetime_1')
                datetime_2 = request.POST.get('preferred_datetime_2')
                datetime_3 = request.POST.get('preferred_datetime_3')
                
                # Format preferred times
                preferred_times = []
                for dt in [datetime_1, datetime_2, datetime_3]:
                    if dt:
                        try:
                            formatted_dt = datetime.strptime(dt, '%Y-%m-%dT%H:%M').strftime('%B %d, %Y at %I:%M %p')
                            preferred_times.append(formatted_dt)
                        except ValueError:
                            pass
                
                subject = f"Tour Request for {apartment.building.name} Unit {apartment.unit_number}"
                message = f"""
New tour request received:

Apartment: {apartment.building.name} - Unit {apartment.unit_number}
Address: {apartment.building.street_address_1}, {apartment.building.city}

Contact Details:
Name: {name}
Email: {email}
Phone: {phone}

Tour Type: {tour_type.replace('_', ' ').title()}

Preferred Times:
{chr(10).join([f"• {time}" for time in preferred_times]) if preferred_times else "No specific times provided"}

Please contact the potential tenant to schedule the tour.
                """
                
            elif contact_type == 'ask_question':
                question = request.POST.get('question')
                
                subject = f"Question about {apartment.building.name} Unit {apartment.unit_number}"
                message = f"""
New question received:

Apartment: {apartment.building.name} - Unit {apartment.unit_number}
Address: {apartment.building.street_address_1}, {apartment.building.city}

Contact Details:
Name: {name}
Email: {email}
Phone: {phone}

Question:
{question}

Please respond to the potential tenant's inquiry.
                """
            
            # Get broker email
            # Business Logic: Route leads to assigned broker for accountability
            # Falls back to user email if professional email not configured
            broker_emails = []
            for broker in apartment.building.brokers.all():
                if hasattr(broker, 'brokerprofile') and broker.brokerprofile.professional_email:
                    broker_emails.append(broker.brokerprofile.professional_email)
                elif broker.email:
                    broker_emails.append(broker.email)
            
            # Send email to broker(s)
            if broker_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=broker_emails,
                    fail_silently=False,
                )
                
                # Send confirmation email to user
                # Business Impact: Immediate response increases lead quality score
                # Sets 24-hour expectation for broker follow-up
                confirmation_subject = f"Your inquiry about {apartment.building.name} Unit {apartment.unit_number}"
                confirmation_message = f"""
Hi {name},

Thank you for your interest in {apartment.building.name} Unit {apartment.unit_number}!

We've forwarded your {'tour request' if contact_type == 'request_tour' else 'question'} to the property broker. You should hear back from them within 24 hours.

If you have any other questions, please don't hesitate to reach out.

Best regards,
DoorWay Team
                """
                
                send_mail(
                    subject=confirmation_subject,
                    message=confirmation_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
                
                messages.success(request, 'Your message has been sent to the broker. You should hear back within 24 hours!')
            else:
                messages.warning(request, 'Message sent, but no broker contact information is available for this property.')
                
        except Exception as e:
            logger.error(f"Failed to send broker contact message for apartment {apartment_id}: {e}")
            messages.error(request, 'There was an error sending your message. Please try again.')
    
    return redirect('apartment_overview', apartment_id=apartment_id)
