from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url

from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.conf import settings


class Amenity(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    

class Neighborhood(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class NeighborhoodPreference(models.Model):
    # Ranked neighborhood selection (1 = top choice)
    applicant = models.ForeignKey('Applicant', on_delete=models.CASCADE)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.CASCADE)
    preference_rank = models.PositiveIntegerField(help_text="1 = highest preference, higher numbers = lower preference")
    
    class Meta:
        unique_together = [
            ['applicant', 'neighborhood'],  # Each applicant can only select each neighborhood once
            ['applicant', 'preference_rank']  # Each applicant can only have one neighborhood at each rank
        ]
        ordering = ['preference_rank']
    
    def __str__(self):
        return f"{self.applicant} - {self.neighborhood} (Rank {self.preference_rank})"


class ApplicantManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('user')


class Applicant(models.Model):
    # Link to User account (optional - can be created later)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='applicant_profile'
    )
    
    objects = ApplicantManager()  # Use custom manager for optimization
    
    # Shadow fields (kept for backward compatibility and orphan records)
    _first_name = models.CharField(max_length=100, default="John", db_column="first_name")
    _last_name = models.CharField(max_length=100, default="Doe", db_column="last_name")
    _email = models.EmailField(default="john@example.com", db_column="email")
    _phone_number = models.CharField(max_length=20, default="555-555-5555", db_column="phone_number")

    @property
    def first_name(self):
        if self.user and self.user.first_name:
            return self.user.first_name
        return self._first_name

    @first_name.setter
    def first_name(self, value):
        if self.user:
            self.user.first_name = value
            self.user.save()
        self._first_name = value

    @property
    def last_name(self):
        if self.user and self.user.last_name:
            return self.user.last_name
        return self._last_name

    @last_name.setter
    def last_name(self, value):
        if self.user:
            self.user.last_name = value
            self.user.save()
        self._last_name = value

    @property
    def email(self):
        if self.user and self.user.email:
            return self.user.email
        return self._email

    @email.setter
    def email(self, value):
        if self.user:
            self.user.email = value
            self.user.save()
        self._email = value

    @property
    def phone_number(self):
        if self.user and self.user.phone_number:
            return self.user.phone_number
        return self._phone_number

    @phone_number.setter
    def phone_number(self, value):
        if self.user:
            self.user.phone_number = value
            self.user.save()
        self._phone_number = value

    @property
    def formatted_phone(self):
        """Returns phone number in (xxx) xxx-xxxx format"""
        if not self.phone_number:
            return None
        
        # Remove non-digit characters
        digits = ''.join(filter(str.isdigit, str(self.phone_number)))
        
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
            
        return self.phone_number

    date_of_birth = models.DateField(null=True, blank=True)

    # Address Details
    street_address_1 = models.CharField(max_length=255, blank=True, null=True)
    street_address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)

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

    state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)

    # Address duration tracking
    length_at_current_address = models.CharField(max_length=50, blank=True, null=True)  # Legacy field for backward compatibility
    current_address_years = models.IntegerField(
        blank=True, null=True, 
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    current_address_months = models.IntegerField(
        blank=True, null=True, 
        validators=[MinValueValidator(0), MaxValueValidator(11)]
    )
    
    housing_status = models.CharField(
        max_length=10,
        choices=[("rent", "Rent"), ("own", "Own")],
        blank=True,
        null=True,
    ) 
    current_landlord_name = models.CharField(max_length=255, blank=True, null=True)
    current_landlord_phone = models.CharField(max_length=20, blank=True, null=True)
    current_landlord_email = models.EmailField(blank=True, null=True)
    reason_for_moving = models.TextField(blank=True, null=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Identification
    driver_license_number = models.CharField(max_length=50, blank=True, null=True)
    driver_license_state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True, null=True)

    # Amenities Preferences
    amenities = models.ManyToManyField(Amenity, blank=True)

    # Keep the old field for now - we'll migrate data later
    neighborhood_preferences = models.ManyToManyField(Neighborhood, blank=True, related_name="applicants")
    
    # New ranked preferences field
    ranked_neighborhood_preferences = models.ManyToManyField(
        Neighborhood, 
        through='NeighborhoodPreference',
        blank=True, 
        related_name="ranked_applicants"
    )

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Employment & Income
    EMPLOYMENT_TYPE_CHOICES = [
        ('student', 'I am a student'),
        ('employed', 'I am employed'),
        ('other', 'Other'),
    ]
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True, null=True)
    
    
    # New detailed employment fields
    company_name = models.CharField(max_length=255, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    supervisor_name = models.CharField(max_length=100, blank=True, null=True)
    supervisor_email = models.EmailField(blank=True, null=True)
    supervisor_phone = models.CharField(max_length=20, blank=True, null=True)
    currently_employed = models.BooleanField(null=True, blank=True)
    employment_start_date = models.DateField(blank=True, null=True)
    employment_end_date = models.DateField(blank=True, null=True)
    
    # Student fields (for student status)
    school_name = models.CharField(max_length=255, blank=True, null=True)
    year_of_graduation = models.CharField(max_length=4, blank=True, null=True)
    school_address = models.TextField(blank=True, null=True)
    school_phone = models.CharField(max_length=20, blank=True, null=True)

    # Rental History
    previous_landlord_name = models.CharField(max_length=255, blank=True, null=True)
    previous_landlord_contact = models.TextField(blank=True, null=True)
    evicted_before = models.BooleanField(null=True, blank=True)
    eviction_explanation = models.TextField(blank=True, null=True)

    # Preferences
    desired_move_in_date = models.DateField(null=True, blank=True)
    # Bedroom range preferences
    min_bedrooms = models.CharField(max_length=10, blank=True, null=True, help_text="Minimum bedrooms desired")
    max_bedrooms = models.CharField(max_length=10, blank=True, null=True, help_text="Maximum bedrooms desired")
    
    # Bathroom range preferences  
    min_bathrooms = models.CharField(max_length=10, blank=True, null=True, help_text="Minimum bathrooms desired")
    max_bathrooms = models.CharField(max_length=10, blank=True, null=True, help_text="Maximum bathrooms desired")
    
    # Keep old fields for backward compatibility (will be deprecated)
    number_of_bedrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1.0, blank=True, null=True)
    number_of_bathrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1.0, blank=True, null=True)
    max_rent_budget = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    open_to_roommates = models.BooleanField(null=True, blank=True)
    has_pets = models.BooleanField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    assigned_broker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tracks if applicant found housing through system
    PLACEMENT_STATUS_CHOICES = [
        ('unplaced', 'Unplaced'),
        ('placed', 'Placed'),
        ('withdrawn', 'Withdrawn'),
    ]
    placement_status = models.CharField(max_length=20, choices=PLACEMENT_STATUS_CHOICES, blank=True, null=True)
    placement_date = models.DateTimeField(null=True, blank=True, help_text="Date when applicant was placed in an apartment")
    placed_apartment = models.ForeignKey('apartments.Apartment', on_delete=models.SET_NULL, null=True, blank=True, help_text="Apartment where applicant was placed")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_filled_fields(self):
        fields = {
            "Full Name": f"{self.first_name} {self.last_name}",
            "Date of Birth": self.date_of_birth.strftime("%B %d, %Y") if self.date_of_birth else None,
            "Desired Move-In Date": self.desired_move_in_date.strftime("%B %d, %Y") if self.desired_move_in_date else None,
            "Phone Number": self.phone_number,
            "Email": self.email,
            "Street Address 1": self.street_address_1,
            "Street Address 2": self.street_address_2,
            "City": self.city,
            "State": self.get_state_display() if self.state else None,
            "Zip Code": self.zip_code,
            "Neighborhood Preferences": ", ".join(n.name for n in self.neighborhood_preferences.all()) if self.neighborhood_preferences.exists() else None,
            "Number of Bedrooms": self.number_of_bedrooms,
            "Number of Bathrooms": self.number_of_bathrooms,
            "Max Rent Budget": f"${self.max_rent_budget}" if self.max_rent_budget else None,
            "Open to Roommates": "Yes" if self.open_to_roommates else "No",
            "Driver's License Number": self.driver_license_number,
            "Driver's License State": self.driver_license_state,
            "Amenities": ", ".join(a.name for a in self.amenities.all()) if self.amenities.exists() else None,
            "Emergency Contact Name": self.emergency_contact_name,
            "Emergency Contact Relationship": self.emergency_contact_relationship,
            "Emergency Contact Phone": self.emergency_contact_phone,
            "Company Name": self.company_name,
            "Position": self.position,
            "Annual Income": f"${self.annual_income}" if self.annual_income else None,
            "Supervisor Name": self.supervisor_name,
            "Supervisor Contact": f"{self.supervisor_email} | {self.supervisor_phone}" if self.supervisor_email or self.supervisor_phone else None,
            "Current Landlord Name": self.current_landlord_name,
            "Current Landlord Contact": self.current_landlord_contact,
            "Previous Landlord Name": self.previous_landlord_name,
            "Previous Landlord Contact": self.previous_landlord_contact,
            "Reason for Moving": self.reason_for_moving,
            "Evicted Before": "Yes" if self.evicted_before else "No",
            "Eviction Explanation": self.eviction_explanation if self.evicted_before else None,
        }
        return {k: v for k, v in fields.items() if v}  # Remove empty fields

    @property
    def current_address_duration_display(self):
        # Formats duration for tenant stability assessment
        if self.current_address_years or self.current_address_months:
            years = self.current_address_years or 0
            months = self.current_address_months or 0
            
            if years and months:
                return f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''}"
            elif years:
                return f"{years} year{'s' if years != 1 else ''}"
            elif months:
                return f"{months} month{'s' if months != 1 else ''}"
        elif self.length_at_current_address:
            # Fallback to legacy field
            return self.length_at_current_address
        return "Not specified"
    
    @property
    def total_months_at_current_address(self):
        # Converts to months for rental history scoring
        if self.current_address_years or self.current_address_months:
            years = self.current_address_years or 0
            months = self.current_address_months or 0
            return (years * 12) + months
        return None
    
    def get_field_completion_status(self):
        """
        Calculates a weighted completion status for each step of the profile.
        Used primarily for UI progress bars and guiding the applicant.
        """
        def is_filled(value):
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, bool):
                return True  # Both True and False are "filled" (explicit choices)
            return bool(value)
        
        # Step 1: Personal Info & History
        field_configs = {
            # Identity & Contact (33% of Step 1)
            'first_name': {'step': 1, 'weight': 10, 'label': 'First Name', 'value': self.first_name},
            'last_name': {'step': 1, 'weight': 10, 'label': 'Last Name', 'value': self.last_name},
            'email': {'step': 1, 'weight': 8, 'label': 'Email', 'value': self.email},
            'phone_number': {'step': 1, 'weight': 8, 'label': 'Phone Number', 'value': self.phone_number},
            'date_of_birth': {'step': 1, 'weight': 5, 'label': 'Date of Birth', 'value': self.date_of_birth},
            'profile_photo': {'step': 1, 'weight': 5, 'label': 'Profile Photo', 'value': True if self.photos.exists() else None},
            'emergency_contact_name': {'step': 1, 'weight': 4, 'label': 'Emergency Contact Name', 'value': self.emergency_contact_name},
            'emergency_contact_phone': {'step': 1, 'weight': 4, 'label': 'Emergency Contact Phone', 'value': self.emergency_contact_phone},
            
            # Housing & History (67% of Step 1)
            'street_address_1': {'step': 1, 'weight': 10, 'label': 'Street Address', 'value': self.street_address_1},
            'city': {'step': 1, 'weight': 6, 'label': 'City', 'value': self.city},
            'state': {'step': 1, 'weight': 4, 'label': 'State', 'value': self.state},
            'zip_code': {'step': 1, 'weight': 4, 'label': 'Zip Code', 'value': self.zip_code},
            'housing_status': {'step': 1, 'weight': 6, 'label': 'Housing Status', 'value': self.housing_status},
            'evicted_before': {'step': 1, 'weight': 6, 'label': 'Eviction History', 'value': self.evicted_before},
            'reason_for_moving': {'step': 1, 'weight': 5, 'label': 'Reason for Moving', 'value': self.reason_for_moving},
            'previous_addresses': {'step': 1, 'weight': 10, 'label': 'Address History', 'value': True if self.previous_addresses.exists() else None},
            'identification_documents': {'step': 1, 'weight': 10, 'label': 'ID Documents', 'value': True if self.identification_documents.exists() else None},
            
            # Step 2: Housing Needs (The Matching Core)
            'desired_move_in_date': {'step': 2, 'weight': 15, 'label': 'Desired Move-in Date', 'value': self.desired_move_in_date},
            'max_rent_budget': {'step': 2, 'weight': 15, 'label': 'Max Rent Budget', 'value': self.max_rent_budget},
            'min_bedrooms': {'step': 2, 'weight': 10, 'label': 'Min Bedrooms', 'value': self.min_bedrooms},
            'max_bedrooms': {'step': 2, 'weight': 8, 'label': 'Max Bedrooms', 'value': self.max_bedrooms},
            'min_bathrooms': {'step': 2, 'weight': 8, 'label': 'Min Bathrooms', 'value': self.min_bathrooms},
            'max_bathrooms': {'step': 2, 'weight': 5, 'label': 'Max Bathrooms', 'value': self.max_bathrooms},
            'open_to_roommates': {'step': 2, 'weight': 8, 'label': 'Roommate Preference', 'value': self.open_to_roommates},
            'pets': {'step': 2, 'weight': 8, 'label': 'Pet Information', 'value': self.has_pets if self.has_pets is not None else (True if self.pets.exists() else None)},
            'neighborhood_preferences': {'step': 2, 'weight': 15, 'label': 'Neighborhood Preferences', 'value': True if self.neighborhood_preferences.exists() else None},
            'amenities': {'step': 2, 'weight': 10, 'label': 'Amenity Preferences', 'value': True if self.amenities.exists() else None},
            
            # Step 3: Employment & Financial
            'employment_status': {'step': 3, 'weight': 15, 'label': 'Employment Status', 'value': self.employment_status},
            'income_sources': {'step': 3, 'weight': 10, 'label': 'Additional Income', 'value': True if self.income_sources.exists() else None},
            'assets': {'step': 3, 'weight': 10, 'label': 'Financial Assets', 'value': True if self.assets.exists() else None},
        }

        # Context-Aware Logic for Step 3
        is_student = self.employment_status == 'student'
        is_employed = self.employment_status == 'employed'

        if is_employed:
            field_configs.update({
                'company_name': {'step': 3, 'weight': 12, 'label': 'Company Name', 'value': self.company_name},
                'position': {'step': 3, 'weight': 12, 'label': 'Position', 'value': self.position},
                'annual_income': {'step': 3, 'weight': 15, 'label': 'Annual Income', 'value': self.annual_income},
                'supervisor_name': {'step': 3, 'weight': 8, 'label': 'Supervisor Name', 'value': self.supervisor_name},
                'currently_employed': {'step': 3, 'weight': 8, 'label': 'Employment Status (Current)', 'value': self.currently_employed},
                'employment_start_date': {'step': 3, 'weight': 10, 'label': 'Employment Start Date', 'value': self.employment_start_date},
            })
        elif is_student:
            field_configs.update({
                'school_name': {'step': 3, 'weight': 15, 'label': 'School Name', 'value': self.school_name},
                'year_of_graduation': {'step': 3, 'weight': 15, 'label': 'Expected Graduation', 'value': self.year_of_graduation},
                'school_phone': {'step': 3, 'weight': 10, 'label': 'School Phone', 'value': self.school_phone},
                'school_address': {'step': 3, 'weight': 10, 'label': 'School Address', 'value': self.school_address},
            })
        
        # Step Definitions for UI Category Display
        steps = {
            1: {'name': 'Personal Info', 'score': 0, 'max': 0, 'missing': [], 'missing_details': []}, 
            2: {'name': 'Housing Needs', 'score': 0, 'max': 0, 'missing': [], 'missing_details': []}, 
            3: {'name': 'Employment', 'score': 0, 'max': 0, 'missing': [], 'missing_details': []}
        }
        
        for field, config in field_configs.items():
            step_num = config['step']
            weight = config['weight']
            label = config['label']
            filled = is_filled(config['value'])
            
            steps[step_num]['max'] += weight
            if filled:
                steps[step_num]['score'] += weight
            else:
                steps[step_num]['missing'].append(label)
                steps[step_num]['missing_details'].append({
                    'key': field,
                    'label': label
                })
        
        # Calculate percentages and totals
        total_score = sum(s['score'] for s in steps.values())
        total_max = sum(s['max'] for s in steps.values())
        overall_pct = round((total_score / total_max) * 100) if total_max > 0 else 0
        
        for step_num in steps:
            s = steps[step_num]
            s['pct'] = round((s['score'] / s['max']) * 100) if s['max'] > 0 else 0

        return {
            'overall_completion_percentage': overall_pct,
            'steps': steps,
            'is_student': is_student,
            'is_employed': is_employed,
        }

    def get_profile_completion_score(self):
        """
        Backward compatibility wrapper. 
        DEPRECATED: Use get_field_completion_status()['overall_completion_percentage'] instead.
        """
        return self.get_field_completion_status()['overall_completion_percentage']
    
    def calculate_total_income(self):
        """
        Calculate total annual income from all sources
        Business Logic: Used for rent affordability calculations (40x rule)
        """
        total = 0
        
        # Add income from all current jobs
        for job in self.jobs.filter(currently_employed=True):
            if job.annual_income:
                total += job.annual_income
        
        # Add income from other sources (already annual)
        for source in self.income_sources.all():
            if source.average_annual_income:
                total += source.average_annual_income
        
        return total



