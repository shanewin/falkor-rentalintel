"""
Search and filter models for apartments app.
Business Context: Enhances user experience by providing personalized search,
saving preferences, and enabling location-based discovery.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Q
import json

User = get_user_model()


class ApartmentSearchPreference(models.Model):
    """
    Saved search preferences for users.
    Business Impact: Increases user retention by remembering preferences.
    Reduces search time and improves match quality.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_preferences')
    
    # Search name and metadata
    name = models.CharField(
        max_length=100,
        help_text="Name for this saved search"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether to use for alerts"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default search to load"
    )
    
    # Price preferences
    min_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    max_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    
    # Size preferences
    min_bedrooms = models.DecimalField(
        max_digits=3, 
        decimal_places=1,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    max_bedrooms = models.DecimalField(
        max_digits=3, 
        decimal_places=1,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    min_bathrooms = models.DecimalField(
        max_digits=3, 
        decimal_places=1,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    min_square_feet = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(100)]
    )
    max_square_feet = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(100)]
    )
    
    # Location preferences
    neighborhoods = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="Preferred neighborhoods"
    )
    
    # Location-based search
    search_latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        blank=True, 
        null=True,
        help_text="Center point latitude for distance search"
    )
    search_longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=7,
        blank=True, 
        null=True,
        help_text="Center point longitude for distance search"
    )
    search_radius_miles = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0.1), MaxValueValidator(50)],
        help_text="Search radius in miles"
    )
    search_address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Address used for search center"
    )
    
    # Amenities (store as JSON for flexibility)
    required_amenities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of required amenity names"
    )
    
    # Additional preferences
    apartment_types = ArrayField(
        models.CharField(max_length=20),
        blank=True,
        default=list,
        help_text="Preferred apartment types"
    )
    pets_allowed = models.BooleanField(
        blank=True,
        null=True,
        help_text="Must allow pets"
    )
    parking_required = models.BooleanField(
        blank=True,
        null=True,
        help_text="Must have parking"
    )
    
    # Utilities preferences
    utilities_included_required = ArrayField(
        models.CharField(max_length=20),
        blank=True,
        default=list,
        help_text="Required included utilities"
    )
    
    # Move-in date preference
    earliest_move_date = models.DateField(
        blank=True,
        null=True,
        help_text="Earliest possible move-in date"
    )
    latest_move_date = models.DateField(
        blank=True,
        null=True,
        help_text="Latest acceptable move-in date"
    )
    
    # Alert preferences
    alert_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Immediate'),
            ('daily', 'Daily Digest'),
            ('weekly', 'Weekly Digest'),
            ('never', 'Never'),
        ],
        default='never'
    )
    last_alert_sent = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used = models.DateTimeField(blank=True, null=True)
    use_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-is_default', '-last_used', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['user', 'is_default']),
        ]
        
    def save(self, *args, **kwargs):
        """Ensure only one default search per user"""
        if self.is_default:
            ApartmentSearchPreference.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
        
    def increment_use(self):
        """Track when search is used"""
        self.use_count += 1
        self.last_used = timezone.now()
        self.save(update_fields=['use_count', 'last_used'])
        
    def to_query_params(self):
        """Convert to URL query parameters"""
        params = {}
        if self.min_price: params['min_price'] = str(self.min_price)
        if self.max_price: params['max_price'] = str(self.max_price)
        if self.min_bedrooms: params['min_bedrooms'] = str(self.min_bedrooms)
        if self.max_bedrooms: params['max_bedrooms'] = str(self.max_bedrooms)
        if self.min_bathrooms: params['min_bathrooms'] = str(self.min_bathrooms)
        if self.min_square_feet: params['min_sqft'] = str(self.min_square_feet)
        if self.max_square_feet: params['max_sqft'] = str(self.max_square_feet)
        if self.neighborhoods: params['neighborhoods'] = self.neighborhoods
        if self.pets_allowed is not None: params['pets_allowed'] = '1' if self.pets_allowed else '0'
        return params
    
    def __str__(self):
        return f"{self.user.email} - {self.name}"


