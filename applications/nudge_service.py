from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import ApplicationActivity
from applicants.models import InteractionLog, ApplicantCRM
from applications.sms_utils import SMSBackend

class NudgeService:
    """
    Service for sending reminders (nudges) to applicants
    to complete their applications or upload documents.
    Supports both Email and SMS.
    """

    @staticmethod
    def send_nudge(target, user, nudge_type='email', custom_message=None):
        """
        Send a nudge to the applicant.
        
        Args:
            target: The Application OR Applicant instance
            user: The Broker/User sending the nudge
            nudge_type: 'email' or 'sms'
            custom_message: Optional custom text to include
            
        Returns:
            Tuple (success: bool, error_message: str or None)
        """
        # Determine if target is Application or Applicant
        application = None
        applicant = None
        
        if hasattr(target, 'applicant'): # It's an Application
            application = target
            applicant = application.applicant
        else: # It's an Applicant
            applicant = target
            # Try to find latest application for context if needed, but not strictly required
            application = applicant.applications.order_by('-created_at').first()

        if not applicant:
            return False, "Invalid target."

        if nudge_type == 'email':
            return NudgeService._send_email_nudge(applicant, application, user, custom_message)
        elif nudge_type == 'sms':
            return NudgeService._send_sms_nudge(applicant, application, user, custom_message)
        
        return False, f"Invalid nudge type: {nudge_type}"

    @staticmethod
    def _send_email_nudge(applicant, application, user, custom_message=None):
        if not applicant.email:
            return False, "Applicant has no email."

        context_str = f" for {application.get_address_display()}" if application else ""
        subject = f"Action Required: Your Application{context_str}"
        
        # Construct message
        link = f"{settings.SITE_URL}/"
        if application:
            link = f"{settings.SITE_URL}/applications/complete/{application.unique_link}/"
        
        # Simple text template
        message_body = f"""
Dear {applicant.first_name},

This is a reminder from your broker, {user.first_name} {user.last_name}{',' + context_str if context_str else ''}.

{custom_message if custom_message else "Please complete the outstanding items to move your application forward."}

Click here to continue: {link}

Best regards,
DoorWay Team
"""

        try:
            send_mail(
                subject,
                message_body,
                settings.DEFAULT_FROM_EMAIL,
                [applicant.email],
                fail_silently=False,
            )
            
            # Log activity
            NudgeService._log_interaction(applicant, user, "EMAIL", custom_message or "Standard Nudge")
            return True, None
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _send_sms_nudge(applicant, application, user, custom_message=None):
        if not applicant.phone_number:
            return False, "Applicant has no phone number."
            
        sms_backend = SMSBackend()
        if not sms_backend.enabled:
            return False, "SMS service not configured."

        message = custom_message
        if not message:
            context_str = f" for {application.get_address_display()}" if application else ""
            message = f"DoorWay: Hi {applicant.first_name}, reminder from {user.first_name}{context_str}. Please check your email for details."

        success, result = sms_backend.send_sms(applicant.phone_number, message)
        
        if success:
            NudgeService._log_interaction(applicant, user, "SMS", message)
            return True, None
        else:
            return False, result

    @staticmethod
    def _log_interaction(applicant, user, method, message):
        """Log the interaction to CRM"""
        try:
            crm, _ = ApplicantCRM.objects.get_or_create(applicant=applicant)
            InteractionLog.objects.create(
                crm=crm,
                broker=user,
                note=f"[{method} SENT] {message}",
                created_at=timezone.now(),
                is_message=True
            )
        except Exception as e:
            print(f"Error logging interaction: {e}")

    @staticmethod
    def get_quick_actions(applicant):
        """
        Generate context-aware quick action templates.
        """
        actions = []
        
        # Missing Docs
        actions.append({
            'label': 'Request Docs',
            'message': f"Hi {applicant.first_name}, please upload your missing identification documents so we can proceed with your application.",
            'method': 'email'
        })

        # Schedule Viewing
        actions.append({
            'label': 'Schedule Viewing',
            'message': f"Hi {applicant.first_name}, are you available for a viewing this week? Please let me know what times work for you.",
            'method': 'sms' # SMS is better for scheduling
        })
        
        # Follow Up
        actions.append({
            'label': 'General Follow-up',
            'message': f"Hi {applicant.first_name}, just checking in on your search. Do you have any questions about the units we discussed?",
            'method': 'email'
        })

        return actions