class ApplicantPhoto(models.Model):
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='photos')
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

    def __str__(self):
        return f"Photo for {self.applicant.first_name} {self.applicant.last_name}"


class Pet(models.Model):
    PET_CHOICES = [
        ('Dog', 'Dog'),
        ('Cat', 'Cat'),
        ('Bird', 'Bird'),
        ('Rabbit', 'Rabbit'),
        ('Reptile', 'Reptile'),
        ('Other', 'Other'),
    ]

    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=100, blank=True, null=True, help_text="Pet's name")
    pet_type = models.CharField(max_length=50, choices=PET_CHOICES)
    quantity = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} {self.pet_type}(s) - {self.applicant.first_name} {self.applicant.last_name}"


class PetPhoto(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='photos')
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

    def __str__(self):
        return f"Photo for {self.pet.pet_type} owned by {self.pet.applicant.first_name} {self.pet.applicant.last_name}"


class PreviousAddress(models.Model):
    # Rental history verification data
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='previous_addresses')
    
    # Address fields (same as current address)
    street_address_1 = models.CharField(max_length=255, blank=True, null=True)
    street_address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, choices=Applicant.STATE_CHOICES, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Duration at this address
    length_at_address = models.CharField(max_length=50, blank=True, null=True, help_text="How long did you live here?")
    years = models.IntegerField(null=True, blank=True, help_text="Years at this address")
    months = models.IntegerField(null=True, blank=True, help_text="Months at this address")
    
    # Housing status and landlord info (same as current address)
    housing_status = models.CharField(
        max_length=10,
        choices=[("rent", "Rent"), ("own", "Own")],
        blank=True,
        null=True,
    )
    landlord_name = models.CharField(max_length=255, blank=True, null=True)
    landlord_phone = models.CharField(max_length=20, blank=True, null=True)
    landlord_email = models.EmailField(blank=True, null=True)

    monthly_rent = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Monthly rent at this previous address"
    )
        
    # Order for display
    order = models.PositiveIntegerField(default=1, help_text="Order of previous addresses (1=most recent)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['applicant', 'order']
    
    def __str__(self):
        address_parts = [self.street_address_1, self.city, self.state]
        address = ', '.join(filter(None, address_parts))
        return f"{self.applicant.first_name} {self.applicant.last_name} - Previous #{self.order}: {address}"


class IdentificationDocument(models.Model):
    # KYC compliance document storage
    
    ID_TYPE_CHOICES = [
        ('passport', 'Passport'),
        ('driver_license', "Driver's License"),
        ('state_id', 'State ID'),
    ]
    
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='identification_documents'
    )
    
    SIDE_CHOICES = [
        ('front', 'Front'),
        ('back', 'Back'),
        ('single', 'Single (Passport)'),
    ]
    
    id_type = models.CharField(
        max_length=20,
        choices=ID_TYPE_CHOICES,
        help_text="Type of identification document"
    )
    
    side = models.CharField(
        max_length=10,
        choices=SIDE_CHOICES,
        default='single',
        help_text="Side of the document (front/back/single)"
    )
    
    # Cloudinary fields for document images
    document_image_front = CloudinaryField(
        'image',
        folder='identification_documents/front',
        null=True,
        blank=True
    )
    
    document_image_back = CloudinaryField(
        'image',
        folder='identification_documents/back',
        null=True,
        blank=True
    )
    
    # Legacy field for backward compatibility
    document_image = CloudinaryField(
        'image',
        folder='identification_documents',
        null=True,
        blank=True
    )
    
    # Optional: Store document number for reference
    document_number = models.CharField(max_length=100, blank=True, null=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['id_type']
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.get_id_type_display()}"
    
    @property
    def thumbnail_url(self):
        """Generate a thumbnail URL for the document"""
        if self.document_image:
            url, _ = cloudinary_url(
                self.document_image.public_id,
                width=200,
                height=200,
                crop="fill",
                quality="auto"
            )
            return url
        return None
    
    @property
    def full_url(self):
        """Get full size document URL"""
        if self.document_image:
            return self.document_image.url
        return None


