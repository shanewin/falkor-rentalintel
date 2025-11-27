"""
Extended models for advanced apartment features.
Business Context: Provides comprehensive property information to reduce
unnecessary inquiries and improve tenant-apartment matching.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from cloudinary.models import CloudinaryField
import datetime


class ApartmentAvailability(models.Model):
    """
    Track apartment availability timeline.
    Business Impact: Enables advance booking and reduces vacancy periods.
    Helps tenants plan moves and brokers manage pipeline.
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='availability_calendar')
    
    # Current lease information
    current_lease_end = models.DateField(
        blank=True, 
        null=True,
        help_text="When current tenant's lease ends"
    )
    
    # Availability window
    available_date = models.DateField(
        help_text="Date unit becomes available for move-in"
    )
    
    # Notice period tracking
    notice_given_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Date current tenant gave notice"
    )
    
    # Preparation time needed
    turnover_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        help_text="Days needed for cleaning/repairs between tenants"
    )
    
    # Booking status
    is_reserved = models.BooleanField(
        default=False,
        help_text="Unit is reserved but not yet rented"
    )
    reserved_until = models.DateField(
        blank=True, 
        null=True,
        help_text="Reservation expiry date"
    )
    reserved_by = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Name/ID of person holding reservation"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['available_date']
        verbose_name_plural = "Availability Calendar"
        
    def clean(self):
        """Validate availability logic"""
        super().clean()
        
        # Available date should be in the future
        if self.available_date and self.available_date < timezone.now().date():
            raise ValidationError({
                'available_date': 'Available date cannot be in the past'
            })
        
        # If reserved, must have expiry date
        if self.is_reserved and not self.reserved_until:
            raise ValidationError({
                'reserved_until': 'Reserved units must have a reservation expiry date'
            })
            
        # Current lease end should be before available date (accounting for turnover)
        if self.current_lease_end and self.available_date:
            min_available = self.current_lease_end + datetime.timedelta(days=self.turnover_days)
            if self.available_date < min_available:
                raise ValidationError({
                    'available_date': f'Available date must be at least {self.turnover_days} days after lease end'
                })
    
    def __str__(self):
        status = "Reserved" if self.is_reserved else "Available"
        return f"{self.apartment} - {status} from {self.available_date}"


class ApartmentPriceHistory(models.Model):
    """
    Track rental price changes over time.
    Business Impact: Provides pricing transparency and helps identify trends.
    Supports data-driven pricing decisions.
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='price_history')
    
    # Price information
    rent_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Monthly rent at this point in time"
    )
    net_effective_rent = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Net rent after concessions"
    )
    
    # Concession details at this price point
    concession_description = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="e.g., '2 months free on 14-month lease'"
    )
    
    # Date range for this price
    effective_date = models.DateField(help_text="Date this price became effective")
    end_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Date this price ended (null if current)"
    )
    
    # Reason for change
    CHANGE_REASONS = [
        ('market_adjustment', 'Market Adjustment'),
        ('renovation', 'Post-Renovation Increase'),
        ('seasonal', 'Seasonal Adjustment'),
        ('promotion', 'Promotional Pricing'),
        ('demand', 'Demand-Based Pricing'),
        ('new_listing', 'New Listing'),
        ('other', 'Other'),
    ]
    change_reason = models.CharField(
        max_length=20,
        choices=CHANGE_REASONS,
        blank=True,
        null=True
    )
    change_notes = models.TextField(blank=True, null=True)
    
    # Who made the change
    changed_by = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-effective_date']
        verbose_name_plural = "Price History"
        
    def save(self, *args, **kwargs):
        """Auto-close previous price record when new one is created"""
        if not self.pk:  # New record
            # Close any open price records for this apartment
            ApartmentPriceHistory.objects.filter(
                apartment=self.apartment,
                end_date__isnull=True
            ).update(end_date=self.effective_date)
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.apartment} - ${self.rent_price} ({self.effective_date})"


class ApartmentVirtualTour(models.Model):
    """
    Virtual tour links and media.
    Business Impact: Reduces unnecessary in-person tours by 40-60%.
    Enables remote leasing for out-of-state tenants.
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='virtual_tours')
    
    TOUR_TYPES = [
        ('matterport', 'Matterport 3D Tour'),
        ('video', 'Video Walkthrough'),
        ('360_photos', '360° Photos'),
        ('live_tour', 'Live Virtual Tour'),
        ('youtube', 'YouTube Video'),
        ('vimeo', 'Vimeo Video'),
        ('other', 'Other'),
    ]
    
    tour_type = models.CharField(max_length=20, choices=TOUR_TYPES)
    tour_url = models.URLField(
        max_length=500,
        help_text="URL to virtual tour"
    )
    
    # Additional metadata
    title = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Display title for the tour"
    )
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        help_text="Duration for video tours"
    )
    
    # Tracking
    is_active = models.BooleanField(default=True)
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.apartment} - {self.get_tour_type_display()}"


