"""
Professional Profile Models for Broker, Owner, and Staff Users
Building on the applicant profile architecture for consistency
"""

from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField
from cloudinary.utils import cloudinary_url
from django.core.validators import MinValueValidator, MaxValueValidator


class BrokerProfile(models.Model):
    """
    Professional profile for brokers with business and licensing information
    """
    # User relationship
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='broker_profile'
    )
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    mobile_phone = models.CharField(max_length=20, blank=True, null=True)
    professional_email = models.EmailField(help_text="Professional email if different from account email", blank=True, null=True)
    
    # Professional Photo
    profile_photo = CloudinaryField('image', blank=True, null=True)
    
    # Business Address
    business_name = models.CharField(max_length=200, help_text="Company or brokerage name")
    business_address_1 = models.CharField(max_length=255)
    business_address_2 = models.CharField(max_length=255, blank=True, null=True)
    business_city = models.CharField(max_length=100)
    
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
    
    business_state = models.CharField(max_length=2, choices=STATE_CHOICES, default='NY')
    business_zip = models.CharField(max_length=10)
    
    # Licensing Information
    broker_license_number = models.CharField(max_length=50, unique=True, help_text="Real estate broker license number")
    license_state = models.CharField(max_length=2, choices=STATE_CHOICES, help_text="State where licensed")
    license_expiration = models.DateField(help_text="License expiration date", blank=True, null=True)
    
    # Professional Details
    department = models.CharField(max_length=100, blank=True, null=True, help_text="Department within company")
    job_title = models.CharField(max_length=100, default="Real Estate Broker")
    years_experience = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(70)])
    
    # Specializations (can be multiple)
    SPECIALIZATION_CHOICES = [
        ('residential', 'Residential Sales'),
        ('commercial', 'Commercial Sales'),
        ('rental', 'Rental/Leasing'),
        ('luxury', 'Luxury Properties'),
        ('first_time', 'First-Time Buyers'),
        ('investment', 'Investment Properties'),
        ('relocation', 'Corporate Relocation'),
        ('property_mgmt', 'Property Management'),
        ('foreclosure', 'Foreclosure/Short Sales'),
        ('new_construction', 'New Construction'),
    ]
    specializations = models.JSONField(default=list, help_text="Areas of specialization")
    
    # Territory/Coverage Area
    territories = models.JSONField(default=list, help_text="Neighborhoods or areas covered")
    
    # Commission Information - FIX: Proper validation for percentages
    standard_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[
            MinValueValidator(0, message="Commission rate cannot be negative"),
            MaxValueValidator(100, message="Commission rate cannot exceed 100%")
        ],
        help_text="Standard commission percentage (0-100)"
    )
    commission_split = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True,
        validators=[
            MinValueValidator(0, message="Commission split cannot be negative"),
            MaxValueValidator(100, message="Commission split cannot exceed 100%")
        ],
        help_text="Broker/Agent split percentage (0-100)"
    )
    
    # Professional Bio
    bio = models.TextField(blank=True, null=True, help_text="Professional biography/description")
    
    # Certifications and Awards
    certifications = models.JSONField(default=list, help_text="Professional certifications")
    awards = models.JSONField(default=list, help_text="Awards and recognitions")
    
    # Contact Preferences
    CONTACT_PREFERENCE_CHOICES = [
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('text', 'Text/SMS'),
        ('whatsapp', 'WhatsApp'),
    ]
    preferred_contact_method = models.CharField(max_length=20, choices=CONTACT_PREFERENCE_CHOICES, default='email')
    available_hours = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 'Mon-Fri 9AM-6PM'")
    
    # Social Media/Professional Links
    linkedin_url = models.URLField(blank=True, null=True)
    website_url = models.URLField(blank=True, null=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_completed = models.BooleanField(default=False)
    completion_percentage = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Broker Profile'
        verbose_name_plural = 'Broker Profiles'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.business_name}"
    
    def get_profile_photo_url(self):
        """Get profile photo URL with proper transformation"""
        if self.profile_photo:
            url, _ = cloudinary_url(
                self.profile_photo.public_id,
                transformation=[
                    {"width": 200, "height": 200, "crop": "fill", "gravity": "face", "quality": "auto"}
                ]
            )
            return url
        return None


