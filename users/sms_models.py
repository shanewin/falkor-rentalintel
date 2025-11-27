"""
SMS Preferences and Verification Models
Stores user SMS preferences and verification status
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import RegexValidator


class SMSPreferences(models.Model):
    """
    User SMS notification preferences and verification status
    """
    
    FREQUENCY_CHOICES = [
        ('all', 'All notifications'),
        ('important', 'Important only'),
        ('urgent', 'Urgent only'),
        ('none', 'No SMS notifications')
    ]
    
    # User relationship
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sms_preferences'
    )
    
    # Phone number and verification
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{10,15}$',
                message="Enter a valid phone number."
            )
        ]
    )
    
    phone_verified = models.BooleanField(
        default=False,
        help_text="Has the phone number been verified via OTP"
    )
    
    phone_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the phone was last verified"
    )
    
    # SMS preferences
    sms_enabled = models.BooleanField(
        default=False,
        help_text="User has opted in to receive SMS"
    )
    
    sms_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default='important'
    )
    
    # TCPA Compliance
    tcpa_consent = models.BooleanField(
        default=False,
        help_text="User has given TCPA consent for automated texts"
    )
    
    tcpa_consent_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When TCPA consent was given"
    )
    
    tcpa_consent_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address when consent was given"
    )
    
    # Notification types (JSON array)
    notification_types = models.JSONField(
        default=list,
        help_text="Types of notifications user wants via SMS"
    )
    
    # Quiet hours
    quiet_hours_enabled = models.BooleanField(
        default=False,
        help_text="Don't send SMS during quiet hours"
    )
    
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        help_text="Start of quiet hours (user's timezone)"
    )
    
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        help_text="End of quiet hours (user's timezone)"
    )
    
    # User timezone for quiet hours
    timezone = models.CharField(
        max_length=50,
        default='America/New_York',
        help_text="User's timezone for quiet hours"
    )
    
    # Opt-out tracking
    opted_out = models.BooleanField(
        default=False,
        help_text="User has opted out via STOP command"
    )
    
    opted_out_date = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Statistics
    total_sms_sent = models.PositiveIntegerField(
        default=0,
        help_text="Total SMS messages sent to this number"
    )
    
    last_sms_sent = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last SMS was sent"
    )
    
    failed_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of failed SMS delivery attempts"
    )
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'SMS Preferences'
        verbose_name_plural = 'SMS Preferences'
    
    def __str__(self):
        return f"{self.user.email} - SMS {'Enabled' if self.sms_enabled else 'Disabled'}"
    
    def can_send_sms(self) -> bool:
        """Check if SMS can be sent to this user"""
        return all([
            self.phone_number,
            self.phone_verified,
            self.sms_enabled,
            self.tcpa_consent,
            not self.opted_out
        ])
    
    def is_in_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours"""
        if not self.quiet_hours_enabled:
            return False
        
        # TODO: Implement timezone-aware quiet hours check
        from datetime import datetime
        import pytz
        
        try:
            user_tz = pytz.timezone(self.timezone)
            now = datetime.now(user_tz).time()
            
            if self.quiet_hours_start <= self.quiet_hours_end:
                # Normal case: quiet hours don't cross midnight
                return self.quiet_hours_start <= now <= self.quiet_hours_end
            else:
                # Quiet hours cross midnight
                return now >= self.quiet_hours_start or now <= self.quiet_hours_end
        except:
            return False
    
    def record_sms_sent(self):
        """Record that an SMS was sent"""
        self.total_sms_sent += 1
        self.last_sms_sent = timezone.now()
        self.save(update_fields=['total_sms_sent', 'last_sms_sent'])
    
    def record_opt_out(self):
        """Record user opt-out"""
        self.opted_out = True
        self.opted_out_date = timezone.now()
        self.sms_enabled = False
        self.save(update_fields=['opted_out', 'opted_out_date', 'sms_enabled'])
    
    def verify_phone(self, ip_address=None):
        """Mark phone as verified"""
        self.phone_verified = True
        self.phone_verified_at = timezone.now()
        if not self.tcpa_consent_date:
            self.tcpa_consent_date = timezone.now()
            if ip_address:
                self.tcpa_consent_ip = ip_address
        self.save()


class SMSVerificationLog(models.Model):
    """
    Log of SMS verification attempts for audit and security
    """
    
    STATUS_CHOICES = [
        ('sent', 'Code Sent'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('expired', 'Code Expired'),
        ('rate_limited', 'Rate Limited')
    ]
    
    # User and phone
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_verifications'
    )
    
    phone_number = models.CharField(max_length=20)
    
    # Verification details
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES
    )
    
    purpose = models.CharField(
        max_length=50,
        help_text="Purpose of verification (registration, 2fa, etc)"
    )
    
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of verification attempts"
    )
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    
    # SMS details
    sms_sid = models.CharField(
        max_length=100,
        blank=True,
        help_text="Twilio message SID"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} - {self.status} ({self.created_at})"


class SMSMessage(models.Model):
    """
    Log of all SMS messages sent for tracking and compliance
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('undelivered', 'Undelivered')
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ('verification', 'Verification Code'),
        ('2fa', 'Two-Factor Auth'),
        ('notification', 'Notification'),
        ('reminder', 'Reminder'),
        ('alert', 'Alert'),
        ('marketing', 'Marketing')
    ]
    
    # Recipient
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_messages'
    )
    
    phone_number = models.CharField(max_length=20)
    
    # Message details
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES
    )
    
    message = models.TextField()
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Twilio tracking
    sms_sid = models.CharField(
        max_length=100,
        blank=True,
        help_text="Twilio message SID"
    )
    
    error_message = models.TextField(blank=True)
    
    # Cost tracking
    segments = models.PositiveIntegerField(
        default=1,
        help_text="Number of SMS segments"
    )
    
    cost = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Cost in USD"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Related object (optional)
    content_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Related object type (e.g., 'application', 'appointment')"
    )
    
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Related object ID"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.phone_number} - {self.message_type} - {self.status}"
    
    def calculate_segments(self):
        """Calculate number of SMS segments based on message length"""
        msg_len = len(self.message)
        if msg_len <= 160:
            return 1
        elif msg_len <= 306:
            return 2
        else:
            return ((msg_len - 307) // 153) + 3
    
    def save(self, *args, **kwargs):
        if not self.segments:
            self.segments = self.calculate_segments()
        if self.segments and not self.cost:
            # Approximate cost (Twilio US pricing)
            self.cost = self.segments * 0.0079
        super().save(*args, **kwargs)