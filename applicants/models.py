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


class Applicant(models.Model):
    # Link to User account (optional - can be created later)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='applicant_profile'
    )
    
    first_name = models.CharField(max_length=100, default="John")
    last_name = models.CharField(max_length=100, default="Doe")
    date_of_birth = models.DateField(null=True, blank=True)

    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)

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
        # Profile completeness for application readiness
        
        def is_filled(value):
            """Check if a field has meaningful content"""
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, bool):
                return True  # Boolean fields are always considered "filled"
            return bool(value)
        
        def format_value(value):
            """Format field values for display"""
            if value is None:
                return ""
            if isinstance(value, bool):
                return "Yes" if value else "No"
            if hasattr(value, 'strftime'):  # Date fields
                return value.strftime("%Y-%m-%d")
            return str(value)
        
        sections = {
            'Basic Information': {
                'fields': {
                    'first_name': {'value': self.first_name, 'required': True, 'label': 'First Name'},
                    'last_name': {'value': self.last_name, 'required': True, 'label': 'Last Name'},
                    'email': {'value': self.email, 'required': True, 'label': 'Email'},
                    'phone_number': {'value': self.phone_number, 'required': False, 'label': 'Phone Number'},
                    'date_of_birth': {'value': self.date_of_birth, 'required': False, 'label': 'Date of Birth'},
                }
            },
            'Current Address': {
                'fields': {
                    'street_address_1': {'value': self.street_address_1, 'required': False, 'label': 'Street Address 1'},
                    'street_address_2': {'value': self.street_address_2, 'required': False, 'label': 'Street Address 2'},
                    'city': {'value': self.city, 'required': False, 'label': 'City'},
                    'state': {'value': self.state, 'required': False, 'label': 'State'},
                    'zip_code': {'value': self.zip_code, 'required': False, 'label': 'Zip Code'},
                    'length_at_current_address': {'value': self.length_at_current_address, 'required': False, 'label': 'Length at Current Address'},
                    'housing_status': {'value': self.housing_status, 'required': False, 'label': 'Housing Status'},
                }
            },
            'Current Housing Details': {
                'fields': {
                    'current_landlord_name': {'value': self.current_landlord_name, 'required': False, 'label': 'Current Landlord Name'},
                    'current_landlord_phone': {'value': self.current_landlord_phone, 'required': False, 'label': 'Current Landlord Phone'},
                    'current_landlord_email': {'value': self.current_landlord_email, 'required': False, 'label': 'Current Landlord Email'},
                    'monthly_rent': {'value': self.monthly_rent, 'required': False, 'label': 'Monthly Rent'},
                    'reason_for_moving': {'value': self.reason_for_moving, 'required': False, 'label': 'Reason for Moving'},
                }
            },
            'Housing Preferences': {
                'fields': {
                    'desired_move_in_date': {'value': self.desired_move_in_date, 'required': False, 'label': 'Desired Move-in Date'},
                    'min_bedrooms': {'value': self.min_bedrooms, 'required': False, 'label': 'Min Bedrooms'},
                    'max_bedrooms': {'value': self.max_bedrooms, 'required': False, 'label': 'Max Bedrooms'},
                    'min_bathrooms': {'value': self.min_bathrooms, 'required': False, 'label': 'Min Bathrooms'},
                    'max_bathrooms': {'value': self.max_bathrooms, 'required': False, 'label': 'Max Bathrooms'},
                    'max_rent_budget': {'value': self.max_rent_budget, 'required': False, 'label': 'Max Rent Budget'},
                    'open_to_roommates': {'value': self.open_to_roommates, 'required': False, 'label': 'Open to Roommates'},
                }
            },
            'Identification': {
                'fields': {
                    'driver_license_number': {'value': self.driver_license_number, 'required': False, 'label': 'Driver License Number'},
                    'driver_license_state': {'value': self.driver_license_state, 'required': False, 'label': 'Driver License State'},
                }
            },
            'Emergency Contact': {
                'fields': {
                    'emergency_contact_name': {'value': self.emergency_contact_name, 'required': False, 'label': 'Emergency Contact Name'},
                    'emergency_contact_relationship': {'value': self.emergency_contact_relationship, 'required': False, 'label': 'Emergency Contact Relationship'},
                    'emergency_contact_phone': {'value': self.emergency_contact_phone, 'required': False, 'label': 'Emergency Contact Phone'},
                }
            },
            'Employment Information': {
                'fields': {
                    'employment_status': {'value': self.employment_status, 'required': False, 'label': 'Employment Status'},
                    'company_name': {'value': self.company_name, 'required': False, 'label': 'Company Name'},
                    'position': {'value': self.position, 'required': False, 'label': 'Position'},
                    'annual_income': {'value': self.annual_income, 'required': False, 'label': 'Annual Income'},
                    'supervisor_name': {'value': self.supervisor_name, 'required': False, 'label': 'Supervisor Name'},
                    'supervisor_email': {'value': self.supervisor_email, 'required': False, 'label': 'Supervisor Email'},
                    'supervisor_phone': {'value': self.supervisor_phone, 'required': False, 'label': 'Supervisor Phone'},
                    'currently_employed': {'value': self.currently_employed, 'required': False, 'label': 'Currently Employed'},
                    'employment_start_date': {'value': self.employment_start_date, 'required': False, 'label': 'Employment Start Date'},
                    'employment_end_date': {'value': self.employment_end_date, 'required': False, 'label': 'Employment End Date'},
                }
            },
            'Student Information': {
                'fields': {
                    'school_name': {'value': self.school_name, 'required': False, 'label': 'School Name'},
                    'year_of_graduation': {'value': self.year_of_graduation, 'required': False, 'label': 'Year of Graduation'},
                    'school_address': {'value': self.school_address, 'required': False, 'label': 'School Address'},
                    'school_phone': {'value': self.school_phone, 'required': False, 'label': 'School Phone'},
                }
            },
            'Rental History': {
                'fields': {
                    'previous_landlord_name': {'value': self.previous_landlord_name, 'required': False, 'label': 'Previous Landlord Name'},
                    'previous_landlord_contact': {'value': self.previous_landlord_contact, 'required': False, 'label': 'Previous Landlord Contact'},
                    'evicted_before': {'value': self.evicted_before, 'required': False, 'label': 'Evicted Before'},
                    'eviction_explanation': {'value': self.eviction_explanation, 'required': False, 'label': 'Eviction Explanation'},
                }
            },
            'Placement Status': {
                'fields': {
                    'placement_status': {'value': self.placement_status, 'required': False, 'label': 'Placement Status'},
                    'placement_date': {'value': self.placement_date, 'required': False, 'label': 'Placement Date'},
                }
            }
        }
        
        # Process each section
        results = {}
        overall_stats = {'total_fields': 0, 'filled_fields': 0, 'required_fields': 0, 'filled_required': 0}
        
        for section_name, section_data in sections.items():
            section_stats = {'total': 0, 'filled': 0, 'required': 0, 'filled_required': 0, 'fields': {}}
            
            for field_name, field_info in section_data['fields'].items():
                value = field_info['value']
                is_required = field_info['required']
                is_field_filled = is_filled(value)
                
                section_stats['fields'][field_name] = {
                    'label': field_info['label'],
                    'value': format_value(value),
                    'filled': is_field_filled,
                    'required': is_required,
                }
                
                section_stats['total'] += 1
                if is_field_filled:
                    section_stats['filled'] += 1
                if is_required:
                    section_stats['required'] += 1
                    if is_field_filled:
                        section_stats['filled_required'] += 1
            
            # Calculate completion percentages
            section_stats['completion_percentage'] = round((section_stats['filled'] / section_stats['total']) * 100) if section_stats['total'] > 0 else 0
            section_stats['required_completion_percentage'] = round((section_stats['filled_required'] / section_stats['required']) * 100) if section_stats['required'] > 0 else 100
            
            results[section_name] = section_stats
            
            # Update overall stats
            overall_stats['total_fields'] += section_stats['total']
            overall_stats['filled_fields'] += section_stats['filled']
            overall_stats['required_fields'] += section_stats['required']
            overall_stats['filled_required'] += section_stats['filled_required']
        
        # Add related model counts
        results['Related Data'] = {
            'fields': {
                'jobs_count': {
                    'label': 'Number of Jobs',
                    'value': self.jobs.count(),
                    'filled': self.jobs.exists(),
                    'required': False,
                },
                'income_sources_count': {
                    'label': 'Number of Income Sources',
                    'value': self.income_sources.count(),
                    'filled': self.income_sources.exists(),
                    'required': False,
                },
                'assets_count': {
                    'label': 'Number of Assets',
                    'value': self.assets.count(),
                    'filled': self.assets.exists(),
                    'required': False,
                },
                'pets_count': {
                    'label': 'Number of Pets',
                    'value': self.pets.count(),
                    'filled': self.pets.exists(),
                    'required': False,
                },
                'photos_count': {
                    'label': 'Number of Photos',
                    'value': self.photos.count(),
                    'filled': self.photos.exists(),
                    'required': False,
                },
                'previous_addresses_count': {
                    'label': 'Number of Previous Addresses',
                    'value': self.previous_addresses.count(),
                    'filled': self.previous_addresses.exists(),
                    'required': False,
                },
                'amenity_preferences_count': {
                    'label': 'Amenity Preferences Set',
                    'value': self.amenities.count(),
                    'filled': self.amenities.exists(),
                    'required': False,
                },
                'neighborhood_preferences_count': {
                    'label': 'Neighborhood Preferences Set',
                    'value': self.neighborhood_preferences.count(),
                    'filled': self.neighborhood_preferences.exists(),
                    'required': False,
                },
            },
            'total': 8,
            'filled': 0,  # Will be calculated below
            'required': 0,
            'filled_required': 0,
        }
        
        # Simplify the related data calculation
        related_filled = 0
        if self.jobs.exists(): related_filled += 1
        if self.income_sources.exists(): related_filled += 1
        if self.assets.exists(): related_filled += 1
        if self.pets.exists(): related_filled += 1
        if self.photos.exists(): related_filled += 1
        if self.previous_addresses.exists(): related_filled += 1
        if self.amenities.exists(): related_filled += 1
        if self.neighborhood_preferences.exists(): related_filled += 1
        
        results['Related Data']['filled'] = related_filled
        results['Related Data']['completion_percentage'] = round((related_filled / 8) * 100)
        results['Related Data']['required_completion_percentage'] = 100  # No required related data
        
        # Update overall stats to include related data
        overall_stats['total_fields'] += 8
        overall_stats['filled_fields'] += related_filled
        
        # Calculate overall completion percentages
        overall_stats['overall_completion_percentage'] = round((overall_stats['filled_fields'] / overall_stats['total_fields']) * 100) if overall_stats['total_fields'] > 0 else 0
        overall_stats['required_completion_percentage'] = round((overall_stats['filled_required'] / overall_stats['required_fields']) * 100) if overall_stats['required_fields'] > 0 else 100
        
        return {
            'sections': results,
            'overall': overall_stats,
            'summary': {
                'sections_count': len(results),
                'highest_completion_section': max(results.keys(), key=lambda x: results[x]['completion_percentage']),
                'lowest_completion_section': min(results.keys(), key=lambda x: results[x]['completion_percentage']),
                'fully_completed_sections': [name for name, data in results.items() if data['completion_percentage'] == 100],
                'empty_sections': [name for name, data in results.items() if data['completion_percentage'] == 0],
            }
        }
    
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
    
    def get_profile_completion_score(self):
        """
        Calculate profile completion percentage
        Business Value: Higher completion = faster approval process
        """
        fields_to_check = [
            'first_name', 'last_name', 'email', 'phone_number', 'date_of_birth',
            'street_address_1', 'city', 'state', 'zip_code',
            'min_bedrooms', 'max_bedrooms',
            'max_rent_budget'
        ]
        
        filled = sum(1 for field in fields_to_check if getattr(self, field, None))
        total = len(fields_to_check)
        
        # Add bonus points for employment info
        if self.jobs.filter(currently_employed=True).exists():
            filled += 2
            total += 2
        
        # Add bonus for preferences
        if self.neighborhood_preferences.exists():
            filled += 1
            total += 1
        
        return round((filled / total) * 100) if total > 0 else 0



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

