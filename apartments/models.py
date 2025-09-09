from django.db import models
from buildings.models import Building
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url

class ApartmentAmenity(models.Model):
    """Amenities that apply to individual apartments, separate from building amenities."""
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    


class Apartment(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="apartments")

    # Unique Identifier from External Data Source
    external_id = models.CharField(max_length=50, unique=True, blank=True, null=True)

    # Basic Apartment Info
    unit_number = models.CharField(max_length=10)
    bedrooms = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)

    APARTMENT_TYPE_CHOICES = [
        ('multi_family', 'Multi-Family'),
        ('duplex', 'Duplex'),
    ]

    apartment_type = models.CharField(
        max_length=20,
        choices=APARTMENT_TYPE_CHOICES,
        default='multi_family',
    )
    rent_price = models.DecimalField(max_digits=10, decimal_places=2)
    net_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    deposit_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
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
    
    SELF_TOUR_STATUS_CHOICES = [
        ('enabled', 'Enabled'),
        ('disabled', 'Disabled'),
    ]

    self_tour_status = models.CharField(
        max_length=10,
        choices=SELF_TOUR_STATUS_CHOICES,
        blank=True,
        null=True
    )

    lease_duration = models.CharField(max_length=50, blank=True, null=True)
    holding_deposit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    free_stuff = models.CharField(max_length=255, blank=True, null=True)
    required_documents = models.TextField(blank=True, null=True)

    # System Fields
    last_modified = models.DateTimeField(auto_now=True)

    def get_filled_fields(self):
        fields = {
            "Building": self.building.name,
            "Unit Number": self.unit_number,
            "Bedrooms": self.bedrooms,
            "Bathrooms": self.bathrooms,
            "Rent Price": f"${self.rent_price:.2f}" if self.rent_price is not None else None,
            "Net Price": f"${self.net_price:.2f}" if self.net_price is not None else None,
            "Deposit Price": f"${self.deposit_price:.2f}" if self.deposit_price is not None else None,
            "Status": self.get_status_display(),
            "Apartment Type": self.get_apartment_type_display(),
            "Lock Type": self.lock_type,
            "Broker Fee Required": "Yes" if self.broker_fee_required else "No",
            "Paid Months": self.paid_months,
            "Self Tour Status": self.get_self_tour_status_display(),
            "Lease Duration": self.lease_duration,
            "Holding Deposit": f"${self.holding_deposit:.2f}" if self.holding_deposit is not None else None,
            "Concessions": self.concessions,
            "Free Stuff": self.free_stuff,
            "Description": self.description,
            "Required Documents": self.required_documents,
        }
        return {k: v for k, v in fields.items() if v is not None}


    def __str__(self):
        return f"{self.building.name} - Unit {self.unit_number}"




class ApartmentImage(models.Model):
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image')

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
    apartment = models.ForeignKey('Apartment', on_delete=models.CASCADE, related_name='concessions')
    months_free = models.DecimalField(max_digits=3, decimal_places=1, blank=True, null=True)
    lease_terms = models.CharField(max_length=50, blank=True, null=True)
    special_offer_id = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.name or 'Concession'} - {self.months_free} months free - {self.lease_terms}"