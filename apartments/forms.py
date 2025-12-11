from django import forms
from .models import Apartment, ApartmentImage, ApartmentAmenity, ApartmentConcession
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Field, Div, Submit
from crispy_forms.bootstrap import InlineCheckboxes
from ckeditor.widgets import CKEditorWidget


# Step 1: Basic Apartment Information
class ApartmentBasicForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = [
            'building', 'unit_number', 'bedrooms', 'bathrooms', 'square_feet', 'apartment_type', 
            'rent_price', 'net_price', 'deposit_price', 'status'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Basic Apartment Information',
                'building',
                Row(
                    Column(Field('unit_number', placeholder="e.g., 2A"), css_class='col-md-3'),
                    Column(Field('bedrooms', placeholder="e.g., 2"), css_class='col-md-3'),
                    Column(Field('bathrooms', placeholder="e.g., 1"), css_class='col-md-3'),
                    Column(Field('square_feet', placeholder="e.g., 850"), css_class='col-md-3'),
                ),
                Row(
                    Column(Field('apartment_type'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('rent_price', placeholder="e.g., 3200"), css_class='col-md-4'),
                    Column(Field('net_price', placeholder="e.g., 3000"), css_class='col-md-4'),
                    Column(Field('deposit_price', placeholder="e.g., 500"), css_class='col-md-4'),
                ),
                Row(
                    Column(Field('status'), css_class='col-md-6'),
                ),
            ),
            Submit('apartment_submit', 'Save & Continue', css_class='btn btn-primary'),
        )

# Step 2: Amenities and Features
class ApartmentAmenitiesForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = ['amenities', 'lock_type', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force checkboxes for amenities
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = ApartmentAmenity.objects.all().order_by('name')
        self.fields['description'].widget = CKEditorWidget()
        
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Apartment Features',
                # Amenities with checkboxes
                Div(
                    Fieldset(
                        'Apartment Amenities',
                        InlineCheckboxes('amenities'),
                    ),
                    css_class="custom-amenities-checkboxes mb-3"
                ),
                Field('lock_type', placeholder="e.g., Smart Lock"),
                Field('description'),
            ),
            Submit('amenities_submit', 'Save & Continue', css_class='btn btn-primary'),
        )

# Step 3: Additional Details
class ApartmentDetailsForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = [
            'broker_fee_required', 'paid_months',
            'lease_duration', 'holding_deposit', 'free_stuff', 'required_documents'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['required_documents'].widget = CKEditorWidget()
        
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Additional Details',
                Row(
                    Column(Field('broker_fee_required'), css_class='col-md-12'),
                ),
                Row(
                    Column(Field('paid_months', placeholder="e.g., 2"), css_class='col-md-6'),
                    Column(Field('holding_deposit', placeholder="e.g., 500"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('lease_duration', placeholder="e.g., 12 months"), css_class='col-md-6'),
                    Column(Field('free_stuff', placeholder="e.g., Free Netflix"), css_class='col-md-6'),
                ),
                Field('required_documents'),
            ),
            Submit('details_submit', 'Complete Apartment Setup', css_class='btn btn-success'),
        )

# Keep original form for backwards compatibility
class ApartmentForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = [
            'building', 'unit_number', 'bedrooms', 'bathrooms', 'square_feet', 'rent_price', 'net_price', 'deposit_price',
            'description', 'status', 'amenities', 'lock_type', 'broker_fee_required',
            'paid_months', 'lease_duration', 'holding_deposit', 'free_stuff',
            'required_documents','apartment_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Force checkboxes for amenities
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = ApartmentAmenity.objects.all()

        # Rich text fields with CKEditor
        self.fields['description'].widget = CKEditorWidget()
        self.fields['required_documents'].widget = CKEditorWidget()

        # Crispy Forms setup
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'
        self.helper.render_required_fields = True

        self.helper.layout = Layout(
            Fieldset(
                'Apartment Details',
                'building',
                Row(
                    Column(Field('unit_number', placeholder="e.g., 2A"), css_class='col-md-3'),
                    Column(Field('bedrooms', placeholder="e.g., 2"), css_class='col-md-3'),
                    Column(Field('bathrooms', placeholder="e.g., 1"), css_class='col-md-3'),
                    Column(Field('square_feet', placeholder="e.g., 850"), css_class='col-md-3'),
                ),
                Row(
                    Column(Field('apartment_type'), css_class='col-md-6'),
                ),

                # Optional wrapper to ensure checkboxes render well
                Div(
                    Fieldset(
                        'Amenities',
                        InlineCheckboxes('amenities'),
                    ),
                    css_class="custom-amenities-checkboxes mb-3"
                ),

                Row(
                    Column(Field('rent_price', placeholder="e.g., 3200"), css_class='col-md-4'),
                    Column(Field('net_price', placeholder="e.g., 3000"), css_class='col-md-4'),
                    Column(Field('deposit_price', placeholder="e.g., 500"), css_class='col-md-4'),
                ),
                Field('description'),
                Row(
                    Column(Field('status'), css_class='col-md-6'),
                    Column(Field('lock_type', placeholder="e.g., Smart Lock"), css_class='col-md-6'),
                ),
            ),

            Fieldset(
                'Additional Details',
                Row(
                    Column(Field('broker_fee_required'), css_class='col-md-6'),
                    Column(Field('paid_months', placeholder="e.g., 2"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('lease_duration', placeholder="e.g., 12 months"), css_class='col-md-6'),
                    Column(Field('holding_deposit', placeholder="e.g., 500"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('free_stuff', placeholder="e.g., Free Netflix"), css_class='col-md-6'),
                ),
                Field('required_documents'),
            ),

            Submit('apartment_submit', 'Save Apartment', css_class='btn btn-primary'),
        )


class ApartmentImageForm(forms.ModelForm):
    class Meta:
        model = ApartmentImage
        fields = ['image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'


class ApartmentConcessionForm(forms.ModelForm):
    class Meta:
        model = ApartmentConcession
        fields = ['months_free', 'lease_terms', 'special_offer_id', 'name']


class BrokerContactForm(forms.Form):
    CONTACT_TYPE_CHOICES = [
        ('request_tour', 'Schedule a Tour'),
        ('ask_question', 'Ask a Question'),
    ]
    TOUR_TYPE_CHOICES = [
        ('in_person', 'In Person'),
        ('video_chat', 'Video Chat'),
    ]

    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=True)
    contact_type = forms.ChoiceField(choices=CONTACT_TYPE_CHOICES, required=True)
    
    # Tour fields
    tour_type = forms.ChoiceField(choices=TOUR_TYPE_CHOICES, required=False)
    preferred_datetime_1 = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M'])
    preferred_datetime_2 = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M'])
    preferred_datetime_3 = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M'])
    
    # Question fields
    question = forms.CharField(widget=forms.Textarea, required=False)

    def clean(self):
        cleaned_data = super().clean()
        contact_type = cleaned_data.get('contact_type')
        
        if contact_type == 'request_tour':
            if not cleaned_data.get('tour_type'):
                self.add_error('tour_type', 'This field is required for tours.')
            # We enforce at least one time is picked ideally, but keeping it flexible
        
        elif contact_type == 'ask_question':
            if not cleaned_data.get('question'):
                self.add_error('question', 'Please enter your question.')
                
        return cleaned_data