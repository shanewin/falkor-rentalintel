"""
Enhanced registration forms with SMS opt-in and verification
Provides TCPA-compliant SMS consent during registration
"""

from django import forms
from .models import User


class PhoneVerificationMixin:
    """
    Mixin to add phone verification fields to forms
    """
    
    def clean_phone_number(self):
        """Clean and validate phone number, removing formatting"""
        phone = self.cleaned_data.get('phone_number', '')
        
        if not phone:
            return ''
        
        # Strip all non-digit characters (parentheses, dashes, spaces)
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        
        # Handle different formats
        if cleaned_phone.startswith('1') and len(cleaned_phone) == 11:
            # US number with country code
            cleaned_phone = cleaned_phone  # Keep as is
        elif len(cleaned_phone) == 10:
            # US number without country code - this is fine
            cleaned_phone = cleaned_phone
        elif len(cleaned_phone) > 15 or len(cleaned_phone) < 10:
            raise forms.ValidationError(
                "Please enter a valid 10-digit phone number."
            )
        
        return cleaned_phone
    
    def add_phone_fields(self):
        """Add phone and SMS consent fields to form"""
        self.fields['phone_number'] = forms.CharField(
            required=False,
            # Remove the regex validator - we'll handle it in clean_phone_number
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(555) 123-4567',
                'data-phone-input': 'true'
            }),
            help_text="We'll use this to send important updates about your application"
        )
        
        self.fields['sms_opt_in'] = forms.BooleanField(
            required=False,
            widget=forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-sms-consent': 'true'
            }),
            label="Send me SMS updates about my application status",
            help_text="Message and data rates may apply. Reply STOP to unsubscribe."
        )
        
        self.fields['verify_phone'] = forms.BooleanField(
            required=False,
            initial=True,
            widget=forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'data-verify-phone': 'true'
            }),
            label="Verify my phone number (recommended for security)"
        )


class ApplicantRegistrationWithSMSForm(forms.ModelForm, PhoneVerificationMixin):
    """
    Enhanced applicant registration form with SMS opt-in
    """
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    # TCPA Compliance
    tcpa_consent = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-tcpa-consent': 'true'
        }),
        label="I agree to receive automated text messages from DoorWay",
        help_text=(
            "By checking this box, you consent to receive automated text messages from DoorWay "
            "regarding your rental application. Message frequency varies. Message and data rates may apply. "
            "Text STOP to cancel. Text HELP for help. View our Privacy Policy and Terms of Service."
        )
    )
    
    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your email address',
                'required': True
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_phone_fields()
        
        # Reorder fields for better UX
        field_order = [
            'email', 'first_name', 'last_name',
            'phone_number', 'sms_opt_in', 'tcpa_consent', 'verify_phone',
            'password', 'password_confirm'
        ]
        new_fields = {}
        for field_name in field_order:
            if field_name in self.fields:
                new_fields[field_name] = self.fields[field_name]
        self.fields = new_fields
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        phone_number = cleaned_data.get('phone_number')
        sms_opt_in = cleaned_data.get('sms_opt_in')
        tcpa_consent = cleaned_data.get('tcpa_consent')
        
        # Password validation
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError("Passwords don't match")
        
        # SMS consent validation
        if sms_opt_in and not phone_number:
            raise forms.ValidationError(
                "Please provide a phone number to receive SMS updates"
            )
        
        # TCPA compliance
        if sms_opt_in and not tcpa_consent:
            raise forms.ValidationError(
                "You must agree to receive text messages to opt-in for SMS updates"
            )
        
        return cleaned_data


