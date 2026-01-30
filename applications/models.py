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
    
    # Payment tracking (Application level)
    payment_completed = models.BooleanField(default=False)
    payment_completed_at = models.DateTimeField(null=True, blank=True)

    def get_total_progress(self):
        """Calculates total weighted progress across all 5 sections"""
        total = 0
        sections = self.sections.all()
        for section in sections:
            total += section.get_progress_percentage()
        return round(total / 5) if sections.exists() else 0

    def get_dynamic_status(self):
        """Returns dynamic status label for NEW applications"""
        if self.status == 'NEW' or self.status == 'New':
            return f"Not Submitted - {self.get_total_progress()}%"
        return self.get_status_display()

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

    def get_progress_percentage(self):
        """Returns a percentage score for this section based on its data model"""
        if self.status == SectionStatus.COMPLETED:
            return 100
            
        # Try to find corresponding data model
        if self.section_number == 1:
            data_model = getattr(self.application, 'personal_info', None)
        elif self.section_number == 2:
            data_model = getattr(self.application, 'income_info', None)
        elif self.section_number == 3:
            data_model = getattr(self.application, 'legal_docs', None)
        elif self.section_number == 5:
            data_model = getattr(self.application, 'payment', None)
        else:
            data_model = None

        if data_model and hasattr(data_model, 'get_completion_status'):
            return data_model.get_completion_status()
        
        return 100 if self.status == SectionStatus.COMPLETED else (20 if self.status == SectionStatus.IN_PROGRESS else 0)


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
    
    # Personal details (SSN is encrypted)
    date_of_birth = models.DateField(blank=True, null=True)
    ssn = EncryptedCharField(max_length=11, blank=True, null=True)  # Encrypted SSN field
    
    # Current address
    street_address_1 = models.CharField(max_length=255, blank=True, null=True)
    street_address_2 = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    current_address_years = models.IntegerField(default=0)
    current_address_months = models.IntegerField(default=0)
    
    # Housing status fields
    housing_status = models.CharField(max_length=50, blank=True, null=True)
    current_monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    is_rental_property = models.BooleanField(null=True, blank=True, default=None)
    reason_for_moving = models.TextField(blank=True, null=True)
    
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
    has_pets = models.BooleanField(null=True, blank=True, default=None)
    
    # References
    reference1_name = models.CharField(max_length=100, blank=True, null=True)
    reference1_phone = models.CharField(max_length=20, blank=True, null=True)
    reference2_name = models.CharField(max_length=100, blank=True, null=True)
    reference2_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Legal history
    has_filed_bankruptcy = models.BooleanField(null=True, blank=True, default=None)
    bankruptcy_explanation = models.TextField(blank=True, null=True)
    has_criminal_conviction = models.BooleanField(null=True, blank=True, default=None)
    conviction_explanation = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_completion_status(self):
        """Weighted completion for Section 1 - Comprehensive version"""
        def is_filled(val):
            if val is None: return False
            if isinstance(val, str): return bool(val.strip())
            return True

        # Base required fields
        weights = {
            'first_name': 10, 'last_name': 10, 'email': 10, 'phone_cell': 5,
            'date_of_birth': 5, 'ssn': 5,
            'street_address_1': 5, 'city': 5, 'state': 5, 'zip_code': 5,
            'current_address_years': 3, 'current_address_months': 2,
            'housing_status': 5, 'referral_source': 5,
            'reference1_name': 5, 'reference1_phone': 5,
            'has_pets': 5  # This counts as answered if answered
        }
        
        # Add conditional landlord fields if renting
        if self.housing_status == 'Rent':
            weights.update({
                'current_monthly_rent': 5,
                'landlord_name': 5,
                'landlord_phone': 2,
                'landlord_email': 3
            })
            
        score = 0
        total_weight = sum(weights.values())
        
        for field, weight in weights.items():
            if is_filled(getattr(self, field)):
                score += weight
                
        return round((score / total_weight) * 100) if total_weight > 0 else 0


class Pet(models.Model):
    PET_CHOICES = [
        ('Dog', 'Dog'),
        ('Cat', 'Cat'),
        ('Bird', 'Bird'),
        ('Rabbit', 'Rabbit'),
        ('Reptile', 'Reptile'),
        ('Other', 'Other'),
    ]

    personal_info = models.ForeignKey(PersonalInfoData, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=100, blank=True, null=True, help_text="Pet's name")
    pet_type = models.CharField(max_length=50, choices=PET_CHOICES)
    quantity = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} {self.pet_type}(s) - Application {self.personal_info.application.id}"