class ApartmentSearchHistory(models.Model):
    """
    Track user search history for analytics and personalization.
    Business Impact: Enables data-driven improvements to search and recommendations.
    Helps understand user behavior and preferences.
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='search_history',
        blank=True,
        null=True  # Allow anonymous searches
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Session ID for anonymous users"
    )
    
    # Search parameters (stored as JSON for flexibility)
    search_params = models.JSONField(
        default=dict,
        help_text="Complete search parameters used"
    )
    
    # Search text if provided
    search_text = models.TextField(
        blank=True,
        null=True,
        help_text="Free text search query"
    )
    
    # Results metadata
    results_count = models.IntegerField(
        default=0,
        help_text="Number of results returned"
    )
    results_clicked = ArrayField(
        models.IntegerField(),
        blank=True,
        default=list,
        help_text="IDs of apartments clicked from results"
    )
    
    # Location if used
    search_location = models.JSONField(
        blank=True,
        null=True,
        help_text="Location data if location-based search"
    )
    
    # Device/browser info
    user_agent = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # Search context
    search_source = models.CharField(
        max_length=50,
        choices=[
            ('homepage', 'Homepage'),
            ('listing', 'Listing Page'),
            ('saved', 'Saved Search'),
            ('alert', 'Email Alert'),
            ('api', 'API'),
            ('mobile', 'Mobile App'),
            ('other', 'Other'),
        ],
        default='listing'
    )
    
    # Performance metrics
    search_duration_ms = models.IntegerField(
        blank=True,
        null=True,
        help_text="Time to execute search in milliseconds"
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_id', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name_plural = "Search History"
        
    def add_click(self, apartment_id):
        """Record when a result is clicked"""
        if apartment_id not in self.results_clicked:
            self.results_clicked.append(apartment_id)
            self.save(update_fields=['results_clicked'])
            
    def __str__(self):
        user_str = self.user.email if self.user else f"Session {self.session_id[:8]}"
        return f"{user_str} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ApartmentSearchIndex(models.Model):
    """
    Full-text search index for apartments.
    Business Impact: Enables fast, relevant search results improving user experience.
    Uses PostgreSQL's full-text search capabilities.
    """
    apartment = models.OneToOneField(
        'Apartment',
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='search_index'
    )
    
    # Combined search vector for full-text search
    search_vector = SearchVectorField(null=True)
    
    # Denormalized fields for faster filtering
    building_name = models.CharField(max_length=255)
    building_address = models.TextField()
    neighborhood = models.CharField(max_length=50, blank=True, null=True)
    
    # Concatenated text for searching
    full_text = models.TextField(
        help_text="All searchable text concatenated"
    )
    
    # Amenities as text for searching
    amenities_text = models.TextField(blank=True, null=True)
    
    # Location for distance searches
    latitude = models.DecimalField(
        max_digits=10, 
        decimal_places=7,
        blank=True,
        null=True
    )
    longitude = models.DecimalField(
        max_digits=11, 
        decimal_places=7,
        blank=True,
        null=True
    )
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
            models.Index(fields=['neighborhood']),
            models.Index(fields=['latitude', 'longitude']),
        ]
        verbose_name = "Search Index"
        verbose_name_plural = "Search Indexes"
        
    def update_search_vector(self):
        """Update the search vector with latest content"""
        from django.contrib.postgres.search import SearchVector
        
        # Combine all searchable fields with different weights
        search_vector = (
            SearchVector('building_name', weight='A') +
            SearchVector('neighborhood', weight='B') +
            SearchVector('full_text', weight='C') +
            SearchVector('amenities_text', weight='D')
        )
        
        # Update the search vector
        ApartmentSearchIndex.objects.filter(pk=self.pk).update(
            search_vector=search_vector
        )
        
    def rebuild_index(self):
        """Rebuild the search index for this apartment"""
        apartment = self.apartment
        building = apartment.building
        
        # Update building info
        self.building_name = building.name
        self.building_address = f"{building.street_address_1} {building.city} {building.state} {building.zip_code}"
        self.neighborhood = building.get_neighborhood_display() if building.neighborhood else ""
        
        # Update location
        self.latitude = building.latitude
        self.longitude = building.longitude
        
        # Build full text
        text_parts = [
            f"Unit {apartment.unit_number}",
            self.building_name,
            self.building_address,
            self.neighborhood,
            f"{apartment.bedrooms} bedroom" if apartment.bedrooms else "",
            f"{apartment.bathrooms} bathroom" if apartment.bathrooms else "",
            f"{apartment.square_feet} sqft" if apartment.square_feet else "",
            apartment.description or "",
            apartment.get_apartment_type_display(),
        ]
        
        # Add utilities if available
        if hasattr(apartment, 'utilities'):
            utilities = apartment.utilities.get_included_utilities_list()
            if utilities:
                text_parts.append(f"Includes {', '.join(utilities)}")
                
        # Add parking info
        parking_options = apartment.parking_options.all()
        for parking in parking_options:
            text_parts.append(parking.get_parking_type_display())
            if parking.has_ev_charging:
                text_parts.append("EV charging")
                
        self.full_text = " ".join(filter(None, text_parts))
        
        # Build amenities text
        amenities = []
        amenities.extend(apartment.amenities.values_list('name', flat=True))
        amenities.extend(building.amenities.values_list('name', flat=True))
        self.amenities_text = " ".join(amenities)
        
        # Save and update search vector
        self.save()
        self.update_search_vector()
        
    def __str__(self):
        return f"Search Index: {self.apartment}"


class PopularSearchTerm(models.Model):
    """
    Track popular search terms for autocomplete and analytics.
    Business Impact: Improves search suggestions and helps understand demand.
    """
    term = models.CharField(
        max_length=255,
        unique=True,
        help_text="Search term or phrase"
    )
    search_count = models.IntegerField(
        default=0,
        help_text="Number of times searched"
    )
    click_count = models.IntegerField(
        default=0,
        help_text="Number of clicks from search results"
    )
    last_searched = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time this term was searched"
    )
    
    # Categorization
    category = models.CharField(
        max_length=50,
        choices=[
            ('neighborhood', 'Neighborhood'),
            ('amenity', 'Amenity'),
            ('building', 'Building Name'),
            ('feature', 'Feature'),
            ('price', 'Price Range'),
            ('size', 'Size/Bedrooms'),
            ('other', 'Other'),
        ],
        blank=True,
        null=True
    )
    
    # For trending analysis
    searches_this_week = models.IntegerField(default=0)
    searches_this_month = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-search_count', '-last_searched']
        indexes = [
            models.Index(fields=['term']),
            models.Index(fields=['-search_count']),
            models.Index(fields=['-last_searched']),
        ]
        
    def increment_search(self):
        """Increment search count and update timestamp"""
        self.search_count += 1
        self.searches_this_week += 1
        self.searches_this_month += 1
        self.last_searched = timezone.now()
        self.save(update_fields=[
            'search_count', 
            'searches_this_week',
            'searches_this_month',
            'last_searched'
        ])
        
    def __str__(self):
        return f"{self.term} ({self.search_count} searches)"