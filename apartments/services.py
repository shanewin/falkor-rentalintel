import logging
from datetime import datetime, date
from django.db.models import Q
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Apartment, ApartmentImage
from buildings.models import Building, Amenity

logger = logging.getLogger(__name__)

def get_filtered_apartments(request, user):
    """
    Handles complex filtering logic for apartments list.
    Returns:
        apartments (QuerySet): Filtered apartments
        filters (dict): Active filters for display
        auto_applied (bool): Whether preferences were auto-applied
    """
    # Start with all apartments - optimized query with related data
    apartments = Apartment.objects.all().select_related('building').prefetch_related('images', 'building__amenities')
    
    # Business Logic: Auto-populate filters from applicant preferences
    auto_applied_preferences = False
    is_ajax_request = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if user.is_authenticated and not request.GET and hasattr(user, 'applicant_profile') and not is_ajax_request:
        try:
            applicant = user.applicant_profile
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
                        continue
                if amenity_ids:
                    get_params.setlist('amenities', amenity_ids)
            
            # Update request.GET with the preferences
            if get_params:
                request.GET = get_params
                auto_applied_preferences = True
                
        except Exception as e:
            logger.error(f"Error applying applicant preferences: {e}")

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
    min_bedrooms = request.GET.get('min_bedrooms')
    max_bedrooms = request.GET.get('max_bedrooms')
    if min_bedrooms:
        if min_bedrooms == 'studio':
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
    
    # Move-in date filter
    move_in_date = request.GET.get('move_in_date')
    if move_in_date:
        if move_in_date in ['available_now', 'within_30', 'within_60']:
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
    pets_allowed = request.GET.get('pets_allowed')
    if pets_allowed == '1':
        apartments = apartments.filter(building__pet_policy__in=['case_by_case', 'pet_fee', 'all_pets', 'small_pets', 'cats_only'])
        filters['pets_allowed'] = 'Pets Allowed'
        
    return apartments, filters, auto_applied_preferences


def serialize_apartments_for_map(apartments):
    """
    Serializes apartment queryset into JSON format for map/AJAX.
    """
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
            
    return apartments_data


def handle_broker_contact(apartment, form_data):
    """
    Handles the logic for emailing the broker and confirming with the user.
    """
    name = form_data.get('name')
    email = form_data.get('email')
    phone = form_data.get('phone')
    contact_type = form_data.get('contact_type')
    
    # Prepare email content based on contact type
    if contact_type == 'request_tour':
        tour_type = form_data.get('tour_type')
        datetime_1 = form_data.get('preferred_datetime_1')
        datetime_2 = form_data.get('preferred_datetime_2')
        datetime_3 = form_data.get('preferred_datetime_3')
        
        # Format preferred times
        preferred_times = []
        for dt in [datetime_1, datetime_2, datetime_3]:
            if dt:
                try:
                    # If it's already a datetime object (from cleaned_data)
                    if isinstance(dt, (datetime, date)):
                        formatted_dt = dt.strftime('%B %d, %Y at %I:%M %p')
                    else:
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

Tour Type: {tour_type.replace('_', ' ').title() if tour_type else 'Not specified'}

Preferred Times:
{chr(10).join([f"• {time}" for time in preferred_times]) if preferred_times else "No specific times provided"}

Please contact the potential tenant to schedule the tour.
        """
        
    else:  # ask_question
        question = form_data.get('question')
        
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
    
    # Get broker emails
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
        return True
    
    return False