class ApplicationStatus(models.TextChoices):
    NEW = 'NEW', _('New')
    PENDING = 'PENDING', _('Pending Review')
    APPROVED = 'APPROVED', _('Approved')
    REJECTED = 'REJECTED', _('Rejected')
    WAITLISTED = 'WAITLISTED', _('Waitlisted')


class ApplicantCRM(models.Model):
    # Broker workflow tracking
    applicant = models.OneToOneField('Applicant', on_delete=models.CASCADE, related_name='crm', null=True, blank=True)
    assigned_broker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices, default=ApplicationStatus.NEW)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CRM for {self.applicant.first_name} {self.applicant.last_name}"


class ApplicationHistory(models.Model):
    # Audit trail for status changes
    crm = models.ForeignKey(ApplicantCRM, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=ApplicationStatus.choices)
    updated_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


    def __str__(self):
        return f"{self.crm.applicant.first_name} - {self.status} at {self.updated_at}"




class InteractionLog(models.Model):
    # Broker-applicant communication history
    crm = models.ForeignKey(ApplicantCRM, on_delete=models.CASCADE, related_name="logs")
    broker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_message = models.BooleanField(default=False)  # Separates notes from messages

    def __str__(self):
        return f"Log for {self.crm.applicant.first_name} by {self.broker.username if self.broker else 'Unknown'}"


