"""
API endpoints for apartments app.
Business Context: Provides programmatic access to apartment inventory for
mobile apps, partner integrations, and third-party listing services.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from .models import Apartment, ApartmentAmenity, ApartmentConcession
from buildings.models import Building
import json
import logging

logger = logging.getLogger(__name__)


def apartment_list_api(request):
    """
    GET /api/apartments/
    Returns paginated list of available apartments with filtering.
    Business Impact: Powers mobile apps and partner property search widgets.
    """
    try:
        # Start with available apartments only
        apartments = Apartment.objects.filter(status='available').select_related('building')
        
        # Apply filters from query parameters
        
        # Price filtering
        min_price = request.GET.get('min_price')
        max_price = request.GET.get('max_price')
        if min_price:
            apartments = apartments.filter(rent_price__gte=min_price)
        if max_price:
            apartments = apartments.filter(rent_price__lte=max_price)
            
        # Bedroom filtering
        min_beds = request.GET.get('min_beds')
        max_beds = request.GET.get('max_beds')
        if min_beds:
            apartments = apartments.filter(bedrooms__gte=min_beds)
        if max_beds:
            apartments = apartments.filter(bedrooms__lte=max_beds)
            
        # Bathroom filtering
        min_baths = request.GET.get('min_baths')
        if min_baths:
            apartments = apartments.filter(bathrooms__gte=min_baths)
            
        # Square footage filtering
        min_sqft = request.GET.get('min_sqft')
        max_sqft = request.GET.get('max_sqft')
        if min_sqft:
            apartments = apartments.filter(square_feet__gte=min_sqft)
        if max_sqft:
            apartments = apartments.filter(square_feet__lte=max_sqft)
            
        # Neighborhood filtering
        neighborhood = request.GET.get('neighborhood')
        if neighborhood:
            apartments = apartments.filter(building__neighborhood=neighborhood)
            
        # Building filtering
        building_id = request.GET.get('building_id')
        if building_id:
            apartments = apartments.filter(building_id=building_id)
            
        # Sorting
        sort_by = request.GET.get('sort', 'rent_price')
        valid_sorts = ['rent_price', '-rent_price', 'bedrooms', '-bedrooms', 
                      'square_feet', '-square_feet', 'last_modified', '-last_modified']
        if sort_by in valid_sorts:
            apartments = apartments.order_by(sort_by)
        else:
            apartments = apartments.order_by('rent_price')
            
        # Pagination
        page = request.GET.get('page', 1)
        per_page = min(int(request.GET.get('per_page', 20)), 100)  # Max 100 per page
        paginator = Paginator(apartments, per_page)
        page_obj = paginator.get_page(page)
        
        # Build response data
        data = {
            'apartments': [],
            'pagination': {
                'total': paginator.count,
                'page': page_obj.number,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }
        
        for apartment in page_obj:
            apt_data = {
                'id': apartment.id,
                'unit_number': apartment.unit_number,
                'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
                'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
                'square_feet': apartment.square_feet,
                'rent_price': float(apartment.rent_price) if apartment.rent_price else 0,
                'net_price': float(apartment.net_price) if apartment.net_price else None,
                'deposit_price': float(apartment.deposit_price) if apartment.deposit_price else None,
                'apartment_type': apartment.apartment_type,
                'building': {
                    'id': apartment.building.id,
                    'name': apartment.building.name,
                    'address': f"{apartment.building.street_address_1}, {apartment.building.city}, {apartment.building.state} {apartment.building.zip_code}",
                    'neighborhood': apartment.building.get_neighborhood_display() if apartment.building.neighborhood else None,
                    'latitude': float(apartment.building.latitude) if apartment.building.latitude else None,
                    'longitude': float(apartment.building.longitude) if apartment.building.longitude else None,
                },
                'amenities': list(apartment.amenities.values_list('name', flat=True)),
                'has_concessions': apartment.concessions.exists(),
                'images_count': apartment.images.count(),
                'last_modified': apartment.last_modified.isoformat()
            }
            data['apartments'].append(apt_data)
            
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error in apartment_list_api: {e}")
        return JsonResponse({'error': 'An error occurred while fetching apartments'}, status=500)


def apartment_detail_api(request, apartment_id):
    """
    GET /api/apartments/<id>/
    Returns detailed information about a specific apartment.
    Business Impact: Provides complete listing data for detail views and applications.
    """
    try:
        apartment = get_object_or_404(
            Apartment.objects.select_related('building')
            .prefetch_related('amenities', 'images', 'concessions'),
            id=apartment_id
        )
        
        # Build comprehensive apartment data
        data = {
            'id': apartment.id,
            'unit_number': apartment.unit_number,
            'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
            'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
            'square_feet': apartment.square_feet,
            'apartment_type': apartment.get_apartment_type_display(),
            'status': apartment.status,
            'pricing': {
                'rent': float(apartment.rent_price) if apartment.rent_price else 0,
                'net_effective': float(apartment.net_price) if apartment.net_price else None,
                'deposit': float(apartment.deposit_price) if apartment.deposit_price else None,
                'holding_deposit': float(apartment.holding_deposit) if apartment.holding_deposit else None,
                'broker_fee_required': apartment.broker_fee_required,
            },
            'lease_terms': {
                'duration': apartment.lease_duration,
                'paid_months': apartment.paid_months,
                'free_stuff': apartment.free_stuff,
                'required_documents': apartment.required_documents,
            },
            'building': {
                'id': apartment.building.id,
                'name': apartment.building.name,
                'address': {
                    'street': apartment.building.street_address_1,
                    'street2': apartment.building.street_address_2,
                    'city': apartment.building.city,
                    'state': apartment.building.state,
                    'zip': apartment.building.zip_code,
                },
                'neighborhood': apartment.building.get_neighborhood_display() if apartment.building.neighborhood else None,
                'coordinates': {
                    'latitude': float(apartment.building.latitude) if apartment.building.latitude else None,
                    'longitude': float(apartment.building.longitude) if apartment.building.longitude else None,
                },
                'pet_policy': apartment.building.get_pet_policy_display() if apartment.building.pet_policy else None,
                'amenities': list(apartment.building.amenities.values_list('name', flat=True)),
            },
            'apartment_amenities': list(apartment.amenities.values_list('name', flat=True)),
            'concessions': [],
            'images': [],
            'description': apartment.description,
            'lock_type': apartment.lock_type,
            'last_modified': apartment.last_modified.isoformat()
        }
        
        # Add concession details
        for concession in apartment.concessions.all():
            data['concessions'].append({
                'name': concession.name,
                'months_free': float(concession.months_free) if concession.months_free else 0,
                'lease_terms': concession.lease_terms,
            })
            
        # Add image URLs
        for image in apartment.images.all():
            data['images'].append({
                'thumbnail': image.thumbnail_url(),
                'large': image.large_url(),
                'original': image.image.url
            })
            
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error in apartment_detail_api: {e}")
        return JsonResponse({'error': 'An error occurred while fetching apartment details'}, status=500)


def apartment_search_api(request):
    """
    POST /api/apartments/search/
    Advanced search endpoint with multiple criteria.
    Business Impact: Enables sophisticated matching for tenant preferences.
    """
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Method not allowed'}, status=405)
            
        try:
            search_data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
        apartments = Apartment.objects.filter(status='available').select_related('building')
        
        # Apply search criteria
        criteria = search_data.get('criteria', {})
        
        # Price range with optional flexibility
        if 'price' in criteria:
            base_price = criteria['price'].get('target')
            flexibility = criteria['price'].get('flexibility', 0)  # Percentage
            if base_price:
                min_price = base_price * (1 - flexibility/100)
                max_price = base_price * (1 + flexibility/100)
                apartments = apartments.filter(rent_price__gte=min_price, rent_price__lte=max_price)
                
        # Required amenities (must have all)
        if 'required_amenities' in criteria:
            for amenity_name in criteria['required_amenities']:
                apartments = apartments.filter(
                    Q(amenities__name__iexact=amenity_name) |
                    Q(building__amenities__name__iexact=amenity_name)
                )
                
        # Neighborhood preferences (any match)
        if 'neighborhoods' in criteria:
            apartments = apartments.filter(building__neighborhood__in=criteria['neighborhoods'])
            
        # Minimum requirements
        if 'minimum' in criteria:
            min_req = criteria['minimum']
            if 'bedrooms' in min_req:
                apartments = apartments.filter(bedrooms__gte=min_req['bedrooms'])
            if 'bathrooms' in min_req:
                apartments = apartments.filter(bathrooms__gte=min_req['bathrooms'])
            if 'square_feet' in min_req:
                apartments = apartments.filter(square_feet__gte=min_req['square_feet'])
                
        # Pet-friendly filter
        if criteria.get('pets_allowed'):
            apartments = apartments.exclude(building__pet_policy='no_pets')
            
        # Has concessions filter
        if criteria.get('has_concessions'):
            apartments = apartments.annotate(
                concession_count=Count('concessions')
            ).filter(concession_count__gt=0)
            
        # Limit results
        limit = min(search_data.get('limit', 50), 100)
        apartments = apartments[:limit]
        
        # Build response
        results = []
        for apartment in apartments:
            results.append({
                'id': apartment.id,
                'unit_number': apartment.unit_number,
                'building_name': apartment.building.name,
                'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
                'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
                'square_feet': apartment.square_feet,
                'rent_price': float(apartment.rent_price),
                'neighborhood': apartment.building.get_neighborhood_display() if apartment.building.neighborhood else None,
                'match_score': calculate_match_score(apartment, criteria)  # Custom scoring
            })
            
        # Sort by match score if scoring is enabled
        results.sort(key=lambda x: x['match_score'], reverse=True)
        
        return JsonResponse({
            'results': results,
            'count': len(results)
        })
        
    except Exception as e:
        logger.error(f"Error in apartment_search_api: {e}")
        return JsonResponse({'error': 'An error occurred during search'}, status=500)


def building_apartments_api(request, building_id):
    """
    GET /api/buildings/<id>/apartments/
    Returns all apartments for a specific building.
    Business Impact: Enables building-specific inventory views for property managers.
    """
    try:
        building = get_object_or_404(Building, id=building_id)
        apartments = Apartment.objects.filter(building=building).order_by('unit_number')
        
        # Group by status for overview
        status_counts = {
            'available': apartments.filter(status='available').count(),
            'pending': apartments.filter(status='pending').count(),
            'rented': apartments.filter(status='rented').count(),
            'unavailable': apartments.filter(status='unavailable').count(),
        }
        
        # Calculate building statistics
        available_apts = apartments.filter(status='available')
        stats = {
            'total_units': apartments.count(),
            'occupancy_rate': (1 - (status_counts['available'] / apartments.count())) * 100 if apartments.count() > 0 else 0,
            'average_rent': available_apts.aggregate(Avg('rent_price'))['rent_price__avg'],
            'price_range': {
                'min': float(min(apt.rent_price for apt in available_apts)) if available_apts else None,
                'max': float(max(apt.rent_price for apt in available_apts)) if available_apts else None,
            }
        }
        
        # Build apartment list
        apartment_list = []
        for apartment in apartments:
            apartment_list.append({
                'id': apartment.id,
                'unit_number': apartment.unit_number,
                'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
                'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
                'square_feet': apartment.square_feet,
                'rent_price': float(apartment.rent_price),
                'status': apartment.status,
                'has_images': apartment.images.exists(),
            })
            
        return JsonResponse({
            'building': {
                'id': building.id,
                'name': building.name,
                'address': f"{building.street_address_1}, {building.city}, {building.state}",
            },
            'statistics': stats,
            'status_breakdown': status_counts,
            'apartments': apartment_list
        })
        
    except Exception as e:
        logger.error(f"Error in building_apartments_api: {e}")
        return JsonResponse({'error': 'An error occurred while fetching building apartments'}, status=500)


@login_required
@require_http_methods(["POST"])
def update_apartment_status_api(request, apartment_id):
    """
    POST /api/apartments/<id>/status/
    Updates apartment availability status.
    Business Impact: Enables real-time inventory management for brokers.
    Requires authentication.
    """
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
        
        # SECURITY FIX: Proper permission check
        # Only allow staff or brokers who manage this building
        can_update = (
            request.user.is_staff or 
            (hasattr(request.user, 'brokerprofile') and 
             apartment.building.brokers.filter(id=request.user.id).exists())
        )
        
        if not can_update:
            return JsonResponse({'error': 'Permission denied'}, status=403)
            
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
            
        new_status = data.get('status')
        valid_statuses = ['available', 'pending', 'rented', 'unavailable']
        
        if new_status not in valid_statuses:
            return JsonResponse({
                'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
            
        old_status = apartment.status
        apartment.status = new_status
        apartment.save()
        
        # Log the status change
        logger.info(f"Apartment {apartment.id} status changed from {old_status} to {new_status} by user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'apartment_id': apartment.id,
            'old_status': old_status,
            'new_status': new_status,
            'updated_at': apartment.last_modified.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error updating apartment status: {e}")
        return JsonResponse({'error': 'An error occurred while updating status'}, status=500)


def apartment_amenities_api(request):
    """
    GET /api/amenities/
    Returns list of all available apartment amenities.
    Business Impact: Powers amenity filters in search interfaces.
    """
    try:
        amenities = ApartmentAmenity.objects.all().order_by('name')
        data = {
            'amenities': [
                {'id': amenity.id, 'name': amenity.name}
                for amenity in amenities
            ]
        }
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error fetching amenities: {e}")
        return JsonResponse({'error': 'An error occurred while fetching amenities'}, status=500)


def neighborhoods_api(request):
    """
    GET /api/neighborhoods/
    Returns list of available neighborhoods.
    Business Impact: Enables location-based search and filtering.
    """
    try:
        neighborhoods = []
        for value, label in Building.NEIGHBORHOOD_CHOICES:
            if value:  # Skip empty values
                neighborhoods.append({
                    'value': value,
                    'label': label,
                    'apartment_count': Apartment.objects.filter(
                        building__neighborhood=value,
                        status='available'
                    ).count()
                })
                
        # Sort by apartment count (most popular first)
        neighborhoods.sort(key=lambda x: x['apartment_count'], reverse=True)
        
        return JsonResponse({'neighborhoods': neighborhoods})
        
    except Exception as e:
        logger.error(f"Error fetching neighborhoods: {e}")
        return JsonResponse({'error': 'An error occurred while fetching neighborhoods'}, status=500)


def calculate_match_score(apartment, criteria):
    """
    Calculate match score for apartment based on search criteria.
    Business Logic: Higher scores indicate better matches for tenant preferences.
    Score range: 0-100
    """
    score = 50  # Base score
    
    # Price match (±20 points)
    if 'price' in criteria and criteria['price'].get('target'):
        target = criteria['price']['target']
        diff_percent = abs(float(apartment.rent_price) - target) / target * 100
        if diff_percent <= 5:
            score += 20
        elif diff_percent <= 10:
            score += 10
        elif diff_percent <= 20:
            score += 5
        else:
            score -= 10
            
    # Amenity matches (+5 per match, max +20)
    if 'required_amenities' in criteria:
        apt_amenities = set(apartment.amenities.values_list('name', flat=True))
        bldg_amenities = set(apartment.building.amenities.values_list('name', flat=True))
        all_amenities = apt_amenities.union(bldg_amenities)
        
        matches = len(set(criteria['required_amenities']).intersection(all_amenities))
        score += min(matches * 5, 20)
        
    # Exact neighborhood match (+15)
    if 'neighborhoods' in criteria:
        if apartment.building.neighborhood in criteria['neighborhoods']:
            score += 15
            
    # Meets minimum requirements (+15)
    if 'minimum' in criteria:
        meets_all = True
        min_req = criteria['minimum']
        
        if 'bedrooms' in min_req and apartment.bedrooms:
            if apartment.bedrooms < min_req['bedrooms']:
                meets_all = False
        if 'bathrooms' in min_req and apartment.bathrooms:
            if apartment.bathrooms < min_req['bathrooms']:
                meets_all = False
        if 'square_feet' in min_req and apartment.square_feet:
            if apartment.square_feet < min_req['square_feet']:
                meets_all = False
                
        if meets_all:
            score += 15
            
    # Has concessions bonus (+10)
    if criteria.get('has_concessions') and apartment.concessions.exists():
        score += 10
        
    return min(max(score, 0), 100)  # Clamp between 0 and 100