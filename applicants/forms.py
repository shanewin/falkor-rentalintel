from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator, EmailValidator
from django.utils.html import escape
from django.core.cache import cache
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import os

# Safe import for python-magic
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("python-magic not installed. File type detection will be limited to extension checking.")
from .models import Applicant, ApplicantPhoto, Pet, PetPhoto, Amenity, Neighborhood, InteractionLog
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Field, Div, Submit, HTML
from crispy_forms.bootstrap import InlineCheckboxes
from cloudinary.forms import CloudinaryFileField

# Security validators and file validation
def validate_image_file(file):
    """Validate uploaded image files for security"""
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024
    if file.size > max_size:
        raise ValidationError(f"File size must be under 10MB. Current size: {file.size / (1024*1024):.1f}MB")
    
    # Check file type using python-magic (MIME type detection) if available
    if MAGIC_AVAILABLE:
        try:
            file_mime = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)  # Reset file pointer
            
            allowed_types = [
                'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
            ]
            
            if file_mime not in allowed_types:
                raise ValidationError(f"Invalid file type: {file_mime}. Only JPEG, PNG, GIF, and WebP images are allowed.")
                
        except Exception as e:
            raise ValidationError("Unable to verify file type. Please ensure this is a valid image file.")
    
    # Check file extension
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_extension = os.path.splitext(file.name)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise ValidationError(f"Invalid file extension: {file_extension}. Allowed: {', '.join(allowed_extensions)}")
    
    # Check for suspicious file patterns
    file.seek(0)
    file_content = file.read(512)  # Read first 512 bytes
    file.seek(0)
    
    # Look for script tags, executable headers, etc.
    suspicious_patterns = [
        b'<script', b'javascript:', b'vbscript:', b'onload=', b'onclick=',
        b'MZ', b'PK',  # PE and ZIP headers (executables)
    ]
    
    for pattern in suspicious_patterns:
        if pattern in file_content:
            raise ValidationError("File contains suspicious content and cannot be uploaded.")

def validate_phone_number(value):
    """Validate phone number format"""
    if not value:
        return  # Optional field
    
    # Remove common formatting
    cleaned = ''.join(char for char in value if char.isdigit())
    
    # Check length (10 or 11 digits for US)
    if len(cleaned) not in [10, 11]:
        raise ValidationError("Phone number must be 10 or 11 digits.")
    
    # Check for valid US phone pattern
    if len(cleaned) == 11 and not cleaned.startswith('1'):
        raise ValidationError("11-digit phone numbers must start with 1.")

def validate_email_domain(value):
    """Enhanced email validation with domain checking"""
    if not value:
        return  # Optional field
    
    # Basic Django validation first
    EmailValidator()(value)
    
    # Check for suspicious domains
    blocked_domains = [
        '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
        'mailinator.com', 'yopmail.com', '33mail.com'
    ]
    
    domain = value.split('@')[1].lower() if '@' in value else ''
    if domain in blocked_domains:
        raise ValidationError("Temporary email addresses are not allowed.")

def validate_currency_amount(value):
    """Validate currency amounts with reasonable limits"""
    if value is None:
        return  # Optional field
    
    if value < 0:
        raise ValidationError("Amount cannot be negative.")
    
    # Set reasonable limits for rent budget (max $50,000/month)
    if value > 50000:
        raise ValidationError("Maximum budget allowed is $50,000 per month.")
    
    # Check for suspiciously low amounts that might indicate data entry errors
    if value > 0 and value < 100:
        raise ValidationError("Minimum budget is $100 per month.")

def sanitize_text_input(value):
    """Sanitize text input to prevent XSS"""
    if not value:
        return value
    
    # HTML escape the input
    sanitized = escape(value)
    
    # Additional checks for malicious patterns
    dangerous_patterns = [
        'javascript:', 'data:', 'vbscript:', 'onclick', 'onload', 
        'onerror', 'onmouseover', '<script', '</script>'
    ]
    
    value_lower = value.lower()
    for pattern in dangerous_patterns:
        if pattern in value_lower:
            raise ValidationError("Input contains potentially unsafe content.")
    
    return sanitized

def validate_birth_date(value):
    """Validate date of birth - must be 18+ and in the past"""
    if not value:
        return  # Optional field
    
    today = date.today()
    
    # Check if date is in the future
    if value > today:
        raise ValidationError("Date of birth cannot be in the future.")
    
    # Calculate age
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    
    # Check minimum age (18)
    if age < 18:
        raise ValidationError("You must be at least 18 years old to apply.")
    
    # Check maximum reasonable age (120)
    if age > 120:
        raise ValidationError("Please check your date of birth - age appears to be over 120 years.")

def validate_move_in_date(value):
    """Validate move-in date - must be reasonable future date"""
    if not value:
        return  # Optional field
    
    today = date.today()
    
    # Check if date is in the past
    if value < today:
        raise ValidationError("Move-in date cannot be in the past.")
    
    # Check if date is too far in future (2 years max)
    max_future_date = today + timedelta(days=730)  # 2 years
    if value > max_future_date:
        raise ValidationError("Move-in date cannot be more than 2 years in the future.")

def validate_employment_dates(start_date, end_date):
    """Validate employment date range"""
    if not start_date or not end_date:
        return  # Both dates must be provided for validation
    
    if end_date < start_date:
        raise ValidationError("Employment end date must be after start date.")
    
    # Check for unreasonably long employment (50 years max)
    if (end_date - start_date).days > (50 * 365):
        raise ValidationError("Employment duration cannot exceed 50 years.")

def check_rate_limit(user_identifier, form_type='form_submission'):
    """Basic rate limiting - max 10 submissions per minute"""
    cache_key = f"rate_limit:{form_type}:{user_identifier}"
    
    # Get current submission count
    current_count = cache.get(cache_key, 0)
    
    # Check if limit exceeded
    if current_count >= 10:
        raise ValidationError(
            "Too many form submissions. Please wait a minute before trying again."
        )
    
    # Increment counter with 60 second expiry
    cache.set(cache_key, current_count + 1, 60)

def validate_bedroom_range(min_bedrooms, max_bedrooms):
    """Validate bedroom range logic"""
    if not min_bedrooms or not max_bedrooms:
        return  # Optional fields
    
    # Convert to numbers for comparison
    try:
        min_val = float(min_bedrooms) if min_bedrooms != '' else 0
        max_val = float(max_bedrooms) if max_bedrooms != '' else 999
        
        if min_val > max_val:
            raise ValidationError("Maximum bedrooms must be greater than or equal to minimum bedrooms.")
            
    except (ValueError, TypeError):
        # Invalid values will be caught by field validation
        pass

def validate_bathroom_range(min_bathrooms, max_bathrooms):
    """Validate bathroom range logic"""
    if not min_bathrooms or not max_bathrooms:
        return  # Optional fields
    
    # Convert to numbers for comparison
    try:
        min_val = float(min_bathrooms) if min_bathrooms != '' else 0
        max_val = float(max_bathrooms) if max_bathrooms != '' else 999
        
        if min_val > max_val:
            raise ValidationError("Maximum bathrooms must be greater than or equal to minimum bathrooms.")
            
    except (ValueError, TypeError):
        # Invalid values will be caught by field validation
        pass

# Multi-step forms for progressive profile completion

