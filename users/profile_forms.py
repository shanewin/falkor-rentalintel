from django import forms
from django.conf import settings
from .profiles_models import BrokerProfile, OwnerProfile, StaffProfile, AdminProfile
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Field, Div, Submit, HTML
from crispy_forms.bootstrap import InlineCheckboxes
from cloudinary.forms import CloudinaryFileField
import cloudinary


class BrokerProfileForm(forms.ModelForm):
    profile_photo = CloudinaryFileField(required=False)
    
    class Meta:
        model = BrokerProfile
        fields = [
            'profile_photo', 'first_name', 'last_name', 'phone_number', 'mobile_phone', 'professional_email',
            'business_name', 'business_address_1', 'business_address_2', 'business_city', 'business_state', 'business_zip',
            'broker_license_number', 'license_state', 'license_expiration',
            'department', 'job_title', 'years_experience',
            'specializations', 'territories', 'standard_commission_rate', 'commission_split',
            'bio', 'certifications', 'awards',
            'preferred_contact_method', 'available_hours',
            'linkedin_url', 'website_url'
        ]
        widgets = {
            'license_expiration': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setup number inputs
        self.fields['years_experience'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        self.fields['standard_commission_rate'].widget = forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'})
        self.fields['commission_split'].widget = forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'})
        
        # Crispy Forms setup
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.render_required_fields = True
        
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                Field('profile_photo', help_text="Upload a professional profile photo"),
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('phone_number', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column(Field('mobile_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Field('professional_email', placeholder="professional@example.com"),
            ),
            Fieldset(
                'Business Information',
                Field('business_name', placeholder="Brokerage Company Name"),
                Row(
                    Column(Field('business_address_1', placeholder="Street Address"), css_class='col-md-12'),
                ),
                Row(
                    Column(Field('business_address_2', placeholder="Suite/Unit (optional)"), css_class='col-md-12'),
                ),
                Row(
                    Column(Field('business_city', placeholder="City"), css_class='col-md-4'),
                    Column(Field('business_state'), css_class='col-md-4'),
                    Column(Field('business_zip', placeholder="ZIP Code"), css_class='col-md-4'),
                ),
            ),
            Fieldset(
                'License Information',
                Row(
                    Column(Field('broker_license_number', placeholder="License #"), css_class='col-md-6'),
                    Column(Field('license_state'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('license_expiration'), css_class='col-md-6'),
                    Column(Field('years_experience'), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Professional Details',
                Row(
                    Column(Field('department', placeholder="Department"), css_class='col-md-6'),
                    Column(Field('job_title'), css_class='col-md-6'),
                ),
                Field('specializations', help_text="Hold Ctrl/Cmd to select multiple"),
                Field('territories', help_text="Areas you cover - JSON format"),
            ),
            Fieldset(
                'Commission Information',
                Row(
                    Column(Field('standard_commission_rate', placeholder="e.g., 2.5"), css_class='col-md-6'),
                    Column(Field('commission_split', placeholder="e.g., 70"), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Professional Information',
                Field('bio', placeholder="Brief professional biography..."),
                Field('certifications', help_text="Professional certifications - JSON format"),
                Field('awards', help_text="Awards and recognitions - JSON format"),
            ),
            Fieldset(
                'Contact & Availability',
                Row(
                    Column(Field('preferred_contact_method'), css_class='col-md-6'),
                    Column(Field('available_hours', placeholder="e.g., Mon-Fri 9AM-6PM"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('linkedin_url', placeholder="https://linkedin.com/in/yourname"), css_class='col-md-6'),
                    Column(Field('website_url', placeholder="https://www.example.com"), css_class='col-md-6'),
                ),
            ),
            Submit('broker_submit', 'Save Profile', css_class='btn btn-primary'),
        )


class OwnerProfileForm(forms.ModelForm):
    profile_photo = CloudinaryFileField(required=False)
    
    class Meta:
        model = OwnerProfile
        fields = [
            'profile_photo', 'owner_type', 'first_name', 'last_name', 'company_name',
            'primary_phone', 'secondary_phone', 'business_email',
            'address_1', 'address_2', 'city', 'state', 'zip_code',
            'mailing_same_as_primary', 'mailing_address_1', 'mailing_address_2', 
            'mailing_city', 'mailing_state', 'mailing_zip',
            'number_of_properties', 'total_units', 'portfolio_value',
            'management_style', 'management_company_name',
            'tax_id_number', 'tax_classification',
            'insurance_carrier', 'insurance_policy_number', 'insurance_expiration',
            'bank_name', 'bank_account_type',
            'years_as_owner', 'acquisition_method',
            'preferred_contact_method', 'preferred_contact_time',
            'emergency_contact_name', 'emergency_contact_phone',
            'attorney_name', 'attorney_phone', 'accountant_name', 'accountant_phone',
            'notes', 'special_instructions'
        ]
        widgets = {
            'insurance_expiration': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'special_instructions': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Setup number inputs
        self.fields['number_of_properties'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        self.fields['total_units'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        self.fields['portfolio_value'].widget = forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'})
        self.fields['years_as_owner'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
        
        # Crispy Forms setup
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.render_required_fields = True
        
        self.helper.layout = Layout(
            Fieldset(
                'Owner Information',
                Field('profile_photo', help_text="Upload a professional profile photo"),
                Row(
                    Column(Field('owner_type'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Field('company_name', placeholder="Company Name (if applicable)"),
            ),
            Fieldset(
                'Contact Information',
                Row(
                    Column(Field('primary_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column(Field('secondary_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Field('business_email', placeholder="business@example.com"),
            ),
            Fieldset(
                'Primary Address',
                Field('address_1', placeholder="Street Address"),
                Field('address_2', placeholder="Suite/Unit (optional)"),
                Row(
                    Column(Field('city', placeholder="City"), css_class='col-md-4'),
                    Column(Field('state'), css_class='col-md-4'),
                    Column(Field('zip_code', placeholder="ZIP Code"), css_class='col-md-4'),
                ),
            ),
            Fieldset(
                'Mailing Address',
                Field('mailing_same_as_primary'),
                Field('mailing_address_1', placeholder="Street Address"),
                Field('mailing_address_2', placeholder="Suite/Unit (optional)"),
                Row(
                    Column(Field('mailing_city', placeholder="City"), css_class='col-md-4'),
                    Column(Field('mailing_state'), css_class='col-md-4'),
                    Column(Field('mailing_zip', placeholder="ZIP Code"), css_class='col-md-4'),
                ),
            ),
            Fieldset(
                'Property Portfolio',
                Row(
                    Column(Field('number_of_properties'), css_class='col-md-4'),
                    Column(Field('total_units'), css_class='col-md-4'),
                    Column(Field('portfolio_value', placeholder="Total Value $"), css_class='col-md-4'),
                ),
                Row(
                    Column(Field('years_as_owner'), css_class='col-md-6'),
                    Column(Field('acquisition_method'), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Property Management',
                Field('management_style'),
                Field('management_company_name', placeholder="Management Company Name (if applicable)"),
            ),
            Fieldset(
                'Tax & Insurance',
                Row(
                    Column(Field('tax_id_number', placeholder="Tax ID/EIN"), css_class='col-md-6'),
                    Column(Field('tax_classification', placeholder="Tax Classification"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('insurance_carrier', placeholder="Insurance Company"), css_class='col-md-6'),
                    Column(Field('insurance_policy_number', placeholder="Policy #"), css_class='col-md-6'),
                ),
                Field('insurance_expiration'),
            ),
            Fieldset(
                'Banking Information',
                Row(
                    Column(Field('bank_name', placeholder="Bank Name"), css_class='col-md-6'),
                    Column(Field('bank_account_type'), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Contact Preferences',
                Row(
                    Column(Field('preferred_contact_method'), css_class='col-md-6'),
                    Column(Field('preferred_contact_time', placeholder="e.g., 9AM-5PM"), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Emergency & Professional Contacts',
                Row(
                    Column(Field('emergency_contact_name', placeholder="Emergency Contact"), css_class='col-md-6'),
                    Column(Field('emergency_contact_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('attorney_name', placeholder="Attorney Name"), css_class='col-md-6'),
                    Column(Field('attorney_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('accountant_name', placeholder="Accountant Name"), css_class='col-md-6'),
                    Column(Field('accountant_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Additional Information',
                Field('notes', placeholder="General notes..."),
                Field('special_instructions', placeholder="Special instructions or requirements..."),
            ),
            Submit('owner_submit', 'Save Profile', css_class='btn btn-primary'),
        )


class StaffProfileForm(forms.ModelForm):
    profile_photo = CloudinaryFileField(required=False)
    
    class Meta:
        model = StaffProfile
        fields = [
            'profile_photo', 'first_name', 'last_name', 'employee_id',
            'office_phone', 'office_extension', 'mobile_phone', 'office_email',
            'department', 'job_title', 'employment_start_date', 'employment_type',
            'office_building', 'office_floor', 'office_room', 
            'office_address_1', 'office_address_2', 'office_city', 'office_state', 'office_zip',
            'access_level', 'system_permissions',
            'can_create_users', 'can_modify_system_settings', 'can_access_logs', 'can_manage_backups',
            'can_manage_integrations', 'can_view_financial_data', 'can_manage_notifications',
            'departments_managed', 'buildings_managed', 'user_groups_managed',
            'security_clearance_level', 'two_factor_enabled',
            'primary_responsibilities', 'secondary_responsibilities',
            'bio', 'skills', 'certifications',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
            'work_schedule', 'remote_work_allowed',
            'training_completed', 'training_required'
        ]
        widgets = {
            'employment_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'primary_responsibilities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'secondary_responsibilities': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Crispy Forms setup
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.render_required_fields = True
        
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                Field('profile_photo', help_text="Upload a professional profile photo"),
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('employee_id', placeholder="Employee ID"), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Employment Information',
                Row(
                    Column(Field('employment_start_date'), css_class='col-md-6'),
                    Column(Field('employment_type'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('department'), css_class='col-md-6'),
                    Column(Field('job_title', placeholder="Position Title"), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Contact Information',
                Row(
                    Column(Field('office_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                    Column(Field('office_extension', placeholder="Ext"), css_class='col-md-4'),
                    Column(Field('mobile_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                ),
                Field('office_email', placeholder="office@example.com"),
            ),
            Fieldset(
                'Office Location',
                Row(
                    Column(Field('office_building', placeholder="Building Name"), css_class='col-md-6'),
                    Column(Field('office_floor', placeholder="Floor"), css_class='col-md-3'),
                    Column(Field('office_room', placeholder="Room #"), css_class='col-md-3'),
                ),
                Field('office_address_1', placeholder="Street Address"),
                Field('office_address_2', placeholder="Suite/Unit (optional)"),
                Row(
                    Column(Field('office_city', placeholder="City"), css_class='col-md-4'),
                    Column(Field('office_state'), css_class='col-md-4'),
                    Column(Field('office_zip', placeholder="ZIP Code"), css_class='col-md-4'),
                ),
            ),
            Fieldset(
                'Access & Permissions',
                Field('access_level'),
                Field('system_permissions', help_text="System permissions - JSON format"),
            ),
            Fieldset(
                'System Permissions',
                Row(
                    Column(Field('can_create_users'), css_class='col-md-4'),
                    Column(Field('can_modify_system_settings'), css_class='col-md-4'),
                    Column(Field('can_access_logs'), css_class='col-md-4'),
                ),
                Row(
                    Column(Field('can_manage_backups'), css_class='col-md-4'),
                    Column(Field('can_manage_integrations'), css_class='col-md-4'),
                    Column(Field('can_view_financial_data'), css_class='col-md-4'),
                ),
                Field('can_manage_notifications'),
            ),
            Fieldset(
                'Management Areas',
                Field('departments_managed', help_text="Departments under management - JSON format"),
                Field('buildings_managed', help_text="Buildings under management - JSON format"), 
                Field('user_groups_managed', help_text="User groups under management - JSON format"),
            ),
            Fieldset(
                'Security Settings',
                Row(
                    Column(Field('security_clearance_level'), css_class='col-md-6'),
                    Column(Field('two_factor_enabled'), css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Responsibilities',
                Field('primary_responsibilities', placeholder="Main job responsibilities..."),
                Field('secondary_responsibilities', placeholder="Additional responsibilities..."),
            ),
            Fieldset(
                'Professional Information',
                Field('bio', placeholder="Professional biography..."),
                Field('skills', help_text="Professional skills - JSON format"),
                Field('certifications', help_text="Professional certifications - JSON format"),
            ),
            Fieldset(
                'Emergency Contact',
                Row(
                    Column(Field('emergency_contact_name', placeholder="Full Name"), css_class='col-md-4'),
                    Column(Field('emergency_contact_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                    Column(Field('emergency_contact_relationship', placeholder="Relationship"), css_class='col-md-4'),
                ),
            ),
            Fieldset(
                'Work Schedule & Training',
                Row(
                    Column(Field('work_schedule', placeholder="e.g., Mon-Fri 9AM-5PM"), css_class='col-md-6'),
                    Column(Field('remote_work_allowed'), css_class='col-md-6'),
                ),
                Field('training_completed', help_text="Completed training programs - JSON format"),
                Field('training_required', help_text="Required training programs - JSON format"),
            ),
            Submit('staff_submit', 'Save Profile', css_class='btn btn-primary'),
        )


class AdminProfileForm(forms.ModelForm):
    # Add email field from the User model
    email = forms.EmailField(
        label='Email Address:',
        required=True,
        help_text='This email is used for login and system notifications'
    )
    
    class Meta:
        model = AdminProfile
        fields = [
            'email', 'first_name', 'last_name', 'position', 'phone_number', 'bio'
        ]
        labels = {
            'first_name': 'First Name:',
            'last_name': 'Last Name:',
            'position': 'Position / Title:',
            'phone_number': 'Preferred Phone Number:',
            'bio': 'Bio:',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If instance exists, populate email from the related User
        if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
            self.fields['email'].initial = self.instance.user.email
        
        # Apply consistent styling to all fields
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control form-control-lg',
                'style': 'border-radius: 8px; border: 2px solid #e9ecef; padding: 12px 16px;'
            })
        
        # Crispy Forms setup
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.render_required_fields = True
        self.helper.form_class = 'admin-profile-form'
        
        self.helper.layout = Layout(
            Div(
                Field('email',
                      placeholder="your.email@example.com",
                      css_class='mb-4'),
                css_class='form-group'
            ),
            Div(
                Row(
                    Column(
                        Field('first_name', 
                              placeholder="Enter your first name",
                              css_class='mb-4'),
                        css_class='col-md-6'
                    ),
                    Column(
                        Field('last_name', 
                              placeholder="Enter your last name",
                              css_class='mb-4'),
                        css_class='col-md-6'
                    ),
                ),
                css_class='form-row mb-3'
            ),
            Div(
                Field('position', 
                      placeholder="e.g., System Administrator, IT Manager, Technical Director",
                      css_class='mb-4'),
                css_class='form-group'
            ),
            Div(
                Field('phone_number', 
                      placeholder="(555) 123-4567",
                      css_class='mb-4'),
                css_class='form-group'
            ),
            Div(
                Field('bio', 
                      placeholder="Share your professional background, expertise, and experience...",
                      css_class='mb-4'),
                css_class='form-group'
            ),
            Div(
                Submit('admin_submit', 'Save Profile', 
                       css_class='btn btn-dark btn-lg px-5 py-3 mt-3 me-3 admin-save-btn',
                       style='border-radius: 8px; font-weight: 600; background-color: #000000; border-color: #000000; color: #ffcc00;'),
                HTML('<a href="{% url \'admin_dashboard\' %}" class="btn btn-outline-secondary btn-lg px-5 py-3 mt-3" style="border-radius: 8px; font-weight: 500;">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )
    
    def save(self, commit=True):
        # Save the AdminProfile instance
        instance = super().save(commit=False)
        
        # Update the related User's email if it has changed
        if hasattr(instance, 'user'):
            new_email = self.cleaned_data.get('email')
            if new_email and instance.user.email != new_email:
                instance.user.email = new_email
                if commit:
                    instance.user.save()
        
        if commit:
            instance.save()
        
        return instance