from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class SMSConversation(models.Model):
    """
    Tracks a multi-turn AI SMS conversation between the platform and an applicant.
    Created when a broker clicks "Remind Missing Fields" on an application.
    Expires after 24 hours.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
    ]

    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='sms_conversations'
    )
    phone_number = models.CharField(max_length=20, help_text="Applicant's phone number (E.164)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # What fields we're trying to collect
    requested_fields = models.JSONField(
        default=list,
        help_text="List of dicts: [{'model': 'personal_info', 'field': 'employer', 'label': 'Employer Name'}, ...]"
    )
    collected_fields = models.JSONField(
        default=dict,
        help_text="Dict of field_name -> value that have been extracted and saved"
    )

    # Full conversation history for AI context
    messages = models.JSONField(
        default=list,
        help_text="List of dicts: [{'role': 'assistant', 'content': '...'}, {'role': 'user', 'content': '...'}]"
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_sms_conversations'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(help_text="Conversation expires after 24 hours")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SMS Conversation for App #{self.application_id} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        if self.status != 'active':
            return False
        if timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save(update_fields=['status'])
            return False
        return True

    @property
    def pending_fields(self):
        """Returns list of field dicts that haven't been collected yet."""
        collected_keys = set(self.collected_fields.keys())
        return [f for f in self.requested_fields if f['field'] not in collected_keys]

    def add_message(self, role, content):
        """Append a message to the conversation history."""
        self.messages.append({'role': role, 'content': content})
        self.save(update_fields=['messages', 'updated_at'])

    def mark_field_collected(self, field_name, value):
        """Record that a field has been successfully extracted and saved."""
        self.collected_fields[field_name] = str(value)
        self.save(update_fields=['collected_fields', 'updated_at'])

    def complete(self):
        """Mark the conversation as completed."""
        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])


# ──────────────────────────────────────────────
# Whitelist of fields safe to collect via SMS
# ──────────────────────────────────────────────

SMS_SAFE_FIELDS = {
    'personal_info': {
        'first_name': {'label': 'First Name', 'type': 'str'},
        'last_name': {'label': 'Last Name', 'type': 'str'},
        'middle_name': {'label': 'Middle Name', 'type': 'str'},
        'suffix': {'label': 'Suffix', 'type': 'str'},
        'email': {'label': 'Email Address', 'type': 'str'},
        'phone_cell': {'label': 'Phone Number', 'type': 'str'},
        'date_of_birth': {'label': 'Date of Birth', 'type': 'date'},
        'street_address_1': {'label': 'Street Address', 'type': 'str'},
        'street_address_2': {'label': 'Apt/Unit', 'type': 'str'},
        'city': {'label': 'City', 'type': 'str'},
        'state': {'label': 'State', 'type': 'str'},
        'zip_code': {'label': 'Zip Code', 'type': 'str'},
        'current_address_years': {'label': 'Years at Current Address', 'type': 'int'},
        'current_address_months': {'label': 'Months at Current Address', 'type': 'int'},
        'housing_status': {'label': 'Housing Status (Own/Rent)', 'type': 'str'},
        'current_monthly_rent': {'label': 'Monthly Rent', 'type': 'decimal'},
        'landlord_name': {'label': 'Landlord Name', 'type': 'str'},
        'landlord_phone': {'label': 'Landlord Phone', 'type': 'str'},
        'landlord_email': {'label': 'Landlord Email', 'type': 'str'},
        'desired_move_in_date': {'label': 'Desired Move-In Date', 'type': 'date'},
        'referral_source': {'label': 'How Did You Hear About Us', 'type': 'str'},
        'has_pets': {'label': 'Do You Have Pets (Yes/No)', 'type': 'bool'},
        'reference1_name': {'label': 'Reference 1 Name', 'type': 'str'},
        'reference1_phone': {'label': 'Reference 1 Phone', 'type': 'str'},
        'reference2_name': {'label': 'Reference 2 Name', 'type': 'str'},
        'reference2_phone': {'label': 'Reference 2 Phone', 'type': 'str'},
        'reason_for_moving': {'label': 'Reason for Moving', 'type': 'str'},
    },
    'income_info': {
        'employer': {'label': 'Employer Name', 'type': 'str'},
        'job_title': {'label': 'Job Title', 'type': 'str'},
        'annual_income': {'label': 'Annual Income', 'type': 'decimal'},
        'employment_length': {'label': 'How Long at This Job', 'type': 'str'},
        'supervisor_name': {'label': 'Supervisor Name', 'type': 'str'},
        'supervisor_email': {'label': 'Supervisor Email', 'type': 'str'},
        'supervisor_phone': {'label': 'Supervisor Phone', 'type': 'str'},
        'currently_employed': {'label': 'Currently Employed (Yes/No)', 'type': 'bool'},
        'start_date': {'label': 'Employment Start Date', 'type': 'date'},
        'end_date': {'label': 'Employment End Date', 'type': 'date'},
        'school_name': {'label': 'School Name', 'type': 'str'},
        'year_of_graduation': {'label': 'Graduation Year', 'type': 'str'},
        'school_address': {'label': 'School Address', 'type': 'str'},
        'school_phone': {'label': 'School Phone', 'type': 'str'},
        'additional_income_source': {'label': 'Additional Income Source', 'type': 'str'},
        'additional_income_amount': {'label': 'Additional Income Amount', 'type': 'decimal'},
    },
}


def get_missing_safe_fields(application):
    """
    Inspects an application's PersonalInfoData and IncomeData,
    returns a list of missing fields that are safe to collect via SMS.
    
    Returns: [{'model': 'personal_info', 'field': 'employer', 'label': 'Employer Name', 'type': 'str'}, ...]
    """
    missing = []

    def _is_empty(val):
        if val is None:
            return True
        if isinstance(val, str) and not val.strip():
            return True
        return False

    # Check PersonalInfoData
    personal_info = getattr(application, 'personal_info', None)
    if personal_info:
        for field_name, meta in SMS_SAFE_FIELDS['personal_info'].items():
            val = getattr(personal_info, field_name, None)
            if _is_empty(val):
                missing.append({
                    'model': 'personal_info',
                    'field': field_name,
                    'label': meta['label'],
                    'type': meta['type'],
                })

    # Check IncomeData
    income_info = getattr(application, 'income_info', None)
    if income_info:
        for field_name, meta in SMS_SAFE_FIELDS['income_info'].items():
            val = getattr(income_info, field_name, None)
            if _is_empty(val):
                missing.append({
                    'model': 'income_info',
                    'field': field_name,
                    'label': meta['label'],
                    'type': meta['type'],
                })

    return missing
