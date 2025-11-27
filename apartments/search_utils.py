"""
Search utilities for apartments app.
Business Context: Provides advanced search capabilities including
full-text search, distance-based filtering, and smart ranking.
"""

from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.db.models import Q, F, Value, FloatField, When, Case
from django.db.models.functions import Cast
from django.db import models
import math
from decimal import Decimal
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    Returns distance in miles.
    Business Impact: Enables "apartments near me" and commute-based searches.
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in miles
    radius_miles = 3959
    
    return radius_miles * c


class ApartmentSearchEngine:
    """
    Advanced search engine for apartments.
    Business Impact: Provides Google-like search experience for apartment hunting.
    """
    
    def __init__(self, base_queryset=None):
        """Initialize with optional base queryset"""
        if base_queryset is None:
            from .models import Apartment
            base_queryset = Apartment.objects.filter(status='available')
        
        self.queryset = base_queryset.select_related('building').prefetch_related(
            'amenities', 'building__amenities', 'images'
        )
        
    def full_text_search(self, query: str, use_trigram: bool = True) -> models.QuerySet:
        """
        Perform full-text search on apartments.
        Uses PostgreSQL's full-text search with ranking.
        
        Args:
            query: Search query string
            use_trigram: Also use trigram similarity for fuzzy matching
            
        Business Impact: Allows natural language searches like "2 bedroom with gym near downtown"
        """
        if not query:
            return self.queryset
        
        # Create search query
        search_query = SearchQuery(query, search_type='websearch')
        
        # Create search vector with weighted fields
        search_vector = (
            SearchVector('unit_number', weight='A') +
            SearchVector('building__name', weight='A') +
            SearchVector('building__neighborhood', weight='B') +
            SearchVector('description', weight='C') +
            SearchVector('building__street_address_1', weight='B')
        )
        
        # Apply full-text search with ranking
        results = self.queryset.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(search=search_query).order_by('-rank')
        
        # If using trigram similarity for fuzzy matching
        if use_trigram and not results.exists():
            # Fallback to trigram similarity for typos
            results = self.queryset.annotate(
                similarity=TrigramSimilarity('building__name', query) +
                          TrigramSimilarity('building__neighborhood', query) +
                          TrigramSimilarity('description', query)
            ).filter(similarity__gt=0.1).order_by('-similarity')
        
        return results
    
    def distance_search(
        self, 
        latitude: float, 
        longitude: float, 
        radius_miles: float = 5.0,
        order_by_distance: bool = True
    ) -> models.QuerySet:
        """
        Search apartments within a radius from a point.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_miles: Search radius in miles
            order_by_distance: Whether to order results by distance
            
        Business Impact: Enables location-based search for commute optimization
        """
        # Convert radius to approximate degrees (rough approximation)
        # 1 degree latitude ≈ 69 miles
        # 1 degree longitude ≈ 69 miles * cos(latitude)
        lat_range = radius_miles / 69
        lon_range = radius_miles / (69 * abs(math.cos(math.radians(latitude))))
        
        # Filter by bounding box first (for performance)
        results = self.queryset.filter(
            building__latitude__range=(
                Decimal(latitude - lat_range),
                Decimal(latitude + lat_range)
            ),
            building__longitude__range=(
                Decimal(longitude - lon_range),
                Decimal(longitude + lon_range)
            )
        )
        
        # Calculate actual distance using database functions
        # This is an approximation but good enough for sorting
        results = results.annotate(
            distance_miles=Cast(
                111.111 * models.Func(
                    models.Func(
                        models.F('building__latitude') - latitude,
                        function='RADIANS'
                    ),
                    models.Func(
                        models.F('building__longitude') - longitude,
                        function='RADIANS'
                    ),
                    function='SQRT',
                    template='SQRT(POWER(%(expressions)s, 2) + POWER(%(expressions)s, 2))'
                ),
                FloatField()
            )
        ).filter(distance_miles__lte=radius_miles)
        
        if order_by_distance:
            results = results.order_by('distance_miles')
            
        return results
    
    def smart_filter(self, filters: Dict[str, Any]) -> models.QuerySet:
        """
        Apply smart filters with intelligent defaults.
        
        Args:
            filters: Dictionary of filter parameters
            
        Business Impact: Reduces irrelevant results and improves match quality
        """
        queryset = self.queryset
        
        # Price filtering with flexibility
        if 'price_target' in filters:
            # Flexible price range around target
            target = filters['price_target']
            flexibility = filters.get('price_flexibility', 0.1)  # 10% default
            min_price = target * (1 - flexibility)
            max_price = target * (1 + flexibility)
            queryset = queryset.filter(
                rent_price__gte=min_price,
                rent_price__lte=max_price
            )
        else:
            # Traditional min/max filtering
            if 'min_price' in filters:
                queryset = queryset.filter(rent_price__gte=filters['min_price'])
            if 'max_price' in filters:
                queryset = queryset.filter(rent_price__lte=filters['max_price'])
        
        # Bedroom filtering
        if 'bedrooms' in filters:
            if filters['bedrooms'] == 'studio':
                queryset = queryset.filter(bedrooms=0)
            else:
                queryset = queryset.filter(bedrooms=filters['bedrooms'])
        else:
            if 'min_bedrooms' in filters:
                queryset = queryset.filter(bedrooms__gte=filters['min_bedrooms'])
            if 'max_bedrooms' in filters:
                queryset = queryset.filter(bedrooms__lte=filters['max_bedrooms'])
        
        # Bathroom filtering
        if 'min_bathrooms' in filters:
            queryset = queryset.filter(bathrooms__gte=filters['min_bathrooms'])
            
        # Square footage filtering
        if 'min_square_feet' in filters:
            queryset = queryset.filter(square_feet__gte=filters['min_square_feet'])
        if 'max_square_feet' in filters:
            queryset = queryset.filter(square_feet__lte=filters['max_square_feet'])
            
        # Neighborhood filtering
        if 'neighborhoods' in filters and filters['neighborhoods']:
            queryset = queryset.filter(building__neighborhood__in=filters['neighborhoods'])
            
        # Amenity filtering
        if 'amenities' in filters and filters['amenities']:
            for amenity_id in filters['amenities']:
                queryset = queryset.filter(
                    Q(amenities__id=amenity_id) |
                    Q(building__amenities__id=amenity_id)
                ).distinct()
                
        # Pet policy filtering
        if filters.get('pets_allowed'):
            queryset = queryset.exclude(building__pet_policy='no_pets')
            
        # Parking filtering
        if filters.get('parking_required'):
            queryset = queryset.filter(
                parking_options__spaces_included__gt=0
            ).distinct()
            
        # Availability date filtering
        if 'available_by' in filters:
            from .models_extended import ApartmentAvailability
            available_date = filters['available_by']
            
            # Get apartments that are available by the date
            available_ids = ApartmentAvailability.objects.filter(
                available_date__lte=available_date,
                is_reserved=False
            ).values_list('apartment_id', flat=True)
            
            # Include apartments without availability records (assumed available now)
            no_availability = queryset.exclude(
                id__in=ApartmentAvailability.objects.values_list('apartment_id', flat=True)
            )
            
            queryset = queryset.filter(
                Q(id__in=available_ids) | Q(id__in=no_availability.values_list('id', flat=True))
            )
            
        # Utilities included filtering
        if 'utilities_included' in filters and filters['utilities_included']:
            from .models_extended import ApartmentUtilities
            utility_filters = Q()
            
            for utility in filters['utilities_included']:
                field_name = f"{utility}_included"
                utility_filters |= Q(**{f"utilities__{field_name}": True})
                
            queryset = queryset.filter(utility_filters).distinct()
            
        return queryset
    
    def rank_results(
        self, 
        queryset: models.QuerySet,
        user_preferences: Optional[Dict] = None
    ) -> models.QuerySet:
        """
        Apply smart ranking based on relevance and user preferences.
        
        Business Impact: Shows most relevant results first, improving conversion
        """
        # Base scoring
        queryset = queryset.annotate(
            relevance_score=Value(100, output_field=FloatField())
        )
        
        if user_preferences:
            # Boost apartments matching user preferences
            
            # Price match bonus
            if 'ideal_price' in user_preferences:
                ideal = user_preferences['ideal_price']
                queryset = queryset.annotate(
                    price_diff=models.Func(
                        F('rent_price') - ideal,
                        function='ABS'
                    ),
                    price_score=Case(
                        When(price_diff__lte=200, then=20),
                        When(price_diff__lte=500, then=10),
                        When(price_diff__lte=1000, then=5),
                        default=0,
                        output_field=FloatField()
                    )
                )
                queryset = queryset.annotate(
                    relevance_score=F('relevance_score') + F('price_score')
                )
            
            # Bedroom match bonus
            if 'preferred_bedrooms' in user_preferences:
                preferred = user_preferences['preferred_bedrooms']
                queryset = queryset.annotate(
                    bedroom_score=Case(
                        When(bedrooms=preferred, then=15),
                        When(bedrooms=preferred-0.5, then=10),
                        When(bedrooms=preferred+0.5, then=10),
                        default=0,
                        output_field=FloatField()
                    )
                )
                queryset = queryset.annotate(
                    relevance_score=F('relevance_score') + F('bedroom_score')
                )
            
            # Recently updated bonus (fresh listings)
            from datetime import timedelta
            from django.utils import timezone
            recent_date = timezone.now() - timedelta(days=7)
            
            queryset = queryset.annotate(
                freshness_score=Case(
                    When(last_modified__gte=recent_date, then=10),
                    default=0,
                    output_field=FloatField()
                )
            )
            queryset = queryset.annotate(
                relevance_score=F('relevance_score') + F('freshness_score')
            )
            
        # Order by relevance score
        return queryset.order_by('-relevance_score', 'rent_price')
    
    def search(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        location: Optional[Dict[str, float]] = None,
        user_preferences: Optional[Dict] = None,
        limit: int = 50
    ) -> models.QuerySet:
        """
        Main search method combining all search features.
        
        Args:
            query: Free text search query
            filters: Filter parameters
            location: Dict with 'latitude', 'longitude', and optional 'radius_miles'
            user_preferences: User preference data for ranking
            limit: Maximum results to return
            
        Returns:
            QuerySet of matching apartments
            
        Business Impact: Provides comprehensive search combining all methods
        """
        results = self.queryset
        
        # Apply text search if query provided
        if query:
            results = self.full_text_search(query)
            
        # Apply filters if provided
        if filters:
            results = self.smart_filter(filters)
            
        # Apply distance search if location provided
        if location and 'latitude' in location and 'longitude' in location:
            radius = location.get('radius_miles', 5.0)
            results = self.distance_search(
                location['latitude'],
                location['longitude'],
                radius,
                order_by_distance=not query  # Only order by distance if no text search
            )
            
        # Apply ranking
        results = self.rank_results(results, user_preferences)
        
        # Apply limit
        results = results[:limit]
        
        return results


