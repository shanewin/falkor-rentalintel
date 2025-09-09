from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.models import Site
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

def send_application_link_email(application, request=None):
    """
    Send application link to applicant via email
    """
    if not application.applicant or not application.applicant.email:
        logger.warning(f"Cannot send email for application {application.id}: No applicant or email")
        return False
    
    try:
        # Get the current site
        current_site = Site.objects.get_current() if request is None else request.get_host()
        protocol = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
        
        # Build the application completion URL
        completion_url = reverse('applicant_complete', kwargs={'uuid': application.unique_link})
        full_url = f"{protocol}://{current_site}{completion_url}?token={application.unique_link}"
        
        # Prepare email context
        context = {
            'application': application,
            'applicant': application.applicant,
            'completion_url': full_url,
            'broker': application.broker,
            'property_display': get_property_display(application),
            'site_name': getattr(settings, 'SITE_NAME', 'DoorWay'),
        }
        
        # Render email templates
        subject = render_to_string('applications/emails/application_link_subject.txt', context).strip()
        html_message = render_to_string('applications/emails/application_link_email.html', context)
        text_message = render_to_string('applications/emails/application_link_email.txt', context)
        
        # Send email
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@doorway.com'),
            recipient_list=[application.applicant.email],
            fail_silently=False,
        )
        
        logger.info(f"Application link email sent successfully to {application.applicant.email} for application {application.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send application link email for application {application.id}: {str(e)}")
        return False

def send_application_reminder_email(application, request=None):
    """
    Send reminder email to applicant about incomplete application
    """
    if not application.applicant or not application.applicant.email:
        return False
    
    if application.submitted_by_applicant:
        logger.warning(f"Application {application.id} already submitted, skipping reminder")
        return False
    
    try:
        # Similar to send_application_link_email but with reminder template
        current_site = Site.objects.get_current() if request is None else request.get_host()
        protocol = 'https' if getattr(settings, 'USE_HTTPS', False) else 'http'
        
        completion_url = reverse('applicant_complete', kwargs={'uuid': application.unique_link})
        full_url = f"{protocol}://{current_site}{completion_url}?token={application.unique_link}"
        
        context = {
            'application': application,
            'applicant': application.applicant,
            'completion_url': full_url,
            'broker': application.broker,
            'property_display': get_property_display(application),
            'site_name': getattr(settings, 'SITE_NAME', 'DoorWay'),
        }
        
        subject = render_to_string('applications/emails/application_reminder_subject.txt', context).strip()
        html_message = render_to_string('applications/emails/application_reminder_email.html', context)
        text_message = render_to_string('applications/emails/application_reminder_email.txt', context)
        
        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@doorway.com'),
            recipient_list=[application.applicant.email],
            fail_silently=False,
        )
        
        logger.info(f"Application reminder email sent to {application.applicant.email} for application {application.id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send reminder email for application {application.id}: {str(e)}")
        return False

def get_property_display(application):
    """Helper function to get property display text"""
    if application.apartment:
        return f"{application.apartment.building.name} - Unit {application.apartment.unit_number}"
    elif application.manual_building_address:
        building_name = application.manual_building_name or "Building"
        unit_number = application.manual_unit_number or "Unit"
        return f"{building_name} - {unit_number}"
    else:
        return "Property details to be provided"