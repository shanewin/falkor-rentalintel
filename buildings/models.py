from django.db import models
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url
from ckeditor.fields import RichTextField



class Building(models.Model):
    name = models.CharField(max_length=255)
    street_address_1 = models.CharField(max_length=255)
    street_address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    
    STATE_CHOICES = [
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
        ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
        ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
        ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
        ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
        ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
        ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
        ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
        ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
        ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
        ('WI', 'Wisconsin'), ('WY', 'Wyoming'),
    ]

    state = models.CharField(
        max_length=2,
        choices=STATE_CHOICES,
        default='NY'
    )

    zip_code = models.CharField(max_length=20)
    
    NEIGHBORHOOD_CHOICES = [
        ('Astoria', 'Astoria'),
        ('Bedford-Stuyvesant', 'Bedford-Stuyvesant'),
        ('Boerum Hill', 'Boerum Hill'),
        ('Borough Park', 'Borough Park'),
        ('Broadway Triangle', 'Broadway Triangle'),
        ('Brookville', 'Brookville'),
        ('Brownsville', 'Brownsville'),
        ('Bushwick', 'Bushwick'),
        ('Canarsie', 'Canarsie'),
        ('Carroll Gardens', 'Carroll Gardens'),
        ('Central Harlem', 'Central Harlem'),
        ('Chelsea', 'Chelsea'),
        ('City Line', 'City Line'),
        ('Clinton Hill', 'Clinton Hill'),
        ('Cobble Hill', 'Cobble Hill'),
        ('Columbia Street Waterfront District', 'Columbia Street Waterfront District'),
        ('Crown Heights', 'Crown Heights'),
        ('Ditmas Park', 'Ditmas Park'),
        ('Downtown Brooklyn', 'Downtown Brooklyn'),
        ('East Flatbush', 'East Flatbush'),
        ('East Harlem', 'East Harlem'),
        ('East New York', 'East New York'),
        ('East Village', 'East Village'),
        ('East Williamsburg', 'East Williamsburg'),
        ('Farragut', 'Farragut'),
        ('Flatbush', 'Flatbush'),
        ('Flushing', 'Flushing'),
        ('Fort Greene', 'Fort Greene'),
        ('Gowanus', 'Gowanus'),
        ('Gravesend', 'Gravesend'),
        ('Greenpoint', 'Greenpoint'),
        ('Greenwood', 'Greenwood'),
        ('Hamilton Heights', 'Hamilton Heights'),
        ('Kensington', 'Kensington'),
        ('Lenox Hill', 'Lenox Hill'),
        ('Long Island City', 'Long Island City'),
        ('Marine Park', 'Marine Park'),
        ('Maspeth', 'Maspeth'),
        ('Midtown South', 'Midtown South'),
        ('Midwood', 'Midwood'),
        ('Mott Haven', 'Mott Haven'),
        ('Ocean Hill', 'Ocean Hill'),
        ('Park Slope', 'Park Slope'),
        ('Prospect Heights', 'Prospect Heights'),
        ('Prospect Lefferts Gardens', 'Prospect Lefferts Gardens'),
        ('Red Hook', 'Red Hook'),
        ('Ridgewood', 'Ridgewood'),
        ('Sheepshead Bay', 'Sheepshead Bay'),
        ('Southside', 'Southside'),
        ('Stuyvesant Heights', 'Stuyvesant Heights'),
        ('Sunset Park', 'Sunset Park'),
        ('Turtle Bay', 'Turtle Bay'),
        ('Vinegar Hill', 'Vinegar Hill'),
        ('Weeksville', 'Weeksville'),
        ('Williamsburg', 'Williamsburg'),
        ('Wingate', 'Wingate'),
        ('Yorkville', 'Yorkville'),
    ]

    neighborhood = models.CharField(
        max_length=100,
        choices=NEIGHBORHOOD_CHOICES,
        blank=True,
        null=True
    )

    # Screening Fee & Hold Deposit - Each has an amount + payment method
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('ach', 'ACH'),
        ('check', 'Deliver Check'),
        ('zelle', 'Zelle'),
        ('venmo', 'Venmo'),
    ]
    # Geographic Coordinates
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True, 
                                   help_text='Latitude coordinate for map display')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True,
                                    help_text='Longitude coordinate for map display')
    
    # Financial Information
    credit_screening_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    credit_screening_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)

    hold_deposit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    hold_deposit_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)

    PET_POLICY_CHOICES = [
        ('case_by_case', 'Case by Case'),
        ('pet_fee', 'Pet Fee'),
        ('all_pets', 'All pets allowed'),
        ('small_pets', 'Small pets allowed'),
        ('cats_only', 'Cats only'),
        ('no_pets', 'No pets'),
    ]
    pet_policy = models.CharField(max_length=20, choices=PET_POLICY_CHOICES, blank=True, null=True)

    amenities = models.ManyToManyField('Amenity', blank=True)

    description = RichTextField(blank=True, null=True)
    api_key = models.CharField(max_length=255, blank=True, null=True)

    owner_name = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    broker_name = models.CharField(max_length=255, blank=True, null=True)  # Keep for backwards compatibility
    brokers = models.ManyToManyField('users.User', blank=True, limit_choices_to={'is_broker': True}, related_name='buildings')

    COMMISSION_PAY_TYPE_CHOICES = [
        ('owner_pays', 'Owner Pays'),
        ('tenant_pays', 'Tenant Pays'),
        ('owner_and_tenant_pays', 'Owner and Tenant Pays'),
    ]
    commission_pay_type = models.CharField(max_length=25, choices=COMMISSION_PAY_TYPE_CHOICES, blank=True, null=True)
    commission_owner_months = models.IntegerField(blank=True, null=True)
    commission_tenant_months = models.IntegerField(blank=True, null=True)
    commission_owner_percent = models.IntegerField(blank=True, null=True)
    commission_tenant_percent = models.IntegerField(blank=True, null=True)
    commission_takeoff_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)


    internal_notes = RichTextField(blank=True, null=True)

    # Neighborhood & Lifestyle Data (cached from APIs)
    walk_score = models.IntegerField(blank=True, null=True, help_text="Walk Score (0-100)")
    walk_description = models.CharField(max_length=100, blank=True, null=True, help_text="Text description of walkability")
    bike_score = models.IntegerField(blank=True, null=True, help_text="Bike Score (0-100)")
    bike_description = models.CharField(max_length=100, blank=True, null=True, help_text="Text description of bikeability")
    transit_score = models.IntegerField(blank=True, null=True, help_text="Transit Score (0-100)")
    transit_description = models.CharField(max_length=100, blank=True, null=True, help_text="Text description of transit access")
    
    neighborhood_data_updated = models.DateTimeField(blank=True, null=True, help_text="Last time API data was updated")

    def __str__(self):
        return f"{self.name} – {self.street_address_1}, {self.city}, {self.state}"
    
    def get_filled_fields(self):
        fields = {
            "Name": self.name,
            "Street Address 1": self.street_address_1,
            "Street Address 2": self.street_address_2,
            "City": self.city,
            "State": self.get_state_display(),
            "Zip Code": self.zip_code,
            "Neighborhood": self.get_neighborhood_display() if self.neighborhood else None,
            "Credit Screening Fee": self.credit_screening_fee,
            "Credit Screening Payment Method": self.get_credit_screening_payment_method_display() if self.credit_screening_payment_method else None,
            "Hold Deposit": self.hold_deposit,
            "Hold Deposit Payment Method": self.get_hold_deposit_payment_method_display() if self.hold_deposit_payment_method else None,
            "Pet Policy": self.get_pet_policy_display() if self.pet_policy else None,
            "Owner Name": self.owner_name,
            "Company Name": self.company_name,
            "Broker Name": self.broker_name,
            "Description": self.description,
            "Internal Notes": self.internal_notes,
            "Walk Score": self.walk_score,
            "Walk Description": self.walk_description,
            "Bike Score": self.bike_score,
            "Transit Score": self.transit_score,
        }
        # Filter out fields with None or empty values
        return {k: v for k, v in fields.items() if v}
    