class ApplicantActivity(models.Model):
    # Engagement tracking for broker insights
    ACTIVITY_TYPES = [
        # Profile & Registration Activities
        ('profile_created', 'Profile Created'),
        ('profile_updated', 'Profile Updated'),
        ('profile_completed', 'Profile Completed'),
        ('password_changed', 'Password Changed'),
        
        # Login & Session Activities  
        ('login', 'Logged In'),
        ('logout', 'Logged Out'),
        ('session_timeout', 'Session Timeout'),
        
        # Application Activities
        ('application_started', 'Application Started'),
        ('application_updated', 'Application Updated'),
        ('application_submitted', 'Application Submitted'),
        ('application_viewed', 'Application Viewed'),
        
        # Property & Apartment Activities
        ('apartment_viewed', 'Apartment Viewed'),
        ('apartment_favorited', 'Apartment Favorited'),
        ('apartment_unfavorited', 'Apartment Unfavorited'),
        ('building_viewed', 'Building Viewed'),
        ('property_search', 'Property Search'),
        ('virtual_tour', 'Virtual Tour Viewed'),
        
        # Communication Activities
        ('email_sent', 'Email Sent'),
        ('sms_sent', 'SMS Sent'),
        ('phone_call', 'Phone Call'),
        ('message_received', 'Message Received'),
        ('message_replied', 'Message Replied'),
        
        # Document Activities
        ('document_uploaded', 'Document Uploaded'),
        ('document_deleted', 'Document Deleted'),
        ('document_verified', 'Document Verified'),
        ('document_rejected', 'Document Rejected'),
        
        # CRM Activities (by brokers/admins)
        ('crm_note_added', 'CRM Note Added'),
        ('status_changed', 'Status Changed'),
        ('broker_assigned', 'Broker Assigned'),
        ('follow_up_scheduled', 'Follow-up Scheduled'),
        ('meeting_scheduled', 'Meeting Scheduled'),
        
        # Engagement Activities
        ('email_opened', 'Email Opened'),
        ('link_clicked', 'Link Clicked'),
        ('form_started', 'Form Started'),
        ('form_abandoned', 'Form Abandoned'),
    ]
    
    applicant = models.ForeignKey('Applicant', on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField(help_text="Human-readable description of the activity")
    
    # Context data for the activity
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional context data")
    
    # Who triggered this activity (if applicable)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="User who triggered this activity (broker, admin, or the applicant themselves)"
    )

    # Link to specific application (optional)
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities',
        help_text="Related application for this activity"
    )
    
    # System context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['applicant', '-created_at']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['triggered_by']),
        ]
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.get_activity_type_display()}"
    
    @property
    def icon_class(self):
        # UI icon mapping for activity visualization
        icon_map = {
            'profile_created': 'fas fa-user-plus',
            'profile_updated': 'fas fa-user-edit',
            'profile_completed': 'fas fa-user-check',
            'login': 'fas fa-sign-in-alt',
            'logout': 'fas fa-sign-out-alt',
            'application_started': 'fas fa-file-plus',
            'application_updated': 'fas fa-file-edit',
            'application_submitted': 'fas fa-file-check',
            'apartment_viewed': 'fas fa-home',
            'apartment_favorited': 'fas fa-heart',
            'building_viewed': 'fas fa-building',
            'property_search': 'fas fa-search',
            'virtual_tour': 'fas fa-vr-cardboard',
            'email_sent': 'fas fa-envelope',
            'sms_sent': 'fas fa-sms',
            'phone_call': 'fas fa-phone',
            'document_uploaded': 'fas fa-file-upload',
            'document_deleted': 'fas fa-trash',
            'document_verified': 'fas fa-file-check',
            'crm_note_added': 'fas fa-sticky-note',
            'status_changed': 'fas fa-exchange-alt',
            'broker_assigned': 'fas fa-user-tie',
            'meeting_scheduled': 'fas fa-calendar-plus',
        }
        return icon_map.get(self.activity_type, 'fas fa-circle')
    
    @property
    def color_class(self):
        # Color coding for activity severity
        color_map = {
            'profile_created': 'text-success',
            'profile_updated': 'text-info',
            'profile_completed': 'text-success',
            'login': 'text-primary',
            'logout': 'text-muted',
            'application_started': 'text-warning',
            'application_updated': 'text-info',
            'application_submitted': 'text-success',
            'apartment_viewed': 'text-primary',
            'apartment_favorited': 'text-danger',
            'building_viewed': 'text-info',
            'property_search': 'text-secondary',
            'email_sent': 'text-info',
            'sms_sent': 'text-success',
            'phone_call': 'text-warning',
            'document_uploaded': 'text-primary',
            'document_deleted': 'text-danger',
            'document_verified': 'text-success',
            'crm_note_added': 'text-secondary',
            'status_changed': 'text-warning',
            'broker_assigned': 'text-info',
        }
        return color_map.get(self.activity_type, 'text-muted')