class BrokerRegistrationWithSMSForm(forms.ModelForm, PhoneVerificationMixin):
    """
    Enhanced broker registration form with SMS opt-in
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    )
    
    # Professional phone for brokers
    business_phone = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Business phone number',
            'data-phone-input': 'true'
        }),
        help_text="Your professional contact number"
    )
    
    # SMS preferences for brokers
    sms_notifications = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        choices=[
            ('new_lead', 'New applicant leads'),
            ('app_complete', 'Application completions'),
            ('urgent', 'Urgent notifications only'),
            ('reminders', 'Appointment reminders'),
            ('updates', 'System updates')
        ],
        label="SMS notification preferences"
    )
    
    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your business email'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_phone_fields()
        # Remove verify_phone for brokers (always verify)
        self.fields['verify_phone'].initial = True
        self.fields['verify_phone'].widget = forms.HiddenInput()
    
    def clean_business_phone(self):
        """Clean and validate business phone number"""
        phone = self.cleaned_data.get('business_phone', '')
        
        if not phone:
            return ''
        
        # Strip all non-digit characters
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        
        # Validate length
        if len(cleaned_phone) == 11 and cleaned_phone.startswith('1'):
            cleaned_phone = cleaned_phone  # US number with country code
        elif len(cleaned_phone) == 10:
            cleaned_phone = cleaned_phone  # US number without country code
        else:
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        
        return cleaned_phone
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm:
            if password != password_confirm:
                raise forms.ValidationError("Passwords don't match")
        
        return cleaned_data


class PhoneVerificationForm(forms.Form):
    """
    Form for entering OTP verification code
    """
    verification_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center verification-code-input',
            'placeholder': '000000',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'maxlength': '6',
            'data-verification-input': 'true'
        }),
        help_text="Enter the 6-digit code we sent to your phone"
    )
    
    def clean_verification_code(self):
        code = self.cleaned_data.get('verification_code')
        if code and not code.isdigit():
            raise forms.ValidationError("Verification code must contain only numbers")
        return code


class SMSPreferencesForm(forms.Form):
    """
    Form for managing SMS preferences in user settings
    """
    SMS_FREQUENCY_CHOICES = [
        ('all', 'All notifications'),
        ('important', 'Important only'),
        ('urgent', 'Urgent only'),
        ('none', 'No SMS notifications')
    ]
    
    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '(555) 123-4567',
            'data-phone-input': 'true'
        })
    )
    
    phone_verified = forms.BooleanField(
        required=False,
        disabled=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'readonly': 'readonly'
        }),
        label="Phone number verified"
    )
    
    sms_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Enable SMS notifications"
    )
    
    sms_frequency = forms.ChoiceField(
        choices=SMS_FREQUENCY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        initial='important'
    )
    
    notification_types = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        choices=[
            ('status_change', 'Application status changes'),
            ('deadlines', 'Important deadlines'),
            ('viewings', 'Viewing appointments'),
            ('documents', 'Document requests'),
            ('reminders', 'General reminders'),
            ('offers', 'Special offers and updates')
        ],
        label="Notification types to receive via SMS"
    )
    
    quiet_hours_enabled = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Enable quiet hours (no SMS during specified times)"
    )
    
    quiet_hours_start = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        }),
        initial='22:00'
    )
    
    quiet_hours_end = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'class': 'form-control',
            'type': 'time'
        }),
        initial='08:00'
    )
    
    def clean_phone_number(self):
        """Clean and validate phone number"""
        phone = self.cleaned_data.get('phone_number', '')
        
        if not phone:
            return ''
        
        # Strip all non-digit characters
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        
        # Validate length
        if len(cleaned_phone) == 11 and cleaned_phone.startswith('1'):
            cleaned_phone = cleaned_phone  # US number with country code
        elif len(cleaned_phone) == 10:
            cleaned_phone = cleaned_phone  # US number without country code
        else:
            raise forms.ValidationError("Please enter a valid 10-digit phone number.")
        
        return cleaned_phone
    
    def clean(self):
        cleaned_data = super().clean()
        sms_enabled = cleaned_data.get('sms_enabled')
        phone_number = cleaned_data.get('phone_number')
        
        if sms_enabled and not phone_number:
            raise forms.ValidationError(
                "Please provide a phone number to enable SMS notifications"
            )
        
        quiet_hours_enabled = cleaned_data.get('quiet_hours_enabled')
        quiet_hours_start = cleaned_data.get('quiet_hours_start')
        quiet_hours_end = cleaned_data.get('quiet_hours_end')
        
        if quiet_hours_enabled:
            if not quiet_hours_start or not quiet_hours_end:
                raise forms.ValidationError(
                    "Please specify both start and end times for quiet hours"
                )
        
        return cleaned_data