class ApartmentFloorPlan(models.Model):
    """
    Floor plan images and documents.
    Business Impact: Helps tenants visualize space and plan furniture placement.
    Reduces questions about layout and dimensions.
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='floor_plans')
    
    # File upload
    floor_plan_image = CloudinaryField(
        'floor_plan',
        blank=True,
        null=True,
        help_text="Floor plan image file"
    )
    floor_plan_pdf_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Link to floor plan PDF"
    )
    
    # Metadata
    title = models.CharField(
        max_length=255,
        default="Floor Plan",
        help_text="e.g., '2BR/2BA Layout A'"
    )
    
    # Dimensions
    total_square_feet = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(100), MaxValueValidator(10000)]
    )
    living_area_sqft = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(50), MaxValueValidator(5000)]
    )
    bedroom_dimensions = models.JSONField(
        blank=True,
        null=True,
        help_text="JSON object with bedroom dimensions, e.g., {'master': '15x12', 'bedroom2': '11x10'}"
    )
    
    # Display settings
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary floor plan to show first"
    )
    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', '-is_primary', 'created_at']
        
    def save(self, *args, **kwargs):
        """Ensure only one primary floor plan per apartment"""
        if self.is_primary:
            ApartmentFloorPlan.objects.filter(
                apartment=self.apartment,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.apartment} - {self.title}"


class ApartmentUtilities(models.Model):
    """
    Track utilities and what's included in rent.
    Business Impact: Clarifies total monthly cost for tenants.
    Reduces confusion about additional expenses.
    """
    apartment = models.OneToOneField(
        'Apartment', 
        on_delete=models.CASCADE, 
        related_name='utilities'
    )
    
    # What's included in rent
    water_included = models.BooleanField(default=False)
    gas_included = models.BooleanField(default=False)
    electricity_included = models.BooleanField(default=False)
    heat_included = models.BooleanField(default=False)
    hot_water_included = models.BooleanField(default=False)
    trash_included = models.BooleanField(default=True)
    sewer_included = models.BooleanField(default=True)
    internet_included = models.BooleanField(default=False)
    cable_included = models.BooleanField(default=False)
    
    # Estimated monthly costs if not included
    water_cost_estimate = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Estimated monthly water cost if not included"
    )
    gas_cost_estimate = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    electricity_cost_estimate = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)]
    )
    
    # Utility provider information
    electricity_provider = models.CharField(max_length=100, blank=True, null=True)
    gas_provider = models.CharField(max_length=100, blank=True, null=True)
    internet_providers = models.TextField(
        blank=True, 
        null=True,
        help_text="Available internet providers for the building"
    )
    
    # Additional notes
    utility_notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional information about utilities"
    )
    
    # Metering
    METER_TYPES = [
        ('individual', 'Individual Meters'),
        ('master', 'Master Metered'),
        ('submeter', 'Submetered'),
        ('rubs', 'RUBS (Ratio Utility Billing)'),
    ]
    electricity_meter_type = models.CharField(
        max_length=20,
        choices=METER_TYPES,
        blank=True,
        null=True
    )
    gas_meter_type = models.CharField(
        max_length=20,
        choices=METER_TYPES,
        blank=True,
        null=True
    )
    water_meter_type = models.CharField(
        max_length=20,
        choices=METER_TYPES,
        blank=True,
        null=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def get_total_included_value(self):
        """Calculate estimated value of included utilities"""
        total = 0
        if self.water_included and self.water_cost_estimate:
            total += self.water_cost_estimate
        if self.gas_included and self.gas_cost_estimate:
            total += self.gas_cost_estimate
        if self.electricity_included and self.electricity_cost_estimate:
            total += self.electricity_cost_estimate
        return total
    
    def get_included_utilities_list(self):
        """Return list of included utilities for display"""
        included = []
        if self.water_included: included.append("Water")
        if self.gas_included: included.append("Gas")
        if self.electricity_included: included.append("Electricity")
        if self.heat_included: included.append("Heat")
        if self.hot_water_included: included.append("Hot Water")
        if self.trash_included: included.append("Trash")
        if self.sewer_included: included.append("Sewer")
        if self.internet_included: included.append("Internet")
        if self.cable_included: included.append("Cable")
        return included
    
    def __str__(self):
        included_count = len(self.get_included_utilities_list())
        return f"{self.apartment} - {included_count} utilities included"


class ApartmentParking(models.Model):
    """
    Parking availability and pricing.
    Business Impact: Parking is a major decision factor in urban areas.
    Clear parking information reduces inquiries and speeds up decision-making.
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='parking_options')
    
    PARKING_TYPES = [
        ('garage', 'Garage'),
        ('covered', 'Covered Parking'),
        ('surface', 'Surface Lot'),
        ('street', 'Street Parking'),
        ('driveway', 'Driveway'),
        ('carport', 'Carport'),
        ('valet', 'Valet Parking'),
        ('none', 'No Parking'),
    ]
    
    parking_type = models.CharField(max_length=20, choices=PARKING_TYPES)
    
    # Availability
    spaces_included = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Number of spaces included with rent"
    )
    spaces_available = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Additional spaces available for rent"
    )
    
    # Pricing
    monthly_rate = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Monthly rate per additional space"
    )
    
    # Location details
    location_description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="e.g., 'Basement level B2' or 'Adjacent lot'"
    )
    distance_from_unit = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., 'Same building' or '100 feet'"
    )
    
    # Features
    is_assigned = models.BooleanField(
        default=False,
        help_text="Specific spots assigned vs first-come"
    )
    has_ev_charging = models.BooleanField(
        default=False,
        help_text="Electric vehicle charging available"
    )
    ev_charging_cost = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., '$30/month' or 'Included'"
    )
    
    # Access
    access_type = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., 'Key fob', 'Remote', 'Gate code'"
    )
    
    # Guest parking
    guest_parking_available = models.BooleanField(default=False)
    guest_parking_details = models.TextField(
        blank=True,
        null=True,
        help_text="Guest parking rules and availability"
    )
    
    # Size restrictions
    height_clearance = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g., '7 feet' for garages"
    )
    compact_only = models.BooleanField(
        default=False,
        help_text="Limited to compact cars"
    )
    
    # Additional details
    notes = models.TextField(blank=True, null=True)
    waitlist_available = models.BooleanField(
        default=False,
        help_text="Can join waitlist if no spaces available"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['parking_type', 'monthly_rate']
        verbose_name_plural = "Parking Options"
        
    def get_total_monthly_cost(self, additional_spaces=0):
        """Calculate total parking cost"""
        if not self.monthly_rate:
            return 0
        # Only charge for spaces beyond what's included
        chargeable_spaces = max(0, additional_spaces - self.spaces_included)
        return chargeable_spaces * self.monthly_rate
    
    def __str__(self):
        included = f"{self.spaces_included} included" if self.spaces_included else "Not included"
        return f"{self.apartment} - {self.get_parking_type_display()} ({included})"