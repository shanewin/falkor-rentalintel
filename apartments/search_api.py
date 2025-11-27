"""
Search API endpoints for apartments.
Business Context: Provides powerful search capabilities for web and mobile clients.
Enables location-based discovery and personalized search experiences.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count
from decimal import Decimal
import json
import logging
from typing import Dict, Any

from .models import Apartment
from .search_models import (
    ApartmentSearchPreference,
    ApartmentSearchHistory,
    ApartmentSearchIndex,
    PopularSearchTerm
)
from .search_utils import (
    ApartmentSearchEngine,
    record_search,
    get_search_suggestions,
    calculate_distance
)

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def search_apartments_api(request):
    """
    POST /api/apartments/search/advanced/
    Advanced search with full-text, filters, and location.
    Business Impact: Powers the main search experience across all platforms.
    """
    try:
        # Parse request body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Extract search parameters
        query = data.get('query', '').strip()
        filters = data.get('filters', {})
        location = data.get('location')
        sort_by = data.get('sort_by', 'relevance')
        page = int(data.get('page', 1))
        per_page = min(int(data.get('per_page', 20)), 100)
        
        # Get user preferences if authenticated
        user_preferences = None
        if request.user.is_authenticated:
            # Get user's ideal preferences for ranking
            if hasattr(request.user, 'applicant_profile'):
                applicant = request.user.applicant_profile
                user_preferences = {
                    'ideal_price': float(applicant.max_rent_budget) if applicant.max_rent_budget else None,
                    'preferred_bedrooms': float(applicant.min_bedrooms) if applicant.min_bedrooms else None,
                }
        
        # Initialize search engine
        search_engine = ApartmentSearchEngine()
        
        # Perform search
        results = search_engine.search(
            query=query,
            filters=filters,
            location=location,
            user_preferences=user_preferences,
            limit=per_page * page  # Get enough for pagination
        )
        
        # Apply sorting
        if sort_by == 'price_low':
            results = results.order_by('rent_price')
        elif sort_by == 'price_high':
            results = results.order_by('-rent_price')
        elif sort_by == 'newest':
            results = results.order_by('-last_modified')
        elif sort_by == 'bedrooms':
            results = results.order_by('-bedrooms', 'rent_price')
        # 'relevance' is already applied in search engine
        
        # Pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_results = results[start_idx:end_idx]
        total_results = results.count()
        
        # Record search for analytics
        search_history = record_search(
            user=request.user if request.user.is_authenticated else None,
            session_id=request.session.session_key,
            search_params={'query': query, 'filters': filters, 'location': location},
            search_text=query,
            results_count=total_results,
            search_source='api',
            request=request
        )
        
        # Build response
        apartments_data = []
        for apartment in paginated_results:
            apt_data = {
                'id': apartment.id,
                'unit_number': apartment.unit_number,
                'building': {
                    'id': apartment.building.id,
                    'name': apartment.building.name,
                    'address': f"{apartment.building.street_address_1}, {apartment.building.city}, {apartment.building.state}",
                    'neighborhood': apartment.building.get_neighborhood_display() if apartment.building.neighborhood else None,
                    'coordinates': {
                        'latitude': float(apartment.building.latitude) if apartment.building.latitude else None,
                        'longitude': float(apartment.building.longitude) if apartment.building.longitude else None,
                    }
                },
                'bedrooms': float(apartment.bedrooms) if apartment.bedrooms else 0,
                'bathrooms': float(apartment.bathrooms) if apartment.bathrooms else 0,
                'square_feet': apartment.square_feet,
                'rent_price': float(apartment.rent_price),
                'net_price': float(apartment.net_price) if apartment.net_price else None,
                'amenities': list(apartment.amenities.values_list('name', flat=True)),
                'building_amenities': list(apartment.building.amenities.values_list('name', flat=True)),
                'images': [img.thumbnail_url() for img in apartment.images.all()[:3]],
                'has_virtual_tour': apartment.virtual_tours.filter(is_active=True).exists(),
                'availability': None,
            }
            
            # Add availability info if exists
            availability = apartment.get_current_availability()
            if availability:
                apt_data['availability'] = {
                    'available_date': availability.available_date.isoformat(),
                    'is_reserved': availability.is_reserved,
                }
            
            # Add distance if location search was used
            if hasattr(apartment, 'distance_miles'):
                apt_data['distance_miles'] = round(apartment.distance_miles, 2)
            
            # Add relevance score if available
            if hasattr(apartment, 'relevance_score'):
                apt_data['relevance_score'] = float(apartment.relevance_score)
            
            apartments_data.append(apt_data)
        
        # Response
        return JsonResponse({
            'success': True,
            'search_id': search_history.id,
            'apartments': apartments_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_results': total_results,
                'total_pages': (total_results + per_page - 1) // per_page,
                'has_next': end_idx < total_results,
                'has_previous': page > 1,
            },
            'applied_filters': filters,
            'query': query,
        })
        
    except Exception as e:
        logger.error(f"Error in search API: {e}")
        return JsonResponse({'error': 'Search failed', 'message': str(e)}, status=500)


@require_http_methods(["GET"])
def search_suggestions_api(request):
    """
    GET /api/apartments/search/suggestions/?q=<query>
    Get search suggestions for autocomplete.
    Business Impact: Improves search UX and guides users to successful searches.
    """
    try:
        query = request.GET.get('q', '').strip()
        if len(query) < 2:
            return JsonResponse({'suggestions': []})
        
        suggestions = get_search_suggestions(query, limit=10)
        
        # Also add building names that match
        from buildings.models import Building
        buildings = Building.objects.filter(
            name__icontains=query
        ).values_list('name', flat=True)[:5]
        
        suggestions.extend(buildings)
        
        # Add neighborhoods that match
        neighborhoods = []
        for code, name in Building.NEIGHBORHOOD_CHOICES:
            if query.lower() in name.lower():
                neighborhoods.append(name)
        
        suggestions.extend(neighborhoods)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
        
        return JsonResponse({
            'suggestions': unique_suggestions[:10]
        })
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return JsonResponse({'suggestions': []})


@login_required
@require_http_methods(["GET", "POST"])
def saved_searches_api(request):
    """
    GET /api/apartments/searches/saved/
    POST /api/apartments/searches/saved/
    Manage saved searches for authenticated users.
    Business Impact: Increases user retention through personalized experience.
    """
    if request.method == "GET":
        # Get user's saved searches
        searches = ApartmentSearchPreference.objects.filter(
            user=request.user
        ).order_by('-is_default', '-last_used')
        
        searches_data = []
        for search in searches:
            searches_data.append({
                'id': search.id,
                'name': search.name,
                'is_active': search.is_active,
                'is_default': search.is_default,
                'parameters': search.to_query_params(),
                'alert_frequency': search.alert_frequency,
                'use_count': search.use_count,
                'last_used': search.last_used.isoformat() if search.last_used else None,
                'created_at': search.created_at.isoformat(),
            })
        
        return JsonResponse({
            'searches': searches_data
        })
        
    elif request.method == "POST":
        # Save a new search
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Create saved search
        search = ApartmentSearchPreference.objects.create(
            user=request.user,
            name=data.get('name', 'Untitled Search'),
            is_active=data.get('is_active', True),
            is_default=data.get('is_default', False),
            min_price=data.get('min_price'),
            max_price=data.get('max_price'),
            min_bedrooms=data.get('min_bedrooms'),
            max_bedrooms=data.get('max_bedrooms'),
            min_bathrooms=data.get('min_bathrooms'),
            min_square_feet=data.get('min_square_feet'),
            max_square_feet=data.get('max_square_feet'),
            neighborhoods=data.get('neighborhoods', []),
            required_amenities=data.get('amenities', []),
            pets_allowed=data.get('pets_allowed'),
            parking_required=data.get('parking_required'),
            alert_frequency=data.get('alert_frequency', 'never'),
        )
        
        # Handle location-based search
        if 'location' in data:
            location = data['location']
            search.search_latitude = location.get('latitude')
            search.search_longitude = location.get('longitude')
            search.search_radius_miles = location.get('radius_miles', 5)
            search.search_address = location.get('address')
            search.save()
        
        return JsonResponse({
            'success': True,
            'search_id': search.id,
            'message': 'Search saved successfully'
        })


@login_required
@require_http_methods(["POST"])
def use_saved_search_api(request, search_id):
    """
    POST /api/apartments/searches/saved/<id>/use/
    Mark a saved search as used.
    Business Impact: Tracks which saved searches are most valuable to users.
    """
    try:
        search = ApartmentSearchPreference.objects.get(
            id=search_id,
            user=request.user
        )
        search.increment_use()
        
        return JsonResponse({
            'success': True,
            'use_count': search.use_count
        })
        
    except ApartmentSearchPreference.DoesNotExist:
        return JsonResponse({'error': 'Search not found'}, status=404)


@require_http_methods(["POST"])
def record_search_click_api(request):
    """
    POST /api/apartments/search/click/
    Record when a user clicks on a search result.
    Business Impact: Improves search ranking through click-through data.
    """
    try:
        data = json.loads(request.body)
        search_id = data.get('search_id')
        apartment_id = data.get('apartment_id')
        
        if not search_id or not apartment_id:
            return JsonResponse({'error': 'Missing required parameters'}, status=400)
        
        # Record the click
        try:
            search_history = ApartmentSearchHistory.objects.get(id=search_id)
            search_history.add_click(apartment_id)
            
            # Update popular search terms if this was a text search
            if search_history.search_text:
                terms = search_history.search_text.lower().split()
                for term in terms:
                    if len(term) >= 3:
                        try:
                            popular_term = PopularSearchTerm.objects.get(term=term)
                            popular_term.click_count += 1
                            popular_term.save(update_fields=['click_count'])
                        except PopularSearchTerm.DoesNotExist:
                            pass
            
            return JsonResponse({'success': True})
            
        except ApartmentSearchHistory.DoesNotExist:
            return JsonResponse({'error': 'Search history not found'}, status=404)
            
    except Exception as e:
        logger.error(f"Error recording click: {e}")
        return JsonResponse({'error': 'Failed to record click'}, status=500)


@require_http_methods(["GET"])
def popular_searches_api(request):
    """
    GET /api/apartments/searches/popular/
    Get popular search terms and trends.
    Business Impact: Shows trending searches to inspire users and showcase inventory.
    """
    try:
        # Get top search terms
        popular_terms = PopularSearchTerm.objects.filter(
            search_count__gt=10  # Minimum threshold
        ).order_by('-searches_this_week')[:20]
        
        # Get trending neighborhoods
        from django.db.models import Count
        trending_neighborhoods = ApartmentSearchHistory.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('search_params__neighborhoods').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Format response
        terms_data = []
        for term in popular_terms:
            terms_data.append({
                'term': term.term,
                'category': term.category,
                'search_count': term.search_count,
                'trend': 'up' if term.searches_this_week > term.searches_this_month / 4 else 'stable'
            })
        
        return JsonResponse({
            'popular_searches': terms_data,
            'trending_neighborhoods': [n['search_params__neighborhoods'] for n in trending_neighborhoods if n['search_params__neighborhoods']],
        })
        
    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        return JsonResponse({'error': 'Failed to get popular searches'}, status=500)


@login_required
@require_http_methods(["POST"])
def rebuild_search_index_api(request):
    """
    POST /api/apartments/search/rebuild-index/
    Rebuild the search index for all apartments.
    Business Impact: Ensures search results are accurate and up-to-date.
    Note: This should be run periodically or after bulk updates.
    """
    try:
        # SECURITY FIX: Ensure user is authenticated and is staff
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        # Rebuild index for all apartments
        apartments = Apartment.objects.all()
        rebuilt_count = 0
        
        for apartment in apartments:
            # Get or create search index
            search_index, created = ApartmentSearchIndex.objects.get_or_create(
                apartment=apartment
            )
            search_index.rebuild_index()
            rebuilt_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Rebuilt search index for {rebuilt_count} apartments'
        })
        
    except Exception as e:
        logger.error(f"Error rebuilding search index: {e}")
        return JsonResponse({'error': 'Failed to rebuild index'}, status=500)


# Import these views in your urls.py
from django.utils import timezone
from datetime import timedelta