def record_search(
    user=None,
    session_id=None,
    search_params=None,
    search_text=None,
    results_count=0,
    search_source='listing',
    request=None
):
    """
    Record a search in history for analytics.
    
    Business Impact: Enables data-driven search improvements and personalization
    """
    from .search_models import ApartmentSearchHistory, PopularSearchTerm
    
    # Create search history record
    history = ApartmentSearchHistory.objects.create(
        user=user,
        session_id=session_id,
        search_params=search_params or {},
        search_text=search_text,
        results_count=results_count,
        search_source=search_source
    )
    
    # Extract IP and user agent from request if provided
    if request:
        history.ip_address = request.META.get('REMOTE_ADDR')
        history.user_agent = request.META.get('HTTP_USER_AGENT')
        history.save(update_fields=['ip_address', 'user_agent'])
    
    # Update popular search terms if text search was used
    if search_text:
        # Extract individual terms
        terms = search_text.lower().split()
        for term in terms:
            if len(term) >= 3:  # Skip very short terms
                popular_term, created = PopularSearchTerm.objects.get_or_create(
                    term=term
                )
                popular_term.increment_search()
                
    return history


def get_search_suggestions(prefix: str, limit: int = 10) -> List[str]:
    """
    Get search suggestions for autocomplete.
    
    Business Impact: Improves search UX and guides users to successful searches
    """
    from .search_models import PopularSearchTerm
    
    # Get popular terms starting with prefix
    suggestions = PopularSearchTerm.objects.filter(
        term__istartswith=prefix
    ).order_by('-search_count')[:limit]
    
    return [s.term for s in suggestions]