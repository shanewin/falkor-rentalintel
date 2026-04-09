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

    # Sequential field tracking — one question at a time
    current_field_index = models.IntegerField(
        default=0,
        help_text="Index into requested_fields — which field we're currently asking about"
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

    @property
    def current_field(self):
        """Returns the field dict we're currently asking about, or None if done."""
        if self.current_field_index < len(self.requested_fields):
            return self.requested_fields[self.current_field_index]
        return None

    @property
    def next_field(self):
        """Returns the field dict that comes after the current one, or None."""
        next_idx = self.current_field_index + 1
        if next_idx < len(self.requested_fields):
            return self.requested_fields[next_idx]
        return None

    @property
    def fields_remaining(self):
        """How many fields are left to ask (including current)."""
        return max(0, len(self.requested_fields) - self.current_field_index)

    def advance_field(self):
        """Move to the next field in the sequence."""
        self.current_field_index += 1
        self.save(update_fields=['current_field_index', 'updated_at'])

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
# priority: 'required' = ask via SMS, 'optional' = allowed but don't ask
#           'conditional' = ask only when a related field triggers it
# ──────────────────────────────────────────────

SMS_SAFE_FIELDS = {
    'personal_info': {
        # ── Required: core identity & contact ──
        'first_name':            {'label': 'First Name', 'type': 'str', 'priority': 'required'},
        'last_name':             {'label': 'Last Name', 'type': 'str', 'priority': 'required'},
        'email':                 {'label': 'Email Address', 'type': 'str', 'priority': 'required'},
        'phone_cell':            {'label': 'Phone Number', 'type': 'str', 'priority': 'required'},
        'date_of_birth':         {'label': 'Date of Birth', 'type': 'date', 'priority': 'required'},

        # ── Required: current address ──
        'street_address_1':      {'label': 'Street Address', 'type': 'str', 'priority': 'required'},
        'city':                  {'label': 'City', 'type': 'str', 'priority': 'required'},
        'state':                 {'label': 'State', 'type': 'str', 'priority': 'required'},
        'zip_code':              {'label': 'Zip Code', 'type': 'str', 'priority': 'required'},
        'current_address_years': {'label': 'Years at Current Address', 'type': 'int', 'priority': 'required'},
        'current_address_months':{'label': 'Months at Current Address', 'type': 'int', 'priority': 'required'},

        # ── Required: housing ──
        'housing_status':        {'label': 'Housing Status (Own/Rent)', 'type': 'str', 'priority': 'required'},
        'has_pets':              {'label': 'Do You Have Pets (Yes/No)', 'type': 'bool', 'priority': 'required'},
        'reason_for_moving':     {'label': 'Reason for Moving', 'type': 'str', 'priority': 'required'},
        'referral_source':       {'label': 'How Did You Hear About Us', 'type': 'str', 'priority': 'required'},
        'reference1_name':       {'label': 'Reference 1 Name', 'type': 'str', 'priority': 'required'},
        'reference1_phone':      {'label': 'Reference 1 Phone', 'type': 'str', 'priority': 'required'},

        # ── Conditional: landlord (only if renting) ──
        'current_monthly_rent':  {'label': 'Current Monthly Rent', 'type': 'decimal', 'priority': 'conditional', 'condition': 'housing_status==Rent'},
        'landlord_name':         {'label': 'Landlord Name', 'type': 'str', 'priority': 'conditional', 'condition': 'housing_status==Rent'},
        'landlord_phone':        {'label': 'Landlord Phone', 'type': 'str', 'priority': 'conditional', 'condition': 'housing_status==Rent'},
        'landlord_email':        {'label': 'Landlord Email', 'type': 'str', 'priority': 'conditional', 'condition': 'housing_status==Rent'},

        # ── Optional: not worth SMS-asking ──
        'middle_name':           {'label': 'Middle Name', 'type': 'str', 'priority': 'optional'},
        'suffix':                {'label': 'Suffix', 'type': 'str', 'priority': 'optional'},
        'street_address_2':      {'label': 'Apt/Unit', 'type': 'str', 'priority': 'optional'},
        'reference2_name':       {'label': 'Reference 2 Name', 'type': 'str', 'priority': 'optional'},
        'reference2_phone':      {'label': 'Reference 2 Phone', 'type': 'str', 'priority': 'optional'},
    },
    'income_info': {
        # ── Conditional on employed ──
        'currently_employed':    {'label': 'Currently Employed (Yes/No)', 'type': 'bool', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'employer':              {'label': 'Employer Name', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'job_title':             {'label': 'Job Title', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'annual_income':         {'label': 'Annual Income', 'type': 'decimal', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'supervisor_name':       {'label': 'Supervisor Name', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'supervisor_email':      {'label': 'Supervisor Email', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'supervisor_phone':      {'label': 'Supervisor Phone', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==employed'},
        'start_date':            {'label': 'Employment Start Date', 'type': 'date', 'priority': 'conditional', 'condition': 'employment_type==employed'},

        # ── Conditional on student ──
        'school_name':           {'label': 'School Name', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==student'},
        'year_of_graduation':    {'label': 'Graduation Year', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==student'},
        'school_address':        {'label': 'School Address', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==student'},
        'school_phone':          {'label': 'School Phone', 'type': 'str', 'priority': 'conditional', 'condition': 'employment_type==student'},

        # ── Optional: not worth SMS-asking ──
        'end_date':              {'label': 'Employment End Date', 'type': 'date', 'priority': 'optional'},
        'employment_length':     {'label': 'How Long at This Job', 'type': 'str', 'priority': 'optional'},
        'additional_income_source': {'label': 'Additional Income Source', 'type': 'str', 'priority': 'optional'},
        'additional_income_amount': {'label': 'Additional Income Amount', 'type': 'decimal', 'priority': 'optional'},
    },
}


def get_missing_safe_fields(application):
    """
    Inspects an application's PersonalInfoData and IncomeData,
    returns a list of missing fields that are REQUIRED (or active CONDITIONAL)
    and safe to collect via SMS.

    Conditionals are evaluated against the current model state:
    - Landlord fields only asked if housing_status == 'Rent'
    - Employment fields only asked if employment_type == 'employed'
    - Student fields only asked if employment_type == 'student'

    Returns: [{'model': 'personal_info', 'field': 'employer', 'label': 'Employer Name', 'type': 'str'}, ...]
    """
    missing = []

    def _is_empty(val):
        if val is None:
            return True
        if isinstance(val, str) and not val.strip():
            return True
        return False

    def _check_condition(condition_str, model_instance):
        """Evaluate a simple 'field==value' condition against a model instance."""
        if not condition_str:
            return True
        field, expected = condition_str.split('==', 1)
        actual = getattr(model_instance, field, None)
        return str(actual).lower() == expected.lower()

    # Check PersonalInfoData
    personal_info = getattr(application, 'personal_info', None)
    if personal_info:
        for field_name, meta in SMS_SAFE_FIELDS['personal_info'].items():
            priority = meta.get('priority')
            if priority == 'optional':
                continue
            # For conditional fields, check if the condition is met
            if priority == 'conditional':
                condition = meta.get('condition', '')
                if not _check_condition(condition, personal_info):
                    continue
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
            priority = meta.get('priority')
            if priority == 'optional':
                continue
            # For conditional fields, check if the condition is met
            if priority == 'conditional':
                condition = meta.get('condition', '')
                if not _check_condition(condition, income_info):
                    continue
            val = getattr(income_info, field_name, None)
            if _is_empty(val):
                missing.append({
                    'model': 'income_info',
                    'field': field_name,
                    'label': meta['label'],
                    'type': meta['type'],
                })

    return missing