class PetPhoto(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='photos')
    image = CloudinaryField('image')

    def __str__(self):
        return f"Photo for {self.pet.pet_type} - Application {self.pet.personal_info.application.id}"


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
    years = models.IntegerField(null=True, blank=True, help_text="Years at this address")
    months = models.IntegerField(null=True, blank=True, help_text="Months at this address")
    
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
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
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
    employer = models.CharField(max_length=200, blank=True, null=True)
    job_title = models.CharField(max_length=100, blank=True, null=True)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    employment_length = models.CharField(max_length=100, blank=True, null=True)
    supervisor_name = models.CharField(max_length=100, blank=True, null=True)
    supervisor_email = models.EmailField(blank=True, null=True)
    supervisor_phone = models.CharField(max_length=20, blank=True, null=True)
    currently_employed = models.BooleanField(null=True, blank=True, default=None)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # Student fields
    school_name = models.CharField(max_length=200, blank=True, null=True)
    year_of_graduation = models.CharField(max_length=20, blank=True, null=True)
    school_address = models.CharField(max_length=255, blank=True, null=True)
    school_phone = models.CharField(max_length=20, blank=True, null=True)

    # Document Uploads (Application ONLY)
    paystub_1 = models.FileField(upload_to='application_docs/paystubs/', null=True, blank=True)
    paystub_2 = models.FileField(upload_to='application_docs/paystubs/', null=True, blank=True)
    paystub_3 = models.FileField(upload_to='application_docs/paystubs/', null=True, blank=True)
    bank_statement_1 = models.FileField(upload_to='application_docs/bank_statements/', null=True, blank=True)
    bank_statement_2 = models.FileField(upload_to='application_docs/bank_statements/', null=True, blank=True)
    
    # Additional income from template
    additional_income_source = models.CharField(max_length=100, blank=True, null=True)
    additional_income_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    proof_of_income = models.FileField(upload_to='application_docs/proof/', null=True, blank=True)

    # Photo ID Rollover (Application ONLY)
    id_type = models.CharField(max_length=50, blank=True, null=True) # passport, driver_license, state_id
    id_number = models.CharField(max_length=100, blank=True, null=True)
    id_state = models.CharField(max_length=50, blank=True, null=True)
    id_front_image = models.FileField(upload_to='application_docs/id_images/', null=True, blank=True)
    id_back_image = models.FileField(upload_to='application_docs/id_images/', null=True, blank=True)

    # Flags for additional data
    has_multiple_jobs = models.BooleanField(null=True, blank=True, default=None)
    has_additional_income = models.BooleanField(null=True, blank=True, default=None)
    has_assets = models.BooleanField(null=True, blank=True, default=None)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_completion_status(self):
        """Weighted completion for Section 2"""
        def is_filled(val):
            if val is None: return False
            if isinstance(val, str): return bool(val.strip())
            return True

        weights = {'employment_type': 10, 'currently_employed': 10}
        
        if self.employment_type == 'student':
            weights.update({'school_name': 30, 'year_of_graduation': 20, 'school_phone': 10, 'school_address': 20})
        else:
            weights.update({'employer': 30, 'job_title': 20, 'annual_income': 20, 'supervisor_name': 10})
            
        score = 0
        total_weight = sum(weights.values())
        
        for field, weight in weights.items():
            if is_filled(getattr(self, field)):
                score += weight
                
        return round((score / total_weight) * 100) if total_weight > 0 else 0


class AdditionalEmployment(models.Model):
    """For multiple jobs - synced with ApplicantJob"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='additional_jobs')
    company_name = models.CharField(max_length=200)
    position = models.CharField(max_length=100)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    supervisor_name = models.CharField(max_length=100, blank=True, null=True)
    supervisor_email = models.EmailField(blank=True, null=True)
    supervisor_phone = models.CharField(max_length=20, blank=True, null=True)
    currently_employed = models.BooleanField(default=True)
    employment_start_date = models.DateField(null=True, blank=True)
    employment_end_date = models.DateField(null=True, blank=True)
    job_type = models.CharField(max_length=20, default='employed') # 'employed' or 'student'


class AdditionalIncome(models.Model):
    """For non-employment income sources - synced with ApplicantIncomeSource"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='additional_income')
    income_source = models.CharField(max_length=255)
    average_annual_income = models.DecimalField(max_digits=12, decimal_places=2)
    source_type = models.CharField(max_length=50, default='other')
    description = models.TextField(blank=True, null=True)


class AssetInfo(models.Model):
    """For tracking assets - synced with ApplicantAsset"""
    income_data = models.ForeignKey(IncomeData, on_delete=models.CASCADE, related_name='assets')
    asset_name = models.CharField(max_length=255)
    account_balance = models.DecimalField(max_digits=12, decimal_places=2)
    asset_type = models.CharField(max_length=50, default='other')
    description = models.TextField(blank=True, null=True)


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

    def get_completion_status(self):
        """Simple completion for Section 3"""
        score = 0
        if self.discrimination_form_signed: score += 50
        if self.brokers_form_signed: score += 50
        return score


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

    def get_completion_status(self):
        """Payment completion"""
        return 100 if self.status == 'completed' else 0