class OwnerProfile(models.Model):
    """
    Professional profile for property owners
    """
    # User relationship
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='owner_profile'
    )
    
    # Personal/Business Information
    OWNER_TYPE_CHOICES = [
        ('individual', 'Individual Owner'),
        ('llc', 'LLC'),
        ('corporation', 'Corporation'),
        ('partnership', 'Partnership'),
        ('trust', 'Trust'),
        ('estate', 'Estate'),
    ]
    owner_type = models.CharField(max_length=20, choices=OWNER_TYPE_CHOICES, default='individual')
    
    # Name fields (adapt based on owner type)
    first_name = models.CharField(max_length=100, help_text="First name or company representative")
    last_name = models.CharField(max_length=100, help_text="Last name or company name if business")
    company_name = models.CharField(max_length=200, blank=True, null=True, help_text="Company name if applicable")
    
    # Contact Information
    primary_phone = models.CharField(max_length=20)
    secondary_phone = models.CharField(max_length=20, blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    
    # Professional Photo
    profile_photo = CloudinaryField('image', blank=True, null=True)
    
    # Primary Address (Business or Personal)
    address_1 = models.CharField(max_length=255)
    address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, choices=BrokerProfile.STATE_CHOICES, default='NY')
    zip_code = models.CharField(max_length=10)
    
    # Mailing Address (if different)
    mailing_same_as_primary = models.BooleanField(default=True)
    mailing_address_1 = models.CharField(max_length=255, blank=True, null=True)
    mailing_address_2 = models.CharField(max_length=255, blank=True, null=True)
    mailing_city = models.CharField(max_length=100, blank=True, null=True)
    mailing_state = models.CharField(max_length=2, choices=BrokerProfile.STATE_CHOICES, blank=True, null=True)
    mailing_zip = models.CharField(max_length=10, blank=True, null=True)
    
    # Property Portfolio Information
    number_of_properties = models.PositiveIntegerField(default=0)
    total_units = models.PositiveIntegerField(default=0)
    portfolio_value = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Property Management
    MANAGEMENT_STYLE_CHOICES = [
        ('self', 'Self-Managed'),
        ('company', 'Property Management Company'),
        ('hybrid', 'Hybrid (Some Self, Some Managed)'),
    ]
    management_style = models.CharField(max_length=20, choices=MANAGEMENT_STYLE_CHOICES, default='self')
    management_company_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Tax Information
    tax_id_number = models.CharField(max_length=20, blank=True, null=True, help_text="EIN or SSN for tax purposes")
    tax_classification = models.CharField(max_length=50, blank=True, null=True)
    
    # Insurance Information
    insurance_carrier = models.CharField(max_length=100, blank=True, null=True)
    insurance_policy_number = models.CharField(max_length=50, blank=True, null=True)
    insurance_expiration = models.DateField(blank=True, null=True)
    
    # Banking Information (encrypted fields would be better in production)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_type = models.CharField(max_length=20, blank=True, null=True, choices=[
        ('checking', 'Checking'),
        ('savings', 'Savings'),
        ('business', 'Business'),
    ])
    
    # Ownership Details
    years_as_owner = models.PositiveIntegerField(default=0)
    acquisition_method = models.CharField(max_length=50, blank=True, null=True, choices=[
        ('purchase', 'Purchase'),
        ('inheritance', 'Inheritance'),
        ('gift', 'Gift'),
        ('development', 'Development'),
    ])
    
    # Contact Preferences
    preferred_contact_method = models.CharField(
        max_length=20, 
        choices=BrokerProfile.CONTACT_PREFERENCE_CHOICES, 
        default='email'
    )
    preferred_contact_time = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Professional Services
    attorney_name = models.CharField(max_length=100, blank=True, null=True)
    attorney_phone = models.CharField(max_length=20, blank=True, null=True)
    accountant_name = models.CharField(max_length=100, blank=True, null=True)
    accountant_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Additional Information
    notes = models.TextField(blank=True, null=True)
    special_instructions = models.TextField(blank=True, null=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_completed = models.BooleanField(default=False)
    completion_percentage = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Owner Profile'
        verbose_name_plural = 'Owner Profiles'
    
    def __str__(self):
        if self.company_name:
            return f"{self.company_name} ({self.first_name} {self.last_name})"
        return f"{self.first_name} {self.last_name}"


class StaffProfile(models.Model):
    """
    Administrative profile for staff members
    """
    # User relationship
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )
    
    # Personal Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
    # Contact Information
    office_phone = models.CharField(max_length=20)
    office_extension = models.CharField(max_length=10, blank=True, null=True)
    mobile_phone = models.CharField(max_length=20, blank=True, null=True)
    office_email = models.EmailField(blank=True, null=True)
    
    # Professional Photo
    profile_photo = CloudinaryField('image', blank=True, null=True)
    
    # Department and Position
    DEPARTMENT_CHOICES = [
        ('admin', 'Administration'),
        ('accounting', 'Accounting'),
        ('hr', 'Human Resources'),
        ('it', 'Information Technology'),
        ('legal', 'Legal'),
        ('marketing', 'Marketing'),
        ('operations', 'Operations'),
        ('maintenance', 'Maintenance'),
        ('customer_service', 'Customer Service'),
        ('compliance', 'Compliance'),
    ]
    department = models.CharField(max_length=30, choices=DEPARTMENT_CHOICES)
    job_title = models.CharField(max_length=100)
    
    # Employment Details
    employment_start_date = models.DateField()
    employment_type = models.CharField(max_length=20, choices=[
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
    ], default='full_time')
    
    # Office Location
    office_building = models.CharField(max_length=100, blank=True, null=True)
    office_floor = models.CharField(max_length=10, blank=True, null=True)
    office_room = models.CharField(max_length=20, blank=True, null=True)
    office_address_1 = models.CharField(max_length=255, blank=True, null=True)
    office_address_2 = models.CharField(max_length=255, blank=True, null=True)
    office_city = models.CharField(max_length=100, blank=True, null=True)
    office_state = models.CharField(max_length=2, choices=BrokerProfile.STATE_CHOICES, blank=True, null=True)
    office_zip = models.CharField(max_length=10, blank=True, null=True)
    
    # Manager Information
    reports_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )
    
    # System Access and Permissions
    ACCESS_LEVEL_CHOICES = [
        ('basic', 'Basic Access'),
        ('standard', 'Standard Access'),
        ('elevated', 'Elevated Access'),
        ('admin', 'Administrative Access'),
        ('super', 'Super Admin Access'),
    ]
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='standard')
    
    # Specific Permissions (stored as JSON array)
    system_permissions = models.JSONField(default=list, help_text="List of specific system permissions")
    
    # Detailed System Permissions (moved from AdminProfile)
    can_create_users = models.BooleanField(default=False, help_text="Can create and manage user accounts")
    can_modify_system_settings = models.BooleanField(default=False, help_text="Can modify system configurations")
    can_access_logs = models.BooleanField(default=False, help_text="Can view system logs and audit trails")
    can_manage_backups = models.BooleanField(default=False, help_text="Can manage system backups")
    can_manage_integrations = models.BooleanField(default=False, help_text="Can manage third-party integrations")
    can_view_financial_data = models.BooleanField(default=False, help_text="Can access financial reports and data")
    can_manage_notifications = models.BooleanField(default=False, help_text="Can manage system notifications")
    
    # Departments and Areas Managed
    departments_managed = models.JSONField(default=list, help_text="Departments under management")
    buildings_managed = models.JSONField(default=list, help_text="Buildings under management") 
    user_groups_managed = models.JSONField(default=list, help_text="User groups under management")
    
    # Security Settings
    security_clearance_level = models.CharField(max_length=20, choices=[
        ('standard', 'Standard'),
        ('elevated', 'Elevated'),
        ('high', 'High Security'),
        ('confidential', 'Confidential'),
    ], default='standard')
    two_factor_enabled = models.BooleanField(default=False)
    
    # Responsibilities
    primary_responsibilities = models.TextField(help_text="Main job responsibilities")
    secondary_responsibilities = models.TextField(blank=True, null=True)
    
    # Professional Information
    bio = models.TextField(blank=True, null=True)
    skills = models.JSONField(default=list, help_text="Professional skills")
    certifications = models.JSONField(default=list, help_text="Professional certifications")
    
    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_relationship = models.CharField(max_length=50, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Work Schedule
    work_schedule = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., 'Mon-Fri 9AM-5PM'")
    remote_work_allowed = models.BooleanField(default=False)
    
    # Training and Development
    training_completed = models.JSONField(default=list, help_text="Completed training programs")
    training_required = models.JSONField(default=list, help_text="Required training programs")
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_completed = models.BooleanField(default=False)
    completion_percentage = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100)])
    last_login = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['department', 'last_name']
        verbose_name = 'Staff Profile'
        verbose_name_plural = 'Staff Profiles'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.job_title}"
    
    def get_full_office_location(self):
        """Get formatted office location"""
        parts = []
        if self.office_building:
            parts.append(self.office_building)
        if self.office_floor:
            parts.append(f"Floor {self.office_floor}")
        if self.office_room:
            parts.append(f"Room {self.office_room}")
        return ", ".join(parts) if parts else "Not specified"


