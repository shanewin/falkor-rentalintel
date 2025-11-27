from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import ApplicationActivity

class NudgeService:
    """
    Service for sending reminders (nudges) to applicants
    to complete their applications or upload documents.
    """

    @staticmethod
    def send_nudge(application, user, nudge_type='email', custom_message=None):
        """
        Send a nudge to the applicant.
        
        Args:
            application: The Application instance
            user: The Broker/User sending the nudge
            nudge_type: 'email' or 'sms' (future)
            custom_message: Optional custom text to include
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not application.applicant:
            return False

        if nudge_type == 'email':
            return NudgeService._send_email_nudge(application, user, custom_message)
        
        # Placeholder for SMS
        return False

    @staticmethod
    def _send_email_nudge(application, user, custom_message=None):
        if not application.applicant.email:
            return False

        subject = f"Action Required: Your Application for {application.get_address_display()}"
        
        # Determine what's missing
        missing_items = []
        if not application.is_satisfied():
            missing_items.append("Required Documents")
        
        # Construct message
        context = {
            'applicant': application.applicant,
            'application': application,
            'broker': user,
            'custom_message': custom_message,
            'missing_items': missing_items,
            'link': f"{settings.SITE_URL}/applications/complete/{application.unique_link}/" 
        }
        
        # Simple text template for now (could be HTML)
        message_body = f"""
Dear {application.applicant.first_name},

This is a reminder from your broker, {user.first_name} {user.last_name}, regarding your application for {application.get_address_display()}.

{custom_message if custom_message else "Please complete the outstanding items to move your application forward."}

"""
        if missing_items:
            message_body += "Missing Items:\n" + "\n".join([f"- {item}" for item in missing_items]) + "\n\n"

        message_body += f"Click here to continue: {context['link']}\n\n"
        message_body += "Best regards,\nDoorWay Team"

        try:
            send_mail(
                subject,
                message_body,
                settings.DEFAULT_FROM_EMAIL,
                [application.applicant.email],
                fail_silently=False,
            )
            
            # Log activity
            ApplicationActivity.objects.create(
                application=application,
                description=f"Nudge sent to {application.applicant.email} by {user.email}"
            )
            return True
        except Exception as e:
            print(f"Error sending nudge: {e}")
            return False
