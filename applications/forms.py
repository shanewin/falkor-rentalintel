from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import escape
from .models import Application, RequiredDocumentType, PersonalInfoData, PreviousAddress, IncomeData
from applicants.models import Applicant
from apartments.models import Apartment
from django.utils.translation import gettext_lazy as _

BOOLEAN_CHOICES = [(True, _('Yes')), (False, _('No'))]

# Reusable security and currency validators (mirrored from applicants/forms.py)
def sanitize_text_input(value):
    """Sanitize text input to prevent XSS"""
    if not value:
        return value
    sanitized = escape(value)
    dangerous_patterns = [
        'javascript:', 'data:', 'vbscript:', 'onclick', 'onload', 
        'onerror', 'onmouseover', '<script', '</script>'
    ]
    value_lower = value.lower()
    for pattern in dangerous_patterns:
        if pattern in value_lower:
            raise ValidationError("Input contains potentially unsafe content.")
    return sanitized

def validate_annual_income(value):
    """Validate annual income amounts"""
    if value is None:
        return
    if value < 0:
        raise ValidationError("Amount cannot be negative.")
    if value > 100000000:
        raise ValidationError("Amount exceeds maximum allowed limit ($100M).")


# V2 Application System Forms

class PersonalInfoForm(forms.ModelForm):
    """Section 1 - Personal Information Form"""
    
    # Add custom field for address lookup
    address_lookup = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Start typing your address...',
            'id': 'address-lookup'
        }),
        help_text='Start typing to search for your address'
    )
    
    # Explicitly override boolean fields with Yes/No radios
    has_pets = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    
    has_filed_bankruptcy = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    
    has_criminal_conviction = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    
    class Meta:
        model = PersonalInfoData
        fields = [
            'first_name', 'middle_name', 'last_name', 'suffix',
            'email', 'phone_cell',
            'date_of_birth', 'ssn',
            'street_address_1', 'street_address_2',
            'city', 'state', 'zip_code',
            'current_address_years', 'current_address_months',
            'housing_status', 'current_monthly_rent', 'is_rental_property',
            'landlord_name', 'landlord_phone', 'landlord_email',
            'desired_address', 'desired_unit', 'desired_move_in_date',
            'referral_source', 'has_pets',
            'reference1_name', 'reference1_phone',
            'reference2_name', 'reference2_phone',
            'has_filed_bankruptcy', 'bankruptcy_explanation',
            'has_criminal_conviction', 'conviction_explanation'
        ]
        
        widgets = {
            # Name fields
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Contact fields
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_cell': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '(xxx) xxx-xxxx'
            }),
            
            # Personal details
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'ssn': forms.TextInput(attrs={
                'class': 'form-control', 
                'pattern': '[0-9]{3}-[0-9]{2}-[0-9]{4}'
            }),
            
            # Address fields
            'street_address_1': forms.TextInput(attrs={'class': 'form-control'}),
            'street_address_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'current_address_years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'current_address_months': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 11}),
            'housing_status': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': "Select Housing Status"
            }, choices=[
                ('', ''),
                ('Rent', 'Rent'),
                ('Own', 'Own'),
                ('Other', 'Other'),
            ]),
            'current_monthly_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_rental_property': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            # Landlord fields (conditional)
            'landlord_name': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_email': forms.EmailInput(attrs={'class': 'form-control'}),
            
            # Desired property
            'desired_address': forms.TextInput(attrs={'class': 'form-control'}),
            'desired_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'desired_move_in_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            
            # Additional info
            'referral_source': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'How did you hear about us?'
            }),
            
            # References
            'reference1_name': forms.TextInput(attrs={'class': 'form-control'}),
            'reference1_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'reference2_name': forms.TextInput(attrs={'class': 'form-control'}),
            'reference2_phone': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Legal history
            'bankruptcy_explanation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Please explain...'}),
            'conviction_explanation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Please explain...'}),
        }
        
        labels = {
            'first_name': 'First Name *',
            'middle_name': 'Middle Name',
            'last_name': 'Last Name *',
            'suffix': 'Suffix',
            'email': 'Email *',
            'phone_cell': 'Cell Phone *',
            'date_of_birth': 'Date of Birth *',
            'ssn': 'Social Security Number *',
            'street_address_1': 'Current Address *',
            'street_address_2': 'Street Address 2 / Apt No.',
            'city': 'City *',
            'state': 'State *',
            'zip_code': 'Zip Code *',
            'current_address_years': 'Years at current address *',
            'current_address_months': 'Months at current address *',
            'landlord_name': "Landlord's Name",
            'landlord_phone': "Landlord's Phone",
            'landlord_email': "Landlord's Email",
            'desired_address': 'Desired Address *',
            'desired_unit': 'Desired Unit *',
            'desired_move_in_date': 'Move-in Date *',
            'referral_source': 'How did you hear about us? *',
            'has_pets': 'I have pets',
            'reference1_name': 'Reference #1 Name *',
            'reference1_phone': 'Reference #1 Phone *',
            'reference2_name': 'Reference #2 Name',
            'reference2_phone': 'Reference #2 Phone',
            'has_filed_bankruptcy': 'I have filed for bankruptcy',
            'has_criminal_conviction': 'I have a criminal conviction',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Landlord fields are required if renting
        # We handle the visual asterisk in the template
        # Here we can add data-conditional for JS logic
        landlord_fields = ['landlord_name', 'landlord_phone', 'landlord_email']
        for field in landlord_fields:
            if field in self.fields:
                self.fields[field].widget.attrs['data-conditional-parent'] = 'id_housing_status'
                self.fields[field].widget.attrs['data-conditional-value'] = 'Rent'

    def clean_ssn(self):
        """Validate and format SSN"""
        ssn = self.cleaned_data.get('ssn')
        if ssn:
            # Remove any non-digits
            ssn_digits = ''.join(filter(str.isdigit, ssn))
            
            # Validate length
            if len(ssn_digits) != 9:
                raise forms.ValidationError("SSN must be 9 digits long")
            
            # Format as XXX-XX-XXXX
            formatted_ssn = f"{ssn_digits[:3]}-{ssn_digits[3:5]}-{ssn_digits[5:]}"
            return formatted_ssn
        
        return ssn
    
    def clean_phone_cell(self):
        """Validate and format phone number"""
        phone = self.cleaned_data.get('phone_cell')
        if phone:
            # Remove any non-digits
            phone_digits = ''.join(filter(str.isdigit, phone))
            
            # Validate length
            if len(phone_digits) != 10:
                raise forms.ValidationError("Phone number must be 10 digits long")
            
            # Format as (XXX) XXX-XXXX
            formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
            return formatted_phone
        
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        housing_status = cleaned_data.get('housing_status')
        
        if housing_status == 'Rent':
            for field in ['landlord_name', 'landlord_phone', 'landlord_email']:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required for rental properties.")
                    
        return cleaned_data


class PreviousAddressForm(forms.ModelForm):
    """Form for adding previous addresses"""
    
    class Meta:
        model = PreviousAddress
        fields = ['street_address_1', 'street_address_2', 'city', 'state', 'zip_code', 'years', 'months', 'landlord_name', 'landlord_phone', 'landlord_email', 'monthly_rent', 'housing_status']
        
        widgets = {
            'street_address_1': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'street_address_2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'years': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'months': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 11}),
            'landlord_name': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'monthly_rent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'housing_status': forms.Select(attrs={'class': 'form-select'}, choices=[('rent', 'Rent'), ('own', 'Own')]),
        }


class IncomeForm(forms.ModelForm):
    """Section 2 - Income & Employment Form"""
    
    # Explicitly override boolean fields with Yes/No radios
    currently_employed = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    has_multiple_jobs = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    has_additional_income = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )
    has_assets = forms.TypedChoiceField(
        choices=BOOLEAN_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        coerce=lambda x: str(x) == 'True',
        required=False,
        initial=None
    )

    class Meta:
        model = IncomeData
        fields = [
            'employment_type', 'employer', 'job_title', 'annual_income',
            'employment_length', 'supervisor_name', 'supervisor_phone', 'supervisor_email',
            'currently_employed', 'start_date', 'end_date',
            'school_name', 'year_of_graduation', 'school_address', 'school_phone',
            'additional_income_source', 'additional_income_amount', 'proof_of_income',
            'paystub_1', 'paystub_2', 'paystub_3',
            'bank_statement_1', 'bank_statement_2',
            'id_type', 'id_number', 'id_state', 'id_front_image', 'id_back_image',
            'has_multiple_jobs', 'has_additional_income', 'has_assets'
        ]
        
        widgets = {
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'job_title': forms.TextInput(attrs={'class': 'form-control'}),
            'annual_income': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'employment_length': forms.TextInput(attrs={'class': 'form-control'}),
            'additional_income_source': forms.TextInput(attrs={'class': 'form-control'}),
            'additional_income_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'proof_of_income': forms.FileInput(attrs={'class': 'form-control'}),
            'supervisor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'supervisor_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 123-4567'}),
            'supervisor_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            
            # Student fields
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'year_of_graduation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY'}),
            'school_address': forms.TextInput(attrs={'class': 'form-control'}),
            'school_phone': forms.TextInput(attrs={'class': 'form-control'}),
            
            # File fields
            'paystub_1': forms.FileInput(attrs={'class': 'form-control'}),
            'paystub_2': forms.FileInput(attrs={'class': 'form-control'}),
            'paystub_3': forms.FileInput(attrs={'class': 'form-control'}),
            'bank_statement_1': forms.FileInput(attrs={'class': 'form-control'}),
            'bank_statement_2': forms.FileInput(attrs={'class': 'form-control'}),
            
            # ID fields
            'id_type': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', 'Select ID Type'),
                ('passport', 'Passport'),
                ('driver_license', 'Driver\'s License'),
                ('state_id', 'State ID'),
            ]),
            'id_number': forms.TextInput(attrs={'class': 'form-control'}),
            'id_state': forms.TextInput(attrs={'class': 'form-control'}),
            'id_front_image': forms.FileInput(attrs={'class': 'form-control'}),
            'id_back_image': forms.FileInput(attrs={'class': 'form-control'}),
        }
        
        labels = {
            'employment_type': 'Employment Status *',
            'employer': 'Company Name',
            'job_title': 'Position/Job Title',
            'annual_income': 'Annual Income ($)',
            'employment_length': 'Length of Employment',
            'supervisor_name': 'Supervisor Name',
            'supervisor_phone': 'Supervisor Phone',
            'currently_employed': 'I am currently employed here',
            'school_name': 'School Name',
            'year_of_graduation': 'Year of Graduation',
            'id_type': 'Identification Type',
            'id_number': 'ID Number',
            'id_state': 'ID Issuing State',
            'paystub_1': 'Most Recent Pay Stub',
            'paystub_2': 'Second Most Recent Pay Stub',
            'paystub_3': 'Third Most Recent Pay Stub',
            'bank_statement_1': 'Most Recent Bank Statement (Full PDF)',
            'bank_statement_2': 'Second Most Recent Bank Statement (Full PDF)',
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add basic form styling
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.FileInput, forms.RadioSelect)):
                field.widget.attrs.update({'class': 'form-control'})
            
        # Add security validators
        text_fields = ['employer', 'job_title', 'supervisor_name', 'school_name', 'id_number', 'id_state']
        for field in text_fields:
            if field in self.fields:
                self.fields[field].validators.append(sanitize_text_input)
                
        # Add annual income validator
        if 'annual_income' in self.fields:
            self.fields['annual_income'].validators.append(validate_annual_income)

    def clean(self):
        cleaned_data = super().clean()
        emp_type = cleaned_data.get('employment_type')
        
        if emp_type == 'employed':
            required_emp = ['employer', 'job_title', 'annual_income', 'start_date']
            for field in required_emp:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required for employed applicants.")
        
        elif emp_type == 'student':
            required_student = ['school_name', 'year_of_graduation']
            for field in required_student:
                if not cleaned_data.get(field):
                    self.add_error(field, "This field is required for student applicants.")
        
        return cleaned_data
