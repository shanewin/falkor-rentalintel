from django import forms
from .models import Applicant, Pet, ApplicantPhoto, PetPhoto, InteractionLog, ApplicantJob, ApplicantIncomeSource, ApplicantAsset
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Field, HTML, Submit
from crispy_forms.bootstrap import InlineCheckboxes
from cloudinary.forms import CloudinaryFileField

class ApplicantBasicInfoForm(forms.ModelForm):
    """Step 1: Basic Information Form"""
    
    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'phone_number', 'email',
            'street_address_1', 'street_address_2', 'city', 'state', 'zip_code',
            'housing_status', 'current_landlord_name', 'current_landlord_phone', 'current_landlord_email',
            'date_of_birth',
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
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only first_name, last_name, and email are required
        required_fields = ['first_name', 'last_name', 'email']
        for field_name, field in self.fields.items():
            if field_name not in required_fields:
                field.required = False

        # Set up form helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
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
                Field('date_of_birth'),
            ),
            
            Submit('submit', 'Continue to Step 2', css_class='btn btn-primary'),
        )