class SecureImageField(forms.FileField):
    """Secure file field with validation for image uploads"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('validators', []).append(validate_image_file)
        super().__init__(*args, **kwargs)

class ApplicantBasicInfoForm(forms.ModelForm):
    """Step 1: Basic Information Form"""
    
    # Add secure file fields for ID documents
    profile_photo = SecureImageField(required=False)
    passport_document = SecureImageField(required=False)
    driver_license_front = SecureImageField(required=False)
    driver_license_back = SecureImageField(required=False)
    state_id_front = SecureImageField(required=False)
    state_id_back = SecureImageField(required=False)
    
    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'phone_number', 'email',
            'street_address_1', 'street_address_2', 'city', 'state', 'zip_code',
            'current_address_years', 'current_address_months',
            'housing_status', 'current_landlord_name', 'current_landlord_phone', 'current_landlord_email',
            'monthly_rent', 'reason_for_moving',
            'date_of_birth', 'driver_license_number', 'driver_license_state',
            'evicted_before', 'eviction_explanation',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'state': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select State'
            }),
            'driver_license_state': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': "Driver's License State"
            }),
            'monthly_rent': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'text',
                'placeholder': 'Monthly Rent'
            }),
            'reason_for_moving': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Tell us a bit about why you are moving'
            }),
        }


    def clean(self):
        """Cross-field validation and rate limiting"""
        cleaned_data = super().clean()
        
        # Rate limiting - use IP + user ID if available
        request = getattr(self, 'request', None)
        if request:
            user_identifier = request.META.get('REMOTE_ADDR', 'unknown')
            if request.user.is_authenticated:
                user_identifier = f"{user_identifier}:{request.user.id}"
            
            try:
                check_rate_limit(user_identifier, 'basic_info_form')
            except ValidationError as e:
                self.add_error(None, e)
        
        return cleaned_data

    def clean_monthly_rent(self):
        """Allow comma-formatted currency input for monthly rent"""
        raw_value = self.data.get('monthly_rent')
        if raw_value:
            try:
                return Decimal(raw_value.replace(',', ''))
            except InvalidOperation:
                pass
        return self.cleaned_data.get('monthly_rent')

    def __init__(self, *args, **kwargs):
        # Extract request for rate limiting
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Add security validators to text fields
        self.fields['first_name'].validators.append(sanitize_text_input)
        self.fields['last_name'].validators.append(sanitize_text_input)
        self.fields['email'].validators.append(validate_email_domain)
        self.fields['phone_number'].validators.append(validate_phone_number)
        
        # Add length limits to prevent database overflow
        self.fields['first_name'].widget.attrs.update({'maxlength': 50})
        self.fields['last_name'].widget.attrs.update({'maxlength': 50})
        self.fields['street_address_1'].widget.attrs.update({'maxlength': 100})
        self.fields['street_address_2'].widget.attrs.update({'maxlength': 100})
        self.fields['city'].widget.attrs.update({'maxlength': 50})
        self.fields['zip_code'].widget.attrs.update({'maxlength': 10})
        
        # Apply sanitization to address fields
        for field_name in ['street_address_1', 'street_address_2', 'city', 'current_landlord_name', 
                          'current_landlord_email', 'eviction_explanation', 'reason_for_moving',
                          'emergency_contact_name', 'emergency_contact_relationship',
                          'driver_license_number']:
            if field_name in self.fields:
                self.fields[field_name].validators.append(sanitize_text_input)
        
        # Add date validation
        if 'date_of_birth' in self.fields:
            self.fields['date_of_birth'].validators.append(validate_birth_date)
        
        if 'emergency_contact_phone' in self.fields:
            self.fields['emergency_contact_phone'].validators.append(validate_phone_number)
        
        if 'monthly_rent' in self.fields:
            self.fields['monthly_rent'].validators.append(validate_currency_amount)
        
        # Only first_name, last_name, and email are required
        required_fields = ['first_name', 'last_name', 'email']
        for field_name, field in self.fields.items():
            if field_name not in required_fields:
                field.required = False
            
            # Remove label suffixes
            field.label_suffix = ''
            if field.required:
                field.widget.attrs['required'] = 'required'
        
        # Setup dropdown choices for duration fields
        year_choices = [('', 'Years')] + [(i, f'{i} year{"s" if i != 1 else ""}') for i in range(0, 21)]
        month_choices = [('', 'Months')] + [(i, f'{i} month{"s" if i != 1 else ""}') for i in range(0, 12)]
        
        self.fields['current_address_years'].widget = forms.Select(
            choices=year_choices,
            attrs={'class': 'form-select select2', 'data-placeholder': 'Years'}
        )
        self.fields['current_address_years'].label = ''
        
        self.fields['current_address_months'].widget = forms.Select(
            choices=month_choices,
            attrs={'class': 'form-select select2', 'data-placeholder': 'Months'}
        )
        self.fields['current_address_months'].label = ''

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            # Profile Photo Section
            HTML('''
            <div class="mb-4 profile-photo-section">
                <label class="form-label">Profile Photo</label>
                <div class="row align-items-center">
                    <div class="col-auto">
                        <div class="profile-photo-container position-relative">
                            {% if form.instance.photos.all %}
                                <img src="{{ form.instance.photos.first.thumbnail_url }}" 
                                     alt="Profile Photo" 
                                     class="preview-image rounded-circle border border-2 border-warning" 
                                     width="120" 
                                     height="120" 
                                     style="object-fit: cover;">
                            {% else %}
                                <div class="image-placeholder bg-light rounded-circle border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                     style="width: 120px; height: 120px;">
                                    <i class="fas fa-user fa-3x text-muted"></i>
                                </div>
                            {% endif %}
                        </div>
                    </div>
                    <div class="col">
                        <h6 class="mb-2">Upload Your Profile Photo</h6>
                        <p class="text-muted small mb-3">Choose a professional photo that represents you well. Accepted formats: JPG, PNG, GIF (max 10MB)</p>
                        
                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                            <button type="button" 
                                    class="btn btn-primary btn-sm"
                                    onclick="document.getElementById('id_profile_photo').click()">
                                <i class="fas fa-camera"></i> Upload Photo
                            </button>
                        </div>
                        
                        <input type="file" 
                               name="profile_photo" 
                               id="id_profile_photo" 
                               accept="image/*"
                               style="display: none;"
                               class="form-control">
                               
                        <!-- Crop transformation data -->
                        <input type="hidden" id="crop-data" name="crop_data" value="">
                    </div>
                </div>
            </div>
            '''),
            
            Fieldset(
                'Personal Information',
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('phone_number', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
            ),
            
            Fieldset(
                'Current Address',
                Row(
                    Column('street_address_1', css_class='col-md-8'),
                    Column('street_address_2', css_class='col-md-4'),
                ),
                Row(
                    Column('city', css_class='col-md-5'),
                    Column('state', css_class='col-md-3'),
                    Column('zip_code', css_class='col-md-4'),
                ),
                HTML('''
                <label class="form-label">
                    How long have you lived at your current address? 
                    <i class="fas fa-info-circle text-success ms-1" 
                       data-bs-toggle="tooltip" 
                       data-bs-placement="right" 
                       title="Important for rental application">
                    </i>
                </label>
                '''),
                Row(
                    Column(Field('current_address_years', label=False), css_class='col-md-2'),
                    Column(Field('current_address_months', label=False), css_class='col-md-2'),
                    Column(css_class='col-md-8'),
                ),
                Div(
                    HTML('''
                    <div class="form-check mb-3">
                        <input class="form-check-input" type="checkbox" id="is_rental_checkbox" name="is_rental_checkbox">
                        <label class="form-check-label" for="is_rental_checkbox">
                            Is this a Rental?
                        </label>
                    </div>
                    '''),
                    Field('housing_status', type="hidden"),
                    Div(
                        Row(
                            Column(Field('current_landlord_name', placeholder="Landlord's Name"), css_class='col-md-4'),
                            Column(Field('current_landlord_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                            Column(Field('current_landlord_email', placeholder="Landlord's Email"), css_class='col-md-4'),
                        ),
                        css_id='rental_landlord_fields',
                        css_class='d-none mb-2'
                    ),
                    Div(
                        HTML('''
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label" for="{{ form.monthly_rent.id_for_label }}">Monthly Rent</label>
                                    <div class="input-group">
                                        <span class="input-group-text">$</span>
                                        <input type="text"
                                               name="{{ form.monthly_rent.html_name }}"
                                               id="{{ form.monthly_rent.id_for_label }}"
                                               class="form-control currency-input"
                                               value="{{ form.monthly_rent.value|default_if_none:'' }}"
                                               placeholder="1,200.00">
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12 mb-3">
                                <label class="form-label" for="{{ form.reason_for_moving.id_for_label }}">Reason for Moving</label>
                                {{ form.reason_for_moving }}
                            </div>
                        </div>
                        '''),
                        css_id='rental_additional_fields',
                        css_class='d-none mb-2'
                    ),
                    css_id='current_rental_container',
                ),
                HTML('''
                <div class="mt-2">
                    <button type="button" id="add-previous-address-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Previous Address
                    </button>
                    <i class="fas fa-info-circle text-success ms-2" 
                       data-bs-toggle="tooltip" 
                       data-bs-placement="right" 
                       title="Adding previous addresses improves your rental application and helps with placement">
                    </i>
                </div>
                <div id="previous-addresses-container">
                    <!-- Dynamic previous address forms will be added here -->
                </div>
                '''),
            ),
            
            HTML('''
            <div class="mb-3">
                <label class="form-label">
                    Have you ever been evicted before?
                    <i class="fas fa-info-circle text-success ms-2" 
                       data-bs-toggle="tooltip" 
                       data-bs-placement="right" 
                       title="Important for rental application">
                    </i>
                </label>
                <div class="form-check">
                    <input class="form-check-input" type="radio" id="id_evicted_before_yes" name="evicted_before" value="True" {% if form.evicted_before.value == True %}checked{% endif %}>
                    <label class="form-check-label" for="id_evicted_before_yes">
                        Yes
                    </label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="radio" id="id_evicted_before_no" name="evicted_before" value="False" {% if form.evicted_before.value == False %}checked{% endif %}>
                    <label class="form-check-label" for="id_evicted_before_no">
                        No
                    </label>
                </div>
            </div>
            <div id="eviction_explanation_field" class="mb-3 {% if not form.evicted_before.value %}d-none{% endif %}">
                <label class="form-label" for="id_eviction_explanation">Please explain the circumstances:</label>
                <textarea class="form-control" id="id_eviction_explanation" name="eviction_explanation" rows="3" placeholder="Briefly describe what happened and what you learned from the experience...">{{ form.eviction_explanation.value|default:'' }}</textarea>
            </div>
            '''),

            Fieldset(
                'Identification',
                Row(
                    Column('date_of_birth', css_class='col-md-4'),
                ),
                HTML('''
                <div class="mt-3">
                    <label class="form-label">
                        Select Identification Type(s)
                        <i class="fas fa-question-circle text-muted ms-2" 
                           data-bs-toggle="tooltip" 
                           data-bs-placement="right" 
                           title="At least one form of identification with photos is required for your application. Uploading multiple types (such as Driver's License AND Passport) will help us process your application faster and improve your chances of approval.">
                        </i>
                    </label>
                    <div class="id-type-checkboxes">
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="passport" id="id_passport" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_passport" style="padding-top: 2px;">
                                <i class="fas fa-passport"></i> Passport
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="driver_license" id="id_driver_license" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_driver_license" style="padding-top: 2px;">
                                <i class="fas fa-id-card"></i> Driver's License
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="state_id" id="id_state_id" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_state_id" style="padding-top: 2px;">
                                <i class="fas fa-id-badge"></i> State ID
                            </label>
                        </div>
                    </div>
                </div>
                '''),
                Row(
                    Column(Field('driver_license_number', placeholder="Driver's License Number"), css_class='col-md-4 driver-license-field d-none'),
                    Column('driver_license_state', css_class='col-md-4 driver-license-field d-none'),
                ),
                HTML('''
                <!-- Upload sections that will be shown/hidden based on selection -->
                <div id="passport_upload" class="id-upload-section mt-3" style="display: none;">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="mb-3"><i class="fas fa-passport"></i> Upload Passport</h6>
                            <div class="row align-items-center">
                                <div class="col-auto">
                                    <div class="passport-container position-relative">
                                        <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                             style="width: 200px; height: 125px;">
                                            <i class="fas fa-passport fa-3x text-muted"></i>
                                        </div>
                                    </div>
                                </div>
                                <div class="col">
                                    <p class="text-muted small mb-3">Upload a clear photo of your passport</p>
                                    <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                        <button type="button" class="btn btn-primary btn-sm"
                                                onclick="document.getElementById('id_passport_document').click()">
                                            <i class="fas fa-camera"></i> Upload Passport
                                        </button>
                                    </div>
                                    <input type="file" name="passport_document" id="id_passport_document" 
                                           accept="image/*" style="display: none;" class="form-control">
                                    <input type="hidden" id="crop-data-passport" name="crop_data_passport" value="">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="driver_license_upload" class="id-upload-section mt-3" style="display: none;">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="mb-3"><i class="fas fa-id-card"></i> Upload Driver's License</h6>
                            
                            <!-- Front of Driver's License -->
                            <div class="mb-4">
                                <label class="form-label fw-bold">Front of Driver's License</label>
                                <div class="row align-items-center">
                                    <div class="col-auto">
                                        <div class="driver-license-front-container position-relative">
                                            <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                 style="width: 200px; height: 125px;">
                                                <i class="fas fa-id-card fa-3x text-muted"></i>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <p class="text-muted small mb-3">Upload a clear photo of the front of your driver's license</p>
                                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                            <button type="button" class="btn btn-primary btn-sm"
                                                    onclick="document.getElementById('id_driver_license_front').click()">
                                                <i class="fas fa-camera"></i> Upload Front
                                            </button>
                                        </div>
                                        <input type="file" name="driver_license_front" id="id_driver_license_front" 
                                               accept="image/*" style="display: none;" class="form-control">
                                        <input type="hidden" id="crop-data-driver-front" name="crop_data_driver_front" value="">
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Back of Driver's License -->
                            <div class="mb-3">
                                <label class="form-label fw-bold">Back of Driver's License</label>
                                <div class="row align-items-center">
                                    <div class="col-auto">
                                        <div class="driver-license-back-container position-relative">
                                            <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                 style="width: 200px; height: 125px;">
                                                <i class="fas fa-id-card fa-3x text-muted"></i>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <p class="text-muted small mb-3">Upload a clear photo of the back of your driver's license</p>
                                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                            <button type="button" class="btn btn-primary btn-sm"
                                                    onclick="document.getElementById('id_driver_license_back').click()">
                                                <i class="fas fa-camera"></i> Upload Back
                                            </button>
                                        </div>
                                        <input type="file" name="driver_license_back" id="id_driver_license_back" 
                                               accept="image/*" style="display: none;" class="form-control">
                                        <input type="hidden" id="crop-data-driver-back" name="crop_data_driver_back" value="">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div id="state_id_upload" class="id-upload-section mt-3" style="display: none;">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="mb-3"><i class="fas fa-id-badge"></i> Upload State ID</h6>
                            
                            <!-- Front of State ID -->
                            <div class="mb-4">
                                <label class="form-label fw-bold">Front of State ID</label>
                                <div class="row align-items-center">
                                    <div class="col-auto">
                                        <div class="state-id-front-container position-relative">
                                            <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                 style="width: 200px; height: 125px;">
                                                <i class="fas fa-id-badge fa-3x text-muted"></i>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <p class="text-muted small mb-3">Upload a clear photo of the front of your state ID</p>
                                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                            <button type="button" class="btn btn-primary btn-sm"
                                                    onclick="document.getElementById('id_state_id_front').click()">
                                                <i class="fas fa-camera"></i> Upload Front
                                            </button>
                                        </div>
                                        <input type="file" name="state_id_front" id="id_state_id_front" 
                                               accept="image/*" style="display: none;" class="form-control">
                                        <input type="hidden" id="crop-data-state-front" name="crop_data_state_front" value="">
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Back of State ID -->
                            <div class="mb-3">
                                <label class="form-label fw-bold">Back of State ID</label>
                                <div class="row align-items-center">
                                    <div class="col-auto">
                                        <div class="state-id-back-container position-relative">
                                            <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                 style="width: 200px; height: 125px;">
                                                <i class="fas fa-id-badge fa-3x text-muted"></i>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <p class="text-muted small mb-3">Upload a clear photo of the back of your state ID</p>
                                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                            <button type="button" class="btn btn-primary btn-sm"
                                                    onclick="document.getElementById('id_state_id_back').click()">
                                                <i class="fas fa-camera"></i> Upload Back
                                            </button>
                                        </div>
                                        <input type="file" name="state_id_back" id="id_state_id_back" 
                                               accept="image/*" style="display: none;" class="form-control">
                                        <input type="hidden" id="crop-data-state-back" name="crop_data_state_back" value="">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                '''),
            ),
            
            Fieldset(
                'Emergency Contact',
                Row(
                    Column(Field('emergency_contact_name', placeholder="Full Name"), css_class='col-md-4'),
                    Column(Field('emergency_contact_relationship', placeholder="Relationship"), css_class='col-md-4'),
                    Column(Field('emergency_contact_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                ),
            ),
        )


class ApplicantHousingForm(forms.ModelForm):
    """Step 2: Housing Needs and Preferences Form"""
    
    BEDROOM_CHOICES = [
        ('', 'Any'),
        ('studio', 'Studio (0)'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5+', '5+'),
    ]
    
    BATHROOM_CHOICES = [
        ('', 'Any'),
        ('1', '1'),
        ('1.5', '1.5'),
        ('2', '2'),
        ('2.5', '2.5'),
        ('3', '3'),
        ('3.5', '3.5'),
        ('4', '4'),
        ('5+', '5+'),
    ]
    
    class Meta:
        model = Applicant
        fields = [
            'desired_move_in_date', 'min_bedrooms', 'max_bedrooms', 'min_bathrooms', 'max_bathrooms',
            'max_rent_budget', 'open_to_roommates',
            'amenities',
        ]
        widgets = {
            'desired_move_in_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'max_rent_budget': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '2500.00',
                'min': '100',
                'max': '50000'
            }),
        }

    def __init__(self, *args, **kwargs):
        # Extract request for rate limiting
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Add currency validation to budget field
        if 'max_rent_budget' in self.fields:
            self.fields['max_rent_budget'].validators.append(validate_currency_amount)

        # Set up bedroom range dropdowns
        self.fields['min_bedrooms'] = forms.ChoiceField(
            choices=self.BEDROOM_CHOICES,
            required=False,
            label='Minimum Bedrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        self.fields['max_bedrooms'] = forms.ChoiceField(
            choices=self.BEDROOM_CHOICES,
            required=False,
            label='Maximum Bedrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        
        # Set up bathroom range dropdowns
        self.fields['min_bathrooms'] = forms.ChoiceField(
            choices=self.BATHROOM_CHOICES,
            required=False,
            label='Minimum Bathrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        self.fields['max_bathrooms'] = forms.ChoiceField(
            choices=self.BATHROOM_CHOICES,
            required=False,
            label='Maximum Bathrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )

        # Multiple selections
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = Amenity.objects.all()
        
        # Remove neighborhood_preferences from rendered fields since we're using custom HTML
        if 'neighborhood_preferences' in self.fields:
            del self.fields['neighborhood_preferences']
        
        # Store neighborhood choices for the template
        from .models import Neighborhood
        self.neighborhood_choices = Neighborhood.objects.all().order_by('name')
        
        # Store building and apartment amenities for the template
        from buildings.models import Amenity as BuildingAmenity
        from apartments.models import ApartmentAmenity
        self.building_amenities = BuildingAmenity.objects.all().order_by('name')
        self.apartment_amenities = ApartmentAmenity.objects.all().order_by('name')
        
        # All fields are optional
        for field_name, field in self.fields.items():
            field.required = False
            field.label_suffix = ''
        
        # Friendly labels
        if 'reason_for_moving' in self.fields:
            self.fields['reason_for_moving'].label = 'Reason for Moving'

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            Fieldset(
                'Housing Needs',
                Row(
                    Column(Field('desired_move_in_date'), css_class='col-md-6 mb-4'),
                    Column(Field('max_rent_budget', template='applicants/currency_field.html'), css_class='col-md-6 mb-4'),
                ),
                HTML('''
                <div class="row mb-4">
                    <div class="col-md-6 mb-4">
                        <label class="form-label">Number of Bedrooms</label>
                        <div class="d-flex align-items-center">
                            <span class="me-2">FROM:</span>
                            <div class="me-3" style="flex: 1;">
                                {{ form.min_bedrooms }}
                            </div>
                            <span class="me-2">TO:</span>
                            <div style="flex: 1;">
                                {{ form.max_bedrooms }}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6 d-flex align-items-end mb-4">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="open_to_roommates" id="{{ form.open_to_roommates.id_for_label }}" style="width: 1.5em; height: 1.5em; transform: scale(1.2);" {% if form.open_to_roommates.value %}checked{% endif %}>
                            <label class="form-check-label ms-3" for="{{ form.open_to_roommates.id_for_label }}" style="font-size: 1.1rem; font-weight: 500; padding-top: 4px;">
                                Open to Roommates?
                            </label>
                        </div>
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col-md-6 mb-4">
                        <label class="form-label">Number of Bathrooms</label>
                        <div class="d-flex align-items-center">
                            <span class="me-2">FROM:</span>
                            <div class="me-3" style="flex: 1;">
                                {{ form.min_bathrooms }}
                            </div>
                            <span class="me-2">TO:</span>
                            <div style="flex: 1;">
                                {{ form.max_bathrooms }}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Pets Section -->
                <div class="row mb-2">
                    <div class="col-md-12">
                        <div class="form-check mb-2">
                            <input class="form-check-input pets-checkbox" type="checkbox" id="has_pets" name="has_pets" style="width: 1.5em; height: 1.5em; transform: scale(1.2);">
                            <label class="form-check-label ms-3" for="has_pets" style="font-size: 1.1rem; font-weight: 500; padding-top: 4px;">
                                Pets?
                            </label>
                        </div>
                        
                        <!-- Pet Details Container (initially hidden) -->
                        <div id="pets-container" class="mt-4" style="display: none;">
                            <div class="mb-4">
                                <button type="button" id="add-pet-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                                    <i class="fas fa-plus"></i> Add Pet
                                </button>
                            </div>
                            <div id="pets-list-container">
                                <!-- Dynamic pet forms will be added here -->
                                <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                            </div>
                        </div>
                    </div>
                </div>
                '''),
            ),
            
            Fieldset(
                'HOUSING PREFERENCES',
                HTML('''
                <div class="mb-4">
                    <h6 class="mb-3">Neighborhood Preferences</h6>
                    <p class="text-muted small mb-3">
                        <i class="fas fa-info-circle"></i> Select your preferred neighborhoods and drag them to rank by priority. 
                        Your #1 choice will have the highest priority in our apartment matching algorithm.
                    </p>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <h6 class="text-secondary small mb-2">Available Neighborhoods</h6>
                            <div id="available-neighborhoods" class="neighborhood-list border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                {% for neighborhood in all_neighborhoods %}
                                <div class="neighborhood-item available" data-neighborhood-id="{{ neighborhood.id }}" draggable="true">
                                    <span class="neighborhood-name">{{ neighborhood.name }}</span>
                                    <i class="fas fa-plus text-success float-end"></i>
                                </div>
                                {% empty %}
                                <p class="text-danger">No neighborhoods found!</p>
                                {% endfor %}
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <h6 class="text-secondary small mb-2">Your Ranked Preferences</h6>
                            <div id="selected-neighborhoods" class="neighborhood-list border rounded p-3" style="min-height: 300px;">
                                <div class="text-muted text-center py-4" id="empty-message">
                                    <i class="fas fa-hand-pointer mb-2"></i><br>
                                    Click neighborhoods from the left to add them here, then drag to reorder by preference.
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Hidden inputs to store the ranked preferences -->
                    <div id="neighborhood-preferences-inputs"></div>
                </div>
                '''),
                HTML('''
                <!-- Building Amenities Section -->
                <div class="mb-5">
                    <div class="d-flex align-items-center mb-3">
                        <h5 class="mb-0 me-3">Building Amenities</h5>
                        <small class="text-muted">
                            <i class="fas fa-info-circle"></i> 
                            Set priorities for building-wide amenities. Only select amenities that matter to you.
                        </small>
                    </div>
                    
                    <!-- Priority Legend -->
                    <div class="priority-legend mb-4 p-3 bg-light rounded">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color unset-legend"></div>
                                    <small><strong>Don't Care</strong><br>Not important</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color nice-to-have-legend"></div>
                                    <small><strong>Nice to Have</strong><br>Mild preference</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color very-important-legend"></div>
                                    <small><strong>Important</strong><br>Strong preference</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color must-have-legend"></div>
                                    <small><strong>Must Have</strong><br>Deal-breaker if missing</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="amenities-grid" id="building-amenities">
                        {% for amenity in all_building_amenities %}
                        <div class="amenity-slider-item unset" data-amenity-id="{{ amenity.id }}" data-amenity-type="building">
                            <div class="amenity-info">
                                <div class="d-flex align-items-center">
                                    {% if amenity.name == "Bike Room" %}
                                        <i class="fa-solid fa-bicycle me-2 text-warning"></i>
                                    {% elif amenity.name == "Business center" %}
                                        <i class="fa-solid fa-briefcase me-2 text-warning"></i>
                                    {% elif amenity.name == "Children's Play Room" %}
                                        <i class="fa-solid fa-child me-2 text-warning"></i>
                                    {% elif amenity.name == "Cold Storage" %}
                                        <i class="fa-regular fa-snowflake me-2 text-warning"></i>
                                    {% elif amenity.name == "Concierge" %}
                                        <i class="fa-solid fa-bell-concierge me-2 text-warning"></i>
                                    {% elif amenity.name == "Courtyard" %}
                                        <i class="fa-solid fa-tree me-2 text-warning"></i>
                                    {% elif amenity.name == "Covered parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Doorman" %}
                                        <i class="fa-solid fa-door-closed me-2 text-warning"></i>
                                    {% elif amenity.name == "Elevator" %}
                                        <i class="fa-solid fa-arrows-up-down me-2 text-warning"></i>
                                    {% elif amenity.name == "Fitness Center" %}
                                        <i class="fa-solid fa-dumbbell me-2 text-warning"></i>
                                    {% elif amenity.name == "Gym" %}
                                        <i class="fa-solid fa-dumbbell me-2 text-warning"></i>
                                    {% elif amenity.name == "Garage Parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Garbage chute" %}
                                        <i class="fa-solid fa-trash me-2 text-warning"></i>
                                    {% elif amenity.name == "Garden" %}
                                        <i class="fa-solid fa-seedling me-2 text-warning"></i>
                                    {% elif amenity.name == "Green building" %}
                                        <i class="fa-solid fa-leaf me-2 text-warning"></i>
                                    {% elif amenity.name == "Guarantors Welcome" %}
                                        <i class="fa-regular fa-file-signature me-2 text-warning"></i>
                                    {% elif amenity.name == "Laundry In Building" %}
                                        <i class="fa-solid fa-soap me-2 text-warning"></i>
                                    {% elif amenity.name == "Live In Super" %}
                                        <i class="fa-solid fa-screwdriver-wrench me-2 text-warning"></i>
                                    {% elif amenity.name == "Locker Rooms" %}
                                        <i class="fa-solid fa-lock me-2 text-warning"></i>
                                    {% elif amenity.name == "Media Room" %}
                                        <i class="fa-solid fa-tv me-2 text-warning"></i>
                                    {% elif amenity.name == "Non Smoking Building" %}
                                        <i class="fa-solid fa-ban-smoking me-2 text-warning"></i>
                                    {% elif amenity.name == "On site super" %}
                                        <i class="fa-solid fa-screwdriver-wrench me-2 text-warning"></i>
                                    {% elif amenity.name == "Outdoor Spaces" %}
                                        <i class="fa-solid fa-umbrella-beach me-2 text-warning"></i>
                                    {% elif amenity.name == "Package Room" %}
                                        <i class="fa-solid fa-box me-2 text-warning"></i>
                                    {% elif amenity.name == "Parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Pet spa" %}
                                        <i class="fa-solid fa-bath me-2 text-warning"></i>
                                    {% elif amenity.name == "Pool" %}
                                        <i class="fa-solid fa-water-ladder me-2 text-warning"></i>
                                    {% elif amenity.name == "Recreation" %}
                                        <i class="fa-solid fa-table-tennis-paddle-ball me-2 text-warning"></i>
                                    {% elif amenity.name == "Resident Lounge" %}
                                        <i class="fa-solid fa-couch me-2 text-warning"></i>
                                    {% elif amenity.name == "Roof Access" %}
                                        <i class="fa-solid fa-arrow-up-from-ground-water me-2 text-warning"></i>
                                    {% elif amenity.name == "Roof Deck" %}
                                        <i class="fa-solid fa-arrow-up-from-ground-water me-2 text-warning"></i>
                                    {% elif amenity.name == "Screening room" %}
                                        <i class="fa-solid fa-tv me-2 text-warning"></i>
                                    {% elif amenity.name == "Security cameras" %}
                                        <i class="fa-solid fa-video me-2 text-warning"></i>
                                    {% elif amenity.name == "Smoke free property" %}
                                        <i class="fa-solid fa-ban-smoking me-2 text-warning"></i>
                                    {% elif amenity.name == "Storage" %}
                                        <i class="fa-solid fa-box-archive me-2 text-warning"></i>
                                    {% elif amenity.name == "Valet" %}
                                        <i class="fa-solid fa-key me-2 text-warning"></i>
                                    {% elif amenity.name == "Verizon Fios" %}
                                        <i class="fa-solid fa-tower-broadcast me-2 text-warning"></i>
                                    {% elif amenity.name == "Virtual Doorman" %}
                                        <i class="fa-solid fa-tablet-screen-button me-2 text-warning"></i>
                                    {% elif amenity.name == "Wheelchair Access" %}
                                        <i class="fa-solid fa-wheelchair me-2 text-warning"></i>
                                    {% elif amenity.name == "Yoga studio" %}
                                        <i class="fa-solid fa-spa me-2 text-warning"></i>
                                    {% else %}
                                        <i class="fa-solid fa-check-circle me-2 text-warning"></i>
                                    {% endif %}
                                    <span class="amenity-name">{{ amenity.name }}</span>
                                </div>
                                <span class="priority-label text-muted"></span>
                            </div>
                            <div class="slider-container mt-2">
                                <input type="range" 
                                       min="0" 
                                       max="3" 
                                       value="0" 
                                       step="1" 
                                       class="amenity-slider unset" 
                                       name="building_amenity_{{ amenity.id }}"
                                       data-amenity-id="{{ amenity.id }}"
                                       data-amenity-type="building"
                                       data-amenity-name="{{ amenity.name }}"
                                       data-existing-value="0">
                                <div class="slider-labels">
                                    <span class="slider-label-left">Don't Care</span>
                                    <span class="slider-label-right">Must Have</span>
                                </div>
                            </div>
                        </div>
                        {% empty %}
                        <p class="text-muted">No building amenities available</p>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Apartment Amenities Section -->
                <div class="mb-5">
                    <div class="d-flex align-items-center mb-3">
                        <h5 class="mb-0 me-3">Apartment Features</h5>
                        <small class="text-muted">
                            <i class="fas fa-info-circle"></i> 
                            Set priorities for apartment-specific features. Only select features that matter to you.
                        </small>
                    </div>
                    
                    <div class="amenities-grid" id="apartment-amenities">
                        {% for amenity in all_apartment_amenities %}
                        <div class="amenity-slider-item unset" data-amenity-id="{{ amenity.id }}" data-amenity-type="apartment">
                            <div class="amenity-info">
                                <span class="amenity-name">{{ amenity.name }}</span>
                                <span class="priority-label text-muted"></span>
                            </div>
                            <div class="slider-container mt-2">
                                <input type="range" 
                                       min="0" 
                                       max="3" 
                                       value="0" 
                                       step="1" 
                                       class="amenity-slider unset" 
                                       name="apartment_amenity_{{ amenity.id }}"
                                       data-amenity-id="{{ amenity.id }}"
                                       data-amenity-type="apartment"
                                       data-amenity-name="{{ amenity.name }}"
                                       data-existing-value="0">
                                <div class="slider-labels">
                                    <span class="slider-label-left">Don't Care</span>
                                    <span class="slider-label-right">Must Have</span>
                                </div>
                            </div>
                        </div>
                        {% empty %}
                        <p class="text-muted">No apartment amenities available</p>
                        {% endfor %}
                    </div>
                </div>
                '''),
            ),
            
            # Navigation Buttons
            Div(
                HTML('<a href="{% url \'profile_step1\' %}" class="btn btn-doorway-secondary btn-lg me-3">← Previous</a>'),
                Submit('housing_submit', 'Save & Continue', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'profile_step3\' %}" class="btn btn-outline-secondary btn-lg">Skip</a>'),
                css_class='text-center mt-4'
            )
        )

    def clean(self):
        """Cross-field validation for bedroom/bathroom ranges, move-in date, and rate limiting"""
        cleaned_data = super().clean()
        
        # Rate limiting
        request = getattr(self, 'request', None)
        if request:
            user_identifier = request.META.get('REMOTE_ADDR', 'unknown')
            if request.user.is_authenticated:
                user_identifier = f"{user_identifier}:{request.user.id}"
            
            try:
                check_rate_limit(user_identifier, 'housing_form')
            except ValidationError as e:
                self.add_error(None, e)
        
        # Cross-field validation for bedroom range
        try:
            validate_bedroom_range(
                cleaned_data.get('min_bedrooms'),
                cleaned_data.get('max_bedrooms')
            )
        except ValidationError as e:
            self.add_error('min_bedrooms', e)
            self.add_error('max_bedrooms', e)
        
        # Cross-field validation for bathroom range
        try:
            validate_bathroom_range(
                cleaned_data.get('min_bathrooms'),
                cleaned_data.get('max_bathrooms')
            )
        except ValidationError as e:
            self.add_error('min_bathrooms', e)
            self.add_error('max_bathrooms', e)
        
        # Validate move-in date
        move_in_date = cleaned_data.get('desired_move_in_date')
        if move_in_date:
            try:
                validate_move_in_date(move_in_date)
            except ValidationError as e:
                self.add_error('desired_move_in_date', e)
        
        return cleaned_data


class ApplicantEmploymentForm(forms.ModelForm):
    """Step 3: Income & Employment Form"""
    
    # Add extra form fields not in the model
    income_source = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    average_annual_income = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        validators=[validate_currency_amount],
        widget=forms.NumberInput(attrs={
            'class': 'form-control currency-field',
            'step': '0.01',
            'placeholder': '$0.00',
            'min': '0',
            'max': '10000000'  # $10M max for income
        })
    )
    
    class Meta:
        model = Applicant
        fields = [
            'employment_status', 
            # Employment fields
            'company_name', 'position', 'annual_income', 'supervisor_name', 'supervisor_email', 
            'supervisor_phone', 'currently_employed', 'employment_start_date', 'employment_end_date',
            # Student fields
            'school_name', 'year_of_graduation', 'school_address', 'school_phone',
        ]
        widgets = {
            'employment_status': forms.Select(attrs={'class': 'form-select select2'}),
            # New employment field widgets
            'annual_income': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '75000.00',
                'min': '0'
            }),
            'supervisor_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 555-5555'}),
            'employment_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employment_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # Legacy field widgets (keep for backward compatibility)
            'monthly_income': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '5000.00',
                'min': '0',
                'max': '500000'  # $500k/month max
            }),
            # Student field widgets
            'school_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123 University Ave, College Town, NY 12345'}),
            'school_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 555-5555'}),
        }

    def __init__(self, *args, **kwargs):
        # Extract request for rate limiting
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Add security validators to text fields
        text_fields_to_sanitize = [
            'company_name', 'position', 'supervisor_name', 'supervisor_email',
            'school_name', 'school_address', 'income_source'
        ]
        
        for field_name in text_fields_to_sanitize:
            if field_name in self.fields:
                self.fields[field_name].validators.append(sanitize_text_input)
        
        # Add phone validation
        phone_fields = ['supervisor_phone', 'school_phone']
        for field_name in phone_fields:
            if field_name in self.fields:
                self.fields[field_name].validators.append(validate_phone_number)
        
        # Add currency validation
        currency_fields = ['annual_income', 'average_annual_income']
        for field_name in currency_fields:
            if field_name in self.fields:
                self.fields[field_name].validators.append(validate_currency_amount)
        
        # Add email validation
        if 'supervisor_email' in self.fields:
            self.fields['supervisor_email'].validators.append(validate_email_domain)
        
        # Add length limits
        length_limits = {
            'company_name': 100,
            'position': 100,
            'supervisor_name': 100,
            'school_name': 100,
            'school_address': 200,
            'income_source': 100
        }
        
        for field_name, max_length in length_limits.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'maxlength': max_length})
        
        # All fields are optional
        for field_name, field in self.fields.items():
            field.required = False
            field.label_suffix = ''
            
        # Customize specific field labels and choices
        self.fields['employment_status'].label = 'Which best describes you?'
        self.fields['employment_status'].required = False
        self.fields['employment_status'].choices = [
            ('', 'Select an option...'),
            ('student', 'I am a student'),
            ('employed', 'I am employed'),
            ('other', 'Other'),
        ]
        self.fields['employment_status'].initial = ''

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            Fieldset(
                'Employment Status',
                Field('employment_status', css_class='employment-status-dropdown mb-4 select2'),
            ),
            
            HTML('<div id="employed-fields" style="display: none;">'),
            Fieldset(
                'Employment Information',
                Row(
                    Column('company_name', css_class='col-md-6'),
                    Column('position', css_class='col-md-6'),
                ),
                Row(
                    Column(Field('annual_income', template='applicants/currency_income_field.html'), css_class='col-md-6'),
                    Column('supervisor_name', css_class='col-md-6'),
                ),
                Row(
                    Column('supervisor_email', css_class='col-md-6'),
                    Column(Field('supervisor_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                HTML('''
                <div class="row mb-3">
                    <div class="col-md-12">
                        <div class="form-check">
                            <input class="form-check-input currently-employed-checkbox" type="checkbox" name="currently_employed" id="{{ form.currently_employed.id_for_label }}" {% if form.currently_employed.value %}checked{% endif %} style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label ms-2" for="{{ form.currently_employed.id_for_label }}" style="font-size: 1.1rem; font-weight: 500;">
                                I am currently employed here
                            </label>
                        </div>
                    </div>
                </div>
                
                <div id="employment-dates" class="row mb-3">
                    <div class="col-md-6" id="start-date-field">
                        <label class="form-label">Start Date</label>
                        {{ form.employment_start_date }}
                    </div>
                    <div class="col-md-6" id="end-date-field" style="display: none;">
                        <label class="form-label">End Date</label>
                        {{ form.employment_end_date }}
                    </div>
                </div>
                '''),
                HTML('''
                <div class="mt-3">
                    <button type="button" id="add-job-btn-employed" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Job
                    </button>
                    <button type="button" id="add-income-btn-employed" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Income Source
                    </button>
                    <button type="button" id="add-asset-btn-employed" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Asset
                    </button>
                </div>
                '''),
            ),
            
            HTML('''
            <div id="jobs-container-employed" style="display: none;">
                <h5 class="mb-3">Additional Employment</h5>
                <div id="jobs-list-employed">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                </div>
            </div>
            '''),
            
            HTML('''
            <div id="income-container-employed" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list-employed">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                </div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container-employed" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list-employed">
                    <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
                </div>
            </div>
            '''),
            
            HTML('</div>'),
            
            HTML('<div id="student-fields" style="display: none;">'),
            Fieldset(
                'School Information',
                Row(
                    Column('school_name', css_class='col-md-6'),
                    Column(Field('year_of_graduation', placeholder="2025"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('school_address', placeholder="123 University Ave, College Town, NY 12345"), css_class='col-md-6'),
                    Column(Field('school_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                HTML('''
                <div class="mt-3">
                    <button type="button" id="add-job-btn" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Job
                    </button>
                    <button type="button" id="add-income-btn" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Income Source
                    </button>
                    <button type="button" id="add-asset-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Asset
                    </button>
                </div>
                '''),
            ),
            
            HTML('''
            <div id="jobs-container" style="display: none;">
                <h5 class="mb-3">Employment</h5>
                <div id="jobs-list"></div>
            </div>
            '''),
            
            HTML('''
            <div id="income-container" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list"></div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list"></div>
            </div>
            '''),
            
            HTML('</div>'),
            
            HTML('<div id="other-fields" style="display: none;">'),
            HTML('''
            <div class="mt-3">
                <button type="button" id="add-income-btn-other" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                    <i class="fas fa-plus"></i> Add Income Source
                </button>
                <button type="button" id="add-asset-btn-other" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                    <i class="fas fa-plus"></i> Add Asset
                </button>
            </div>
            '''),
            
            HTML('''
            <div id="income-container-other" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list-other"></div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container-other" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list-other"></div>
            </div>
            '''),
            
            HTML('</div>'),
            
            # Navigation Buttons
            Div(
                HTML('<a href="{% url \'profile_step2\' %}" class="btn btn-doorway-secondary btn-lg me-3">← Previous</a>'),
                Submit('employment_submit', 'Complete Profile', css_class='btn btn-success btn-lg me-3'),
                HTML('<a href="{% url \'applicant_dashboard\' %}" class="btn btn-outline-secondary btn-lg">Skip</a>'),
                css_class='text-center mt-4'
            )
        )

    def clean(self):
        """Cross-field validation for employment dates and rate limiting"""
        cleaned_data = super().clean()
        
        # Rate limiting
        request = getattr(self, 'request', None)
        if request:
            user_identifier = request.META.get('REMOTE_ADDR', 'unknown')
            if request.user.is_authenticated:
                user_identifier = f"{user_identifier}:{request.user.id}"
            
            try:
                check_rate_limit(user_identifier, 'employment_form')
            except ValidationError as e:
                self.add_error(None, e)
        
        # Cross-field validation for employment dates
        start_date = cleaned_data.get('employment_start_date')
        end_date = cleaned_data.get('employment_end_date')
        currently_employed = cleaned_data.get('currently_employed')
        
        # If not currently employed, end date is required
        if not currently_employed and start_date and not end_date:
            self.add_error('employment_end_date', 'End date is required for past employment.')
        
        # Validate employment date range
        if start_date and end_date:
            try:
                validate_employment_dates(start_date, end_date)
            except ValidationError as e:
                self.add_error('employment_start_date', e)
                self.add_error('employment_end_date', e)
        
        return cleaned_data


# Original single-page form (keep for backward compatibility)
class ApplicantForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'phone_number', 'email',
            'street_address_1', 'street_address_2', 'city', 'state', 'zip_code',
            'housing_status', 'current_landlord_name', 'current_landlord_phone', 'current_landlord_email',
            'desired_move_in_date', 'number_of_bedrooms', 'number_of_bathrooms', 'max_rent_budget', 'open_to_roommates',
            'driver_license_number', 'driver_license_state',
            'amenities', 'neighborhood_preferences',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
            'employment_status', 'school_name', 'year_of_graduation', 'school_address', 'school_phone',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'desired_move_in_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # Currency fields with same restrictions as buildings form
            'max_rent_budget': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '2500.00',
                'min': '100',
                'max': '50000'
            }),
            'employment_status': forms.Select(attrs={'class': 'form-select select2'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add security validators
        self.fields['first_name'].validators.append(sanitize_text_input)
        self.fields['last_name'].validators.append(sanitize_text_input)
        self.fields['email'].validators.append(validate_email_domain)
        self.fields['phone_number'].validators.append(validate_phone_number)
        self.fields['max_rent_budget'].validators.append(validate_currency_amount)
        
        # Add length limits
        length_limits = {
            'first_name': 50, 'last_name': 50, 'street_address_1': 100,
            'street_address_2': 100, 'city': 50, 'zip_code': 10,
            'emergency_contact_name': 100, 'emergency_contact_relationship': 50,
            'driver_license_number': 50, 'school_name': 100, 'school_address': 200
        }
        
        for field_name, max_length in length_limits.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'maxlength': max_length})
                self.fields[field_name].validators.append(sanitize_text_input)

        # Allow decimal values for bedrooms and bathrooms
        self.fields['number_of_bedrooms'].widget = forms.NumberInput(attrs={'step': '0.5', 'class': 'form-control'})
        self.fields['number_of_bathrooms'].widget = forms.NumberInput(attrs={'step': '0.5', 'class': 'form-control'})

        # Multiple selections
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = Amenity.objects.all()

        self.fields['neighborhood_preferences'].widget = forms.CheckboxSelectMultiple()
        self.fields['neighborhood_preferences'].queryset = Neighborhood.objects.all()
        
        # Only first_name, last_name, and email are required
        # Mark all other fields as not required
        required_fields = ['first_name', 'last_name', 'email']
        for field_name, field in self.fields.items():
            if field_name not in required_fields:
                field.required = False

        # Crispy Forms setup - matching buildings form style
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'
        
        # Remove label suffixes like buildings form
        for field_name, field in self.fields.items():
            field.label_suffix = ''
            if field.required:
                field.widget.attrs['required'] = 'required'

        self.helper.layout = Layout(
            Fieldset(
                'Basic Info',
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('phone_number', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Current Address</h6>'),
                Row(
                    Column('street_address_1', css_class='col-md-8'),
                    Column('street_address_2', css_class='col-md-4'),
                ),
                Row(
                    Column('city', css_class='col-md-5'),
                    Column('state', css_class='col-md-3'),
                    Column('zip_code', css_class='col-md-4'),
                ),
                HTML('''
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="is_rental_checkbox" name="is_rental_checkbox">
                    <label class="form-check-label" for="is_rental_checkbox">
                        Is this a Rental?
                    </label>
                </div>
                '''),
                Field('housing_status', type="hidden"),
                Div(
                    Row(
                        Column(Field('current_landlord_name', placeholder="Landlord's Name"), css_class='col-md-4'),
                        Column(Field('current_landlord_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                        Column(Field('current_landlord_email', placeholder="Landlord's Email"), css_class='col-md-4'),
                    ),
                    css_id='landlord_fields',
                    css_class='d-none'
                ),
                HTML('''
                <!-- Previous Address Section -->
                <div class="mt-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="fw-bold text-secondary mb-0" style="font-size: 1rem;">Previous Addresses</h6>
                        <button type="button" id="add-previous-address-btn" class="btn btn-outline-primary btn-sm">
                            <i class="fas fa-plus"></i> Add Previous Address
                        </button>
                    </div>
                    <p class="text-muted small mb-3">Add up to 4 previous addresses to help with your rental history.</p>
                    <div id="previous-addresses-container">
                        <!-- Dynamic previous address forms will be added here -->
                    </div>
                </div>
                '''),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Identification</h6>'),
                Row(
                    Column(Field('date_of_birth', placeholder=""), css_class='col-md-6'),
                    Column(css_class='col-md-6'),
                ),
                Row(
                    Column(Field('driver_license_number', placeholder="Driver's License Number"), css_class='col-md-6'),
                    Column('driver_license_state', css_class='col-md-6'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Emergency Contact</h6>'),
                Row(
                    Column(Field('emergency_contact_name', placeholder="Full Name"), css_class='col-md-6'),
                    Column(Field('emergency_contact_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Field('emergency_contact_relationship', placeholder="Relationship (e.g., Friend, Sibling)"),
            ),
            Fieldset(
                'Housing Needs and Preferences',
                Row(
                    Column(Field('desired_move_in_date'), css_class='col-md-6'),
                    Column(Field('max_rent_budget', template='applicants/currency_field.html'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('number_of_bedrooms'), css_class='col-md-4'),
                    Column(Field('number_of_bathrooms'), css_class='col-md-4'),
                    Column('open_to_roommates', css_class='col-md-4'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Preferences</h6>'),
                InlineCheckboxes('neighborhood_preferences'),
                InlineCheckboxes('amenities'),
            ),
            Fieldset(
                'Employment & Student Information',
                Row(
                    Column('employment_status', css_class='col-md-6'),
                    css_class='mb-3'
                ),
                # Student fields
                Row(
                    Column('school_name', css_class='col-md-6'),
                    Column('year_of_graduation', css_class='col-md-6'),
                ),
                'school_address',
                'school_phone',
                # Dynamic employment sections
                HTML('{% include "applicants/employment_sections.html" %}'),
            ),
            Div(
                Submit('applicant_submit', 'Save Profile', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'applicant_dashboard\' %}" class="btn btn-doorway-secondary btn-lg">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )


class ApplicantPhotoForm(forms.ModelForm):
    image = CloudinaryFileField()

    class Meta:
        model = ApplicantPhoto
        fields = ['image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = ['pet_type', 'quantity', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'

        self.helper.layout = Layout(
            Fieldset(
                'Pet Information',
                Row(
                    Column(Field('pet_type'), css_class='col-md-6'),
                    Column(Field('quantity', placeholder="e.g., 1"), css_class='col-md-6'),
                ),
                Field('description'),
            ),
            Submit('pet_submit', 'Save Pet', css_class='btn btn-primary'),
        )


class PetPhotoForm(forms.ModelForm):
    image = CloudinaryFileField()

    class Meta:
        model = PetPhoto
        fields = ['image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'



FAKE_USERS = [
    ("Meron", "Meron"),
    ("Eden", "Eden"),
    ("Asaf", "Asaf"),
    ("Fabron", "Fabron"),
]



from django import forms
from .models import InteractionLog

FAKE_USERS = [
    ("meron", "Meron"),
    ("eden", "Eden"),
    ("asaf", "Asaf"),
    ("fabron", "Fabron"),
]

class InteractionLogForm(forms.ModelForm):
    file = SecureImageField(required=False)  # Use secure file field
    notify_users = forms.MultipleChoiceField(
        choices=FAKE_USERS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Notify Users",
    )

    class Meta:
        model = InteractionLog
        fields = ["note", "file", "notify_users"]
        widgets = {
            "note": forms.Textarea(attrs={
                "class": "form-control", 
                "rows": 3, 
                "placeholder": "Enter interaction details...",
                "maxlength": 1000  # Limit note length
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add XSS protection to note field
        self.fields['note'].validators.append(sanitize_text_input)
