from django.db import models
from django.contrib.auth.models import User
from cloudinary.models import CloudinaryField
from apartments.models import Apartment
from applicants.models import Applicant
import uuid
from django.conf import settings
from encrypted_model_fields.fields import EncryptedCharField

class ApplicationStatus(models.TextChoices):
    NEW = 'NEW', 'New'
    PENDING = 'PENDING', 'Pending Review'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    WAITLISTED = 'WAITLISTED', 'Waitlisted'

class SectionStatus(models.TextChoices):
    NOT_STARTED = 'NOT_STARTED', 'Not Started'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs Review'

class RequiredDocumentType(models.TextChoices):
    # New document types for v2 system
    PHOTO_ID = 'photo_id', 'Photo ID'
    PAYSTUB = 'paystub', 'Recent Paystub'
    BANK_STATEMENT = 'bank_statement', 'Bank Statement'
    TAX_FORM = 'tax_form', '1040/1099'
    # Legacy document types for backward compatibility
    PAY_STUB = 'Pay Stub', 'Pay Stub'
    TAX_RETURN = 'Tax Return', 'Tax Return'
    RENTAL_HISTORY = 'Rental History', 'Rental History'
    OTHER = 'Other', 'Other'

    @classmethod
    def get_choices(cls):
        """Returns a list of valid document choices"""
        return [choice[0] for choice in cls.choices]

class EmploymentType(models.TextChoices):
    STUDENT = 'student', 'Student'
    EMPLOYED = 'employed', 'Employed'
    OTHER = 'other', 'Other'

class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'

class Application(models.Model):
    broker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name='applications', null=True, blank=True)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, related_name='applications', null=True, blank=True)
    
    # Manual address fields for applications without apartment relationships
    manual_building_name = models.CharField(max_length=200, blank=True, null=True, help_text="Building name if not in our database")
    manual_building_address = models.CharField(max_length=500, blank=True, null=True, help_text="Full building address")
    manual_unit_number = models.CharField(max_length=50, blank=True, null=True, help_text="Apartment/unit number")

    # Application Status
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.NEW
    )

    # Required Documents (Selected by User)
    required_documents = models.JSONField(default=list)

    unique_link = models.UUIDField(default=uuid.uuid4, unique=True)
    submitted_by_applicant = models.BooleanField(default=False)

    # Track application creation/modification
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # New fields for v2 system
    # Section Progress Tracking
    current_section = models.IntegerField(default=1)
    section_statuses = models.JSONField(default=dict)  # {1: 'completed', 2: 'in_progress', ...}
    
    # Application fee tracking
    application_fee_amount = models.DecimalField(max_digits=6, decimal_places=2, default=50.00)
    
    # Version tracking for new system
    application_version = models.CharField(max_length=10, default='v1')  # 'v1' = old, 'v2' = new
    
    # Application revocation tracking
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='revoked_applications')
    revocation_reason = models.CharField(max_length=200, blank=True, null=True)
    revocation_notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        """Ensure that required_documents only contains valid choices"""
        if isinstance(self.required_documents, list):
            self.required_documents = [doc for doc in self.required_documents if doc in RequiredDocumentType.get_choices()]
        super().save(*args, **kwargs)

    def __str__(self):
        # Handle case where applicant might not exist yet
        if self.applicant:
            applicant_name = f"{self.applicant.first_name} {self.applicant.last_name}"
        else:
            applicant_name = "Pending Applicant"
            
        if self.apartment:
            return f"Application for {applicant_name} – {self.apartment.building.name} Unit {self.apartment.unit_number}"
        else:
            building_name = self.manual_building_name or "Building"
            unit_number = self.manual_unit_number or "Unit"
            return f"Application for {applicant_name} – {building_name} {unit_number}"
    
    def get_building_display(self):
        """Returns building name for display, either from apartment or manual entry"""
        if self.apartment:
            return self.apartment.building.name
        return self.manual_building_name or "Unknown Building"
    
    def get_address_display(self):
        """Returns full address for display, either from apartment or manual entry"""
        if self.apartment:
            building = self.apartment.building
            return f"{building.street_address_1}, {building.city}, {building.state} {building.zip_code}"
        return self.manual_building_address or "Unknown Address"
    
    def get_unit_display(self):
        """Returns unit number for display, either from apartment or manual entry"""
        if self.apartment:
            return self.apartment.unit_number
        return self.manual_unit_number or "Unknown Unit"

    def is_satisfied(self):
        """
        Check if all required documents have been uploaded.
        Returns True if all requirements are met, False otherwise.
        """
        if not self.required_documents:
            return True

        uploaded_types = set(
            self.uploaded_files.values_list('document_type', flat=True)
        )
        
        # Check if every required doc is in the uploaded types
        # Note: required_documents is a list of strings (e.g. ['paystub', 'photo_id'])
        for req_doc in self.required_documents:
            if req_doc not in uploaded_types:
                return False
        
        return True