class Amenity(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='fa-check-circle', help_text="FontAwesome icon class (e.g. 'fa-swimming-pool')")

    def __str__(self):
        return self.name



class BuildingImage(models.Model):
    building = models.ForeignKey('Building', on_delete=models.CASCADE, related_name='images')
    image = CloudinaryField('image', blank=True, null=True)

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
        return f"Image for {self.building.name}"


class BuildingAccess(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='access_points')
    location = models.CharField(max_length=255, blank=True, null=True)
    time_restriction_enabled = models.BooleanField(default=False)
    ACCESS_TYPE_CHOICES = [
        ('pin', 'Pin Code'),
        ('note', 'Note'),
    ]

    access_type = models.CharField(max_length=10, choices=ACCESS_TYPE_CHOICES, blank=True, null=True)


    pin_code = models.CharField(max_length=20, blank=True, null=True)
    custom_note = models.TextField(blank=True, null=True)
    image = CloudinaryField('image', blank=True, null=True)

    def thumbnail_url(self):
        if self.image:
            url, _ = cloudinary_url(
                self.image.public_id,  # This gets the unique Cloudinary public ID
                format="auto",         # Auto format (e.g., WebP, AVIF if supported)
                quality="auto",        # Auto quality (e.g., q_auto)
                width=100,             # Small thumbnail (adjust size if you want)
                height=100,
                crop="fill",           # Crop to fill, avoids squishing
                gravity="auto"         # Auto focus on the subject
            )
            return url
        return None

    def __str__(self):
        return f"Access Point for {self.building.name} – {self.location}"



class BuildingSpecial(models.Model):
    building = models.ForeignKey('Building', on_delete=models.CASCADE, related_name='specials')

    SPECIAL_TYPE_CHOICES = [
        ('concession', 'Concession'),
        ('free_stuff', 'Free Stuff'),
    ]
    special_type = models.CharField(max_length=20, choices=SPECIAL_TYPE_CHOICES, blank=True, null=True)

    # Common
    name = models.CharField(max_length=255, blank=True, null=True)

    # Concession-specific fields
    months_free = models.IntegerField(blank=True, null=True)
    lease_terms = models.TextField(blank=True, null=True)
    additional_info = models.TextField(blank=True, null=True)

    # Free Stuff-specific fields (comma-separated for simplicity)
    free_stuff_items = models.CharField(max_length=255, blank=True, null=True)  # e.g., "Google Speaker,Free Netflix"

    # Time-based fields
    is_time_based = models.BooleanField(default=False)
    date_from = models.DateField(blank=True, null=True)
    date_to = models.DateField(blank=True, null=True)

    # Trigger Event
    trigger_event = models.CharField(
        max_length=25,
        choices=[
            ('application_submitted', 'Application Submitted'),
            ('lease_signed', 'Lease Signed'),
            ('move_in', 'Move In'),
        ],
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.name} ({self.get_special_type_display()}) for {self.building.name}"


class NearbySchool(models.Model):
    """
    Nearby school information cached from GreatSchools or similar API.
    Business Context: School quality is a top 3 decision factor for families.
    """
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='nearby_schools')
    name = models.CharField(max_length=255)
    rating = models.IntegerField(
        blank=True, 
        null=True, 
        help_text="GreatSchools rating (1-10)"
    )
    grades = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        help_text="e.g. 'PK-5' or '9-12'"
    )
    distance = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        help_text="Distance in miles"
    )
    school_type = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        help_text="e.g. 'Public', 'Private', 'Charter'"
    )
    
    class Meta:
        ordering = ['distance']
        unique_together = ['building', 'name']

    def __str__(self):
        return f"{self.name} ({self.rating}/10) - {self.distance} mi"