class UploadedFile(models.Model):
    # File attachments for broker notes
    log = models.ForeignKey(InteractionLog, on_delete=models.CASCADE, related_name="uploaded_files")
    file = models.FileField(upload_to="interaction_logs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File for log {self.log.id}"


class ApplicantBuildingAmenityPreference(models.Model):
    # Only records amenities user actively wants
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='building_amenity_preferences')
    amenity = models.ForeignKey('buildings.Amenity', on_delete=models.CASCADE)
    
    PRIORITY_CHOICES = [
        (2, 'Nice to Have'),
        (3, 'Important'),
        (4, 'Must Have'),
    ]
    priority_level = models.IntegerField(choices=PRIORITY_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['applicant', 'amenity']
        ordering = ['-priority_level', 'amenity__name']
        verbose_name = 'Building Amenity Preference'
        verbose_name_plural = 'Building Amenity Preferences'
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.amenity.name} ({self.get_priority_level_display()})"


class ApplicantApartmentAmenityPreference(models.Model):
    # Unit-level feature requirements
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='apartment_amenity_preferences')
    amenity = models.ForeignKey('apartments.ApartmentAmenity', on_delete=models.CASCADE)
    
    PRIORITY_CHOICES = [
        (2, 'Nice to Have'),
        (3, 'Important'),
        (4, 'Must Have'),
    ]
    priority_level = models.IntegerField(choices=PRIORITY_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['applicant', 'amenity']
        ordering = ['-priority_level', 'amenity__name']
        verbose_name = 'Apartment Amenity Preference'
        verbose_name_plural = 'Apartment Amenity Preferences'
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.amenity.name} ({self.get_priority_level_display()})"


