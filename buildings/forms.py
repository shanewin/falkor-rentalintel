from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from .models import Building, BuildingImage, BuildingAccess, BuildingSpecial, Amenity
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit, Field, HTML, Row, Column, Div
from crispy_forms.bootstrap import InlineCheckboxes

class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),

            'internal_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),

            'zip_code': forms.TextInput(attrs={
                'pattern': '[0-9]{5}(-[0-9]{4})?',
                'class': 'form-control'
            }),

            # Currency fields
            'credit_screening_fee': forms.NumberInput(attrs={
                'class': 'form-control currency-field', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'hold_deposit': forms.NumberInput(attrs={
                'class': 'form-control currency-field', 
                'step': '0.01',
                'placeholder': '0.00'
            }),
            # Select2 fields
            'neighborhood': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Neighborhood'
            }),
            'pet_policy': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Pet Policy'
            }),
            'commission_pay_type': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Commission Type'
            }),
            'state': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select State'
            }),
            'credit_screening_payment_method': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Payment Method'
            }),
            'hold_deposit_payment_method': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Payment Method'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Force checkboxes for amenities
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = Amenity.objects.all().order_by('name')
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'  # Main form class

        # Remove bold from labels and add help icons where needed
        for field_name, field in self.fields.items():
            field.label_suffix = ''  # Removes colon
            if field.required:
                field.widget.attrs['required'] = 'required'
        
        # Add help icon to name field label
        self.fields['name'].label = mark_safe('Name')
        
        # Set amenities label to be a normal field label like Pet Policy
        self.fields['amenities'].label = 'Building Amenities'
        
        # Set up brokers field with checkboxes
        from users.models import User
        self.fields['brokers'].widget = forms.CheckboxSelectMultiple()
        self.fields['brokers'].queryset = User.objects.filter(is_broker=True).order_by('email')
        self.fields['brokers'].label = 'Brokers'
        
        # Convert owner field to ChoiceField with existing owners
        owner_choices = [('', 'Select Owner')] + [(user.email, user.email) for user in User.objects.filter(is_owner=True)]
        
        # Replace the CharField with a ChoiceField
        self.fields['owner_name'] = forms.ChoiceField(
            choices=owner_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select Owner'
            })
        )
        
        # Remove empty options completely and use Select2 placeholders instead
        self.fields['state'].empty_label = None
        self.fields['neighborhood'].empty_label = None 
        self.fields['pet_policy'].empty_label = None
        self.fields['commission_pay_type'].empty_label = None
        self.fields['credit_screening_payment_method'].empty_label = None
        self.fields['hold_deposit_payment_method'].empty_label = None
        
        # Simple layout without complex components
        self.helper.layout = Layout(
            Fieldset(
                '',
                Field('name', template='buildings/name_field.html'),
                Row(
                    Column('street_address_1', css_class='col-md-8'),
                    Column('street_address_2', css_class='col-md-4'),
                ),
                Row(
                    Column('city', css_class='col-md-5'),
                    Column('state', css_class='col-md-3'),
                    Column('zip_code', css_class='col-md-4'),
                ),
                'neighborhood'
            ),
            Fieldset(
                'Financial Information',
                Row(
                    Column(Field('credit_screening_fee', template='buildings/currency_field.html'), css_class='col-md-6'),
                    Column('credit_screening_payment_method', css_class='col-md-6'),
                ),
                Row(
                    Column(Field('hold_deposit', template='buildings/currency_field.html'), css_class='col-md-6'),
                    Column('hold_deposit_payment_method', css_class='col-md-6'),
                )
            ),
            Fieldset(
                'Property Features',
                'pet_policy',
                # Amenities with checkboxes - use Field to avoid fieldset wrapper
                Field('amenities', template='buildings/amenities_field.html'),
                Field('description', template='buildings/description_field.html')
            ),
            Fieldset(
                'Management & Commission',
                'owner_name',
                Field('brokers', template='buildings/brokers_field.html'),
                'commission_pay_type',
                Row(
                    Column(Field('commission_owner_percent', template='buildings/percent_field.html'), css_class='col-md-6 commission-percent-field'),
                    Column(Field('commission_tenant_percent', template='buildings/percent_field.html'), css_class='col-md-6 commission-percent-field'),
                )
            ),
            Fieldset(
                'Additional Information',
                'internal_notes'
            ),
            Div(
                Submit('building_submit', 'Save & Continue', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'buildings_list\' %}" class="btn btn-doorway-secondary btn-lg">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )

    def clean_zip_code(self):
        zip_code = self.cleaned_data.get('zip_code')
        if zip_code and not zip_code.replace('-', '').isdigit():
            raise ValidationError('Enter a valid ZIP code')
        return zip_code

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate commission percentages sum to 100% when both owner and tenant pay
        commission_pay_type = cleaned_data.get('commission_pay_type')
        if commission_pay_type == 'owner_and_tenant_pays':
            owner_percent = cleaned_data.get('commission_owner_percent')
            tenant_percent = cleaned_data.get('commission_tenant_percent')
            
            if owner_percent is not None and tenant_percent is not None:
                total = owner_percent + tenant_percent
                if total != 100:
                    raise ValidationError(
                        f'Owner and tenant commission percentages must total 100%. Currently: {total}%'
                    )
            elif owner_percent is not None or tenant_percent is not None:
                raise ValidationError(
                    'Both owner and tenant commission percentages are required when "Owner and Tenant Pays" is selected.'
                )
        
        return cleaned_data


class BuildingImageForm(forms.ModelForm):
    class Meta:
        model = BuildingImage
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            })
        }

    def __init__(self, *args, **kwargs):
        building_id = kwargs.pop('building_id', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_enctype = 'multipart/form-data'
        self.helper.form_class = 'doorway-form'
        
        # Remove label and help text since they're in card header
        self.fields['image'].label = ''
        self.fields['image'].help_text = ''
        
        if building_id:
            skip_url = f'/buildings/{building_id}/step3/'
        else:
            skip_url = '#'
            
        self.helper.layout = Layout(
            Field('image', css_class='form-control auto-upload-field'),
            Div(
                HTML(f'<a href="{skip_url}" class="btn btn-doorway-secondary btn-lg">Skip This Step</a>'),
                css_class='text-center mt-4'
            )
        )


class BuildingAccessForm(forms.ModelForm):
    class Meta:
        model = BuildingAccess
        fields = ['location', 'access_type', 'pin_code', 'custom_note']
        widgets = {
            'custom_note': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Access Information',
                'location',
                'access_type',
                'pin_code',
                'custom_note'
            ),
            Submit('submit', 'Save Access', css_class='btn btn-primary')
        )


class BuildingSpecialForm(forms.ModelForm):
    class Meta:
        model = BuildingSpecial
        fields = ['special_type', 'name', 'months_free', 'additional_info']
        widgets = {
            'additional_info': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Special Offer',
                Row(
                    Column('special_type', css_class='col-md-6'),
                    Column('name', css_class='col-md-6'),
                ),
                'months_free',
                'additional_info',
            ),
            Submit('submit', 'Save Special', css_class='btn btn-primary')
        )