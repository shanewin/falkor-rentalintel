from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from buildings.models import Building
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url

# Import extended models
from .models_extended import (
    ApartmentAvailability,
    ApartmentPriceHistory,
    ApartmentVirtualTour,
    ApartmentFloorPlan,
    ApartmentUtilities,
    ApartmentParking
)

# Import search models
from .search_models import (
    ApartmentSearchPreference,
    ApartmentSearchHistory,
    ApartmentSearchIndex,
    PopularSearchTerm
)

class ApartmentAmenity(models.Model):
    """Amenities that apply to individual apartments, separate from building amenities."""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='fa-check-circle', help_text="FontAwesome icon class (e.g. 'fa-swimming-pool')")

    def __str__(self):
        return self.name
    


class Apartment(models.Model):
    """
    Core rental unit model representing individual apartments
    Business Impact: Each apartment is the revenue-generating asset
    """
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="apartments")

    # Basic Apartment Info
    unit_number = models.CharField(max_length=10)
    bedrooms = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Number of bedrooms (0 for studio)"
    )
    bathrooms = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Number of bathrooms"
    )
    square_feet = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(100), MaxValueValidator(10000)],
        help_text="Living space in square feet"
    )

    APARTMENT_TYPE_CHOICES = [
        ('multi_family', 'Multi-Family'),
        ('duplex', 'Duplex'),
    ]

    apartment_type = models.CharField(
        max_length=20,
        choices=APARTMENT_TYPE_CHOICES,
        default='multi_family',
    )
    
    # Pricing Strategy Fields
    rent_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Gross rent (before concessions)"
    )
    net_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Net effective rent (after concessions)"
    )
    deposit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Security deposit amount"
    )
    description = models.TextField(blank=True, null=True)

    # Status Choices
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('pending', 'Pending'),
        ('rented', 'Rented'),
        ('unavailable', 'Unavailable'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')

    # Additional Features
    amenities = models.ManyToManyField(ApartmentAmenity, blank=True)
    lock_type = models.CharField(max_length=50, blank=True, null=True)
    broker_fee_required = models.BooleanField(default=False)
    paid_months = models.IntegerField(blank=True, null=True)
    
    lease_duration = models.CharField(max_length=50, blank=True, null=True)
    holding_deposit = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Holding deposit to reserve unit"
    )

    free_stuff = models.CharField(max_length=255, blank=True, null=True)
    required_documents = models.TextField(blank=True, null=True)

    # System Fields
    last_modified = models.DateTimeField(auto_now=True)

    @property
    def is_new(self):
        from django.utils import timezone
        created = getattr(self, 'created_at', None) or self.last_modified
        if not created:
            return False
        return (timezone.now() - created).days <= 30  # treat “new” as last 30 days for sparse data

    @property
    def has_special(self):
        try:
            concessions_exist = hasattr(self, 'concessions') and self.concessions.exists()
        except Exception:
            concessions_exist = False
        return bool(getattr(self, 'rent_specials', None) or getattr(self, 'free_stuff', None) or concessions_exist)

    @property
    def pet_policy_display(self):
        return self.building.get_pet_policy_display() if self.building and self.building.pet_policy else ''

    @property
    def available_display(self):
        return getattr(self, 'available_from', None)

    def get_filled_fields(self):
        fields = {
            "Building": self.building.name,
            "Unit Number": self.unit_number,
            "Bedrooms": self.bedrooms,
            "Bathrooms": self.bathrooms,
            "Square Feet": self.square_feet,
            "Rent Price": f"${self.rent_price:.2f}" if self.rent_price is not None else None,
            "Net Price": f"${self.net_price:.2f}" if self.net_price is not None else None,
            "Deposit Price": f"${self.deposit_price:.2f}" if self.deposit_price is not None else None,
            "Status": self.get_status_display(),
            "Apartment Type": self.get_apartment_type_display(),
            "Lock Type": self.lock_type,
            "Broker Fee Required": "Yes" if self.broker_fee_required else "No",
            "Paid Months": self.paid_months,
            "Lease Duration": self.lease_duration,
            "Holding Deposit": f"${self.holding_deposit:.2f}" if self.holding_deposit is not None else None,
            # Business Logic: Concessions are special offers (e.g., 1 month free rent)
            "Concessions": [str(c) for c in self.concessions.all()] if self.concessions.exists() else None,
            "Free Stuff": self.free_stuff,
            "Description": self.description,
            "Required Documents": self.required_documents,
        }
        return {k: v for k, v in fields.items() if v is not None}


    def clean(self):
        """
        Model-level validation for business rules.
        Business Logic: Ensures data integrity and prevents pricing errors.
        """
        super().clean()
        
        # Validate net price is not greater than rent price
        if self.net_price and self.rent_price:
            if self.net_price > self.rent_price:
                raise ValidationError({
                    'net_price': 'Net effective rent cannot be greater than gross rent price'
                })
        
        # Validate square footage is reasonable for bedroom count
        if self.square_feet and self.bedrooms is not None:
            min_sqft_per_bedroom = 200  # Business rule: minimum 200 sqft per bedroom
            if self.bedrooms > 0:
                min_expected = self.bedrooms * min_sqft_per_bedroom
                if self.square_feet < min_expected:
                    raise ValidationError({
                        'square_feet': f'Square footage seems low for {self.bedrooms} bedroom(s). Expected at least {min_expected} sqft'
                    })
            elif self.bedrooms == 0:  # Studio
                if self.square_feet < 200:
                    raise ValidationError({
                        'square_feet': 'Studio apartments should be at least 200 square feet'
                    })
        
        # Validate deposit is reasonable relative to rent
        if self.deposit_price and self.rent_price:
            max_deposit_ratio = 3  # Business rule: deposit shouldn't exceed 3x monthly rent
            if self.deposit_price > (self.rent_price * max_deposit_ratio):
                raise ValidationError({
                    'deposit_price': f'Security deposit should not exceed {max_deposit_ratio}x monthly rent'
                })
        
        # Validate bathrooms relative to bedrooms
        if self.bedrooms is not None and self.bathrooms is not None:
            if self.bedrooms > 0 and self.bathrooms > (self.bedrooms * 2):
                raise ValidationError({
                    'bathrooms': 'Number of bathrooms seems excessive for bedroom count'
                })
    
    def save(self, *args, **kwargs):
        """Override save to run full validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.building.name} - Unit {self.unit_number}"
    
    # Extended model helper methods
    def get_current_availability(self):
        """Get the current availability record"""
        return self.availability_calendar.filter(
            available_date__gte=timezone.now().date()
        ).first()
    
    def get_latest_price(self):
        """Get the current/latest price from history"""
        return self.price_history.filter(end_date__isnull=True).first()
    
    def get_primary_floor_plan(self):
        """Get the primary floor plan"""
        return self.floor_plans.filter(is_primary=True, is_active=True).first()
    
    def get_active_virtual_tours(self):
        """Get all active virtual tours"""
        return self.virtual_tours.filter(is_active=True)
    
    def get_total_monthly_cost(self, include_parking=True, parking_spaces=1):
        """
        Calculate total monthly cost including utilities and parking.
        Business Logic: Provides transparent total cost for budgeting.
        """
        total = float(self.rent_price) if self.rent_price else 0
        
        # Add parking cost if applicable
        if include_parking and self.parking_options.exists():
            primary_parking = self.parking_options.first()
            if primary_parking and primary_parking.monthly_rate:
                parking_cost = primary_parking.get_total_monthly_cost(parking_spaces)
                total += float(parking_cost)
        
        return total
    
    def is_available_on_date(self, check_date):
        """Check if apartment is available on a specific date"""
        availability = self.get_current_availability()
        if availability:
            return check_date >= availability.available_date and not availability.is_reserved
        return self.status == 'available'

    @property
    def all_images(self):
        """
        Return a combined list of apartment images and building images.
        Apartment images come first.
        """
        apartment_imgs = list(self.images.all())
        building_imgs = list(self.building.images.all()) if self.building else []
        return apartment_imgs + building_imgs

    @property
    def total_image_count(self):
        """Return the total number of images (apartment + building)"""
        count = self.images.count()
        if self.building:
            count += self.building.images.count()
        return count

    @property
    def image_url(self):
        """Standard property for templates to access main image URL"""
        first_img = self.all_images
        if first_img:
            return first_img[0].large_url()
        return None




class ApartmentImage(models.Model):
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image')

    @property
    def thumbnail_url(self):
        url, _ = cloudinary_url(
            self.image.public_id,
            transformation=[
                {"width": 300, "height": 300, "crop": "fill", "gravity": "auto", "quality": "auto", "fetch_format": "auto"}
            ],
        )
        return url

    def large_url(self):
        url, _ = cloudinary_url(
            self.image.public_id,
            transformation=[
                {"width": 1200, "height": 800, "crop": "fill", "gravity": "auto", "quality": "auto", "fetch_format": "auto"}
            ],
        )
        return url

    def custom_url(self, width, height):
        url, _ = cloudinary_url(
            self.image.public_id,
            transformation=[
                {"width": width, "height": height, "crop": "fill", "gravity": "auto", "quality": "auto", "fetch_format": "auto"}
            ],
        )
        return url

    def __str__(self):
        return f"Image for {self.apartment.building.name} - Unit {self.apartment.unit_number}"


class ApartmentConcession(models.Model):
    """
    Rental incentives to attract tenants and fill vacancies
    Business Impact: Reduces net effective rent to compete in market
    Example: "2 months free on 14-month lease" or "No broker fee"
    """
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='concessions')
    months_free = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(12)],
        help_text="Number of free months offered"
    )
    lease_terms = models.CharField(max_length=50, blank=True, null=True)  # e.g., "12-month lease required"
    special_offer_id = models.IntegerField(blank=True, null=True)  # External system tracking ID
    name = models.CharField(max_length=100, blank=True, null=True)  # Marketing name for the offer
    
    def clean(self):
        """Validate concession logic"""
        super().clean()
        
        # Ensure months_free doesn't exceed reasonable limits
        if self.months_free and self.months_free > 3:
            # Business rule: More than 3 months free requires manager approval
            # This is a warning, not a hard stop
            pass  # Could trigger notification to management here

    def __str__(self):
        return f"{self.name or 'Concession'} - {self.months_free} months free - {self.lease_terms}"


class BrokerInquiry(models.Model):
    INQUIRY_TYPE_CHOICES = [
        ('request_tour', 'Schedule a Tour'),
        ('ask_question', 'Ask a Question'),
    ]

    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='inquiries')
    applicant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_inquiries')
    broker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_inquiries')
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    
    inquiry_type = models.CharField(max_length=20, choices=INQUIRY_TYPE_CHOICES)
    message = models.TextField(blank=True, null=True)
    preferred_times = models.JSONField(default=list, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Inquiry from {self.name} for {self.apartment}"