class ApplicantJob(models.Model):
    # Multiple employment verification
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='jobs')
    company_name = models.CharField(max_length=255)
    position = models.CharField(max_length=100)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    supervisor_name = models.CharField(max_length=100, blank=True, null=True)
    supervisor_email = models.EmailField(blank=True, null=True)
    supervisor_phone = models.CharField(max_length=20, blank=True, null=True)
    currently_employed = models.BooleanField(default=True)
    employment_start_date = models.DateField(blank=True, null=True)
    employment_end_date = models.DateField(blank=True, null=True)
    job_type = models.CharField(
        max_length=20, 
        choices=[
            ('student', 'Student Job'),
            ('employed', 'Additional Employment'),
        ],
        default='student'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.company_name} ({self.position})"


class ApplicantIncomeSource(models.Model):
    # Non-employment income tracking
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='income_sources')
    income_source = models.CharField(max_length=255)
    average_annual_income = models.DecimalField(max_digits=12, decimal_places=2)
    source_type = models.CharField(
        max_length=20,
        choices=[
            ('student', 'Student Income'),
            ('employed', 'Employed Income'),
            ('other', 'Other Income'),
        ],
        default='student'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.income_source} (${self.average_annual_income})"


class ApplicantAsset(models.Model):
    # Financial proof for qualification
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='assets')
    asset_name = models.CharField(max_length=255)
    account_balance = models.DecimalField(max_digits=12, decimal_places=2)
    asset_type = models.CharField(
        max_length=20,
        choices=[
            ('student', 'Student Asset'),
            ('employed', 'Employed Asset'), 
            ('other', 'Other Asset'),
        ],
        default='student'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.applicant.first_name} {self.applicant.last_name} - {self.asset_name} (${self.account_balance})"


class SavedApartment(models.Model):
    """
    Model to store apartments saved/favorited by an applicant.
    """
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='saved_apartments')
    apartment = models.ForeignKey('apartments.Apartment', on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('applicant', 'apartment')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.applicant} saved {self.apartment}"