class AdminProfile(models.Model):
    """
    Simple personal profile for superusers (automatic full system access)
    """
    # User relationship
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_profile'
    )
    
    # ONLY basic fields as specified
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True, help_text="Job title or position")
    profile_photo = CloudinaryField('image', blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Profile'
        verbose_name_plural = 'Admin Profiles'
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.title}"
    
    def get_profile_photo_url(self):
        """Get profile photo URL with proper transformation"""
        if self.profile_photo:
            url, _ = cloudinary_url(
                self.profile_photo.public_id,
                transformation=[
                    {"width": 200, "height": 200, "crop": "fill", "gravity": "face", "quality": "auto"}
                ]
            )
            return url
        return None
    
    def is_on_call(self):
        """Check if admin is currently on call"""
        return bool(self.on_call_schedule)
    
    def get_managed_departments_display(self):
        """Get formatted list of managed departments"""
        return ", ".join(self.departments_managed) if self.departments_managed else "None"


class ProfilePhoto(models.Model):
    """
    Generic model for additional profile photos (portfolio, certifications, etc.)
    Can be linked to any profile type
    """
    # Generic relation to any profile type
    broker_profile = models.ForeignKey(BrokerProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='additional_photos')
    owner_profile = models.ForeignKey(OwnerProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='additional_photos')
    staff_profile = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='additional_photos')
    admin_profile = models.ForeignKey(AdminProfile, on_delete=models.CASCADE, null=True, blank=True, related_name='additional_photos')
    
    photo = CloudinaryField('image')
    caption = models.CharField(max_length=200, blank=True, null=True)
    photo_type = models.CharField(max_length=50, choices=[
        ('certification', 'Certification'),
        ('award', 'Award'),
        ('property', 'Property'),
        ('team', 'Team Photo'),
        ('other', 'Other'),
    ], default='other')
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Photo: {self.caption or self.photo_type}"