class UploadedFile(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='uploaded_files')
    file = CloudinaryField(resource_type='raw')
    document_type = models.CharField(
        max_length=50,
        choices=RequiredDocumentType.choices,
        blank=True,
        null=True
    )  # ✅ Store document type for each uploaded file

    uploaded_at = models.DateTimeField(auto_now_add=True)
    analysis_results = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)  # Track async analysis tasks 

    def __str__(self):
        return f"File for Application {self.application.id} - {self.document_type if self.document_type else 'Other'}"



class ApplicationActivity(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="activity_log")
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp} - {self.description}"


# New models for v2 5-section system

class ApplicationSection(models.Model):
    """Tracks progress and data for each section of the application"""
    
    SECTION_CHOICES = [
        (1, 'Personal Information'),
        (2, 'Income'),
        (3, 'Legal'),
        (4, 'Review'),
        (5, 'Payment'),
    ]
    
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='sections')
    section_number = models.IntegerField(choices=SECTION_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=SectionStatus.choices,
        default=SectionStatus.NOT_STARTED
    )
    
    # Store section-specific data as JSON
    data = models.JSONField(default=dict)
    
    # Validation tracking
    is_valid = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=dict)
    
    # Timestamps
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_modified = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['application', 'section_number']
        ordering = ['section_number']
    
    def __str__(self):
        return f"Application {self.application.id} - Section {self.get_section_number_display()}"


class PersonalInfoData(models.Model):
    """Section 1 - Personal Information"""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='personal_info')
    
    # Name fields
    first_name = models.CharField(max_length=100, blank=True, null=True)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    suffix = models.CharField(max_length=20, blank=True, null=True)
    
    # Contact
    email = models.EmailField(blank=True, null=True)
    phone_cell = models.CharField(max_length=20, blank=True, null=True)
    can_receive_sms = models.BooleanField(default=True)
    
    # Personal details (SSN is encrypted)
    date_of_birth = models.DateField(blank=True, null=True)
    ssn = EncryptedCharField(max_length=11, blank=True, null=True)  # Encrypted SSN field
    
    # Current address
    current_address = models.CharField(max_length=255, blank=True, null=True)
    apt_unit_number = models.CharField(max_length=50, blank=True, null=True)
    address_duration = models.CharField(max_length=50, blank=True, null=True)
    is_rental_property = models.BooleanField(default=False)
    
    # Landlord info
    landlord_name = models.CharField(max_length=100, blank=True, null=True)
    landlord_phone = models.CharField(max_length=20, blank=True, null=True)
    landlord_email = models.EmailField(blank=True, null=True)
    
    # Desired property
    desired_address = models.CharField(max_length=255, blank=True, null=True)
    desired_unit = models.CharField(max_length=50, blank=True, null=True)
    desired_move_in_date = models.DateField(blank=True, null=True)
    
    # Additional info
    referral_source = models.CharField(max_length=200, blank=True, null=True)
    has_pets = models.BooleanField(default=False)
    
    # References
    reference1_name = models.CharField(max_length=100, blank=True, null=True)
    reference1_phone = models.CharField(max_length=20, blank=True, null=True)
    reference2_name = models.CharField(max_length=100, blank=True, null=True)
    reference2_phone = models.CharField(max_length=20, blank=True, null=True)
    
    leasing_agent = models.CharField(max_length=100, blank=True, null=True)
    
    # Legal history
    has_filed_bankruptcy = models.BooleanField(default=False)
    has_criminal_conviction = models.BooleanField(default=False)
    
    about_yourself = models.TextField(blank=True, null=True)
    
    # Broker pre-fill tracking
    broker_notes = models.TextField(blank=True, null=True, help_text="Notes about broker pre-filled information")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PreviousAddress(models.Model):
    """For storing multiple previous addresses - updated to match applicant profile structure"""
    personal_info = models.ForeignKey(PersonalInfoData, on_delete=models.CASCADE, related_name='previous_addresses')
    
    # Detailed address fields (matching applicant structure)
    street_address_1 = models.CharField(max_length=255, blank=True, null=True)
    street_address_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Duration at address
    length_at_address = models.CharField(max_length=50, blank=True, null=True, help_text="How long did you live here?")
    
    # Housing status and landlord info
    housing_status = models.CharField(
        max_length=10,
        choices=[("rent", "Rent"), ("own", "Own")],
        blank=True,
        null=True,
    )
    landlord_name = models.CharField(max_length=255, blank=True, null=True)
    landlord_phone = models.CharField(max_length=20, blank=True, null=True)
    landlord_email = models.EmailField(blank=True, null=True)
    
    # Legacy fields for backward compatibility
    address = models.CharField(max_length=255, blank=True, null=True, help_text="Legacy field - use street_address_1 instead")
    apt_unit = models.CharField(max_length=50, blank=True, null=True, help_text="Legacy field - use street_address_2 instead")
    duration = models.CharField(max_length=50, blank=True, null=True, help_text="Legacy field - use length_at_address instead")
    landlord_contact = models.CharField(max_length=100, blank=True, null=True, help_text="Legacy field - use landlord_phone instead")
    
    order = models.IntegerField(default=0)  # To maintain order
    
    class Meta:
        ordering = ['order']


class IncomeData(models.Model):
    """Section 2 - Income Information"""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='income_info')
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices)
    
    # Primary employment
    company_name = models.CharField(max_length=200)
    position = models.CharField(max_length=100)
    annual_income = models.DecimalField(max_digits=10, decimal_places=2)
    supervisor_name = models.CharField(max_length=100)
    supervisor_email = models.EmailField()
    supervisor_phone = models.CharField(max_length=20)
    currently_employed = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    
    # Flags for additional data
    has_multiple_jobs = models.BooleanField(default=False)
    has_additional_income = models.BooleanField(default=False)
    has_assets = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AdditionalEmployment(models.Model):
    """For multiple jobs"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='additional_jobs')
    company_name = models.CharField(max_length=200)
    position = models.CharField(max_length=100)
    annual_income = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    is_current = models.BooleanField(default=True)


class AdditionalIncome(models.Model):
    """For non-employment income sources"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='additional_income')
    source_type = models.CharField(max_length=50)  # 'investment', 'rental', 'alimony', etc
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()


class AssetInfo(models.Model):
    """For tracking assets"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='assets')
    asset_type = models.CharField(max_length=50)  # 'savings', 'stocks', 'property', etc
    value = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()


class LegalDocuments(models.Model):
    """Section 3 - Legal Documents with E-signatures"""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='legal_docs')
    
    # NY Discrimination Form
    discrimination_form_viewed = models.BooleanField(default=False)
    discrimination_form_signed = models.BooleanField(default=False)
    discrimination_form_signature = models.CharField(max_length=200, blank=True, null=True)
    discrimination_form_signed_at = models.DateTimeField(null=True, blank=True)
    discrimination_form_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # NY Brokers Form
    brokers_form_viewed = models.BooleanField(default=False)
    brokers_form_signed = models.BooleanField(default=False)
    brokers_form_signature = models.CharField(max_length=200, blank=True, null=True)
    brokers_form_signed_at = models.DateTimeField(null=True, blank=True)
    brokers_form_ip = models.GenericIPAddressField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ApplicationPayment(models.Model):
    """Section 5 - Payment Information"""
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='payment')
    
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    
    # Payment processor fields
    payment_intent_id = models.CharField(max_length=200, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    
    # Transaction details
    paid_at = models.DateTimeField(null=True, blank=True)
    receipt_url = models.URLField(blank=True, null=True)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Refund tracking
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
