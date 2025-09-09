"""
Activity Tracking Signals
========================

Automatic activity tracking using Django signals.
These signals will automatically log user activities across the platform.
"""

from django.db.models.signals import post_save, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Applicant, ApplicantActivity
from .activity_tracker import ActivityTracker
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    """Track when applicant users log in"""
    try:
        if hasattr(user, 'applicant_profile'):
            ActivityTracker.track_login(
                applicant=user.applicant_profile,
                request=request
            )
    except Exception as e:
        logger.error(f"Failed to track login for {user}: {e}")


@receiver(user_logged_out)
def track_user_logout(sender, request, user, **kwargs):
    """Track when applicant users log out"""
    try:
        if user and hasattr(user, 'applicant_profile'):
            ActivityTracker.track_activity(
                applicant=user.applicant_profile,
                activity_type='logout',
                description=f"{user.applicant_profile.first_name} {user.applicant_profile.last_name} logged out",
                triggered_by=user,
                request=request
            )
    except Exception as e:
        logger.error(f"Failed to track logout for {user}: {e}")


@receiver(post_save, sender=Applicant)
def track_applicant_profile_changes(sender, instance, created, **kwargs):
    """Track when applicant profiles are created or updated"""
    try:
        if created:
            # New profile created
            ActivityTracker.track_activity(
                applicant=instance,
                activity_type='profile_created',
                description=f"Profile created for {instance.first_name} {instance.last_name}",
                triggered_by=instance.user if instance.user else None,
                metadata={
                    'email': instance.email,
                    'phone': instance.phone_number,
                }
            )
        else:
            # Profile updated - we'd need to track specific field changes
            # This is a simplified version
            ActivityTracker.track_activity(
                applicant=instance,
                activity_type='profile_updated',
                description=f"Profile updated for {instance.first_name} {instance.last_name}",
                triggered_by=instance.user if instance.user else None
            )
    except Exception as e:
        logger.error(f"Failed to track applicant profile changes: {e}")


# Signal for tracking application activities
from applications.models import Application

@receiver(post_save, sender=Application)
def track_application_activities(sender, instance, created, **kwargs):
    """Track application creation and updates"""
    try:
        # Find the applicant from the application
        applicant = None
        if hasattr(instance, 'applicant'):
            applicant = instance.applicant
        elif hasattr(instance, 'user') and hasattr(instance.user, 'applicant_profile'):
            applicant = instance.user.applicant_profile
        
        if not applicant:
            return
        
        if created:
            # New application created
            ActivityTracker.track_application_activity(
                applicant=applicant,
                activity_type='application_started',
                application=instance
            )
        else:
            # Application updated
            ActivityTracker.track_application_activity(
                applicant=applicant,
                activity_type='application_updated',
                application=instance
            )
            
            # Track status changes specifically
            if hasattr(instance, '_previous_status') and instance.status != instance._previous_status:
                ActivityTracker.track_activity(
                    applicant=applicant,
                    activity_type='status_changed',
                    description=f"Application status changed from {instance._previous_status} to {instance.status}",
                    metadata={
                        'old_status': instance._previous_status,
                        'new_status': instance.status,
                        'application_id': instance.id
                    }
                )
                
    except Exception as e:
        logger.error(f"Failed to track application activity: {e}")


@receiver(pre_save, sender=Application)
def store_previous_application_status(sender, instance, **kwargs):
    """Store previous status before save to track changes"""
    try:
        if instance.pk:  # Only for existing instances
            previous = Application.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
    except Application.DoesNotExist:
        instance._previous_status = None


# Custom signal for tracking apartment views
from django.dispatch import Signal

# Custom signals for specific activities
apartment_viewed = Signal()
building_viewed = Signal()
document_uploaded = Signal()

@receiver(apartment_viewed)
def track_apartment_view_signal(sender, applicant, apartment, request=None, **kwargs):
    """Handle apartment view tracking"""
    ActivityTracker.track_apartment_view(
        applicant=applicant,
        apartment=apartment,
        request=request
    )

@receiver(building_viewed)
def track_building_view_signal(sender, applicant, building, request=None, **kwargs):
    """Handle building view tracking"""
    ActivityTracker.track_building_view(
        applicant=applicant,
        building=building,
        request=request
    )

@receiver(document_uploaded)
def track_document_upload_signal(sender, applicant, document_type, filename, request=None, **kwargs):
    """Handle document upload tracking"""
    ActivityTracker.track_activity(
        applicant=applicant,
        activity_type='document_uploaded',
        description=f"Uploaded {document_type}: {filename}",
        triggered_by=applicant.user if hasattr(applicant, 'user') else None,
        metadata={
            'document_type': document_type,
            'filename': filename
        },
        request=request
    )


# Helper function to manually trigger signals from views
def trigger_apartment_viewed(applicant, apartment, request=None):
    """Helper to trigger apartment viewed signal from views"""
    apartment_viewed.send(
        sender=apartment.__class__,
        applicant=applicant,
        apartment=apartment,
        request=request
    )

def trigger_building_viewed(applicant, building, request=None):
    """Helper to trigger building viewed signal from views"""
    building_viewed.send(
        sender=building.__class__,
        applicant=applicant,
        building=building,
        request=request
    )