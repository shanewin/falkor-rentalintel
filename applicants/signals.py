"""
Activity Tracking Signals
=========================

Automated activity tracking for applicant behavior analytics and CRM.
Tracks user sessions, profile changes, application lifecycle, and document management.
"""

from django.db.models.signals import post_save, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
import logging
import hashlib
import json

from .models import Applicant, ApplicantActivity
from .activity_tracker import ActivityTracker

User = get_user_model()
logger = logging.getLogger(__name__)


# Utility Functions
# -----------------

def get_status_cache_key(model_name: str, instance_id: int) -> str:
    """Generate unique cache key for instance status"""
    return f"signal_status_{model_name}_{instance_id}"


def get_dedup_cache_key(applicant_id: int, activity_type: str, context: str = "") -> str:
    """Generate deduplication cache key with 1-minute resolution"""
    timestamp = timezone.now().strftime("%Y%m%d%H%M")
    unique_str = f"{applicant_id}_{activity_type}_{context}_{timestamp}"
    return f"dedup_{hashlib.sha256(unique_str.encode()).hexdigest()[:16]}"


def should_skip_duplicate(applicant_id: int, activity_type: str, context: str = "") -> bool:
    """Prevent duplicate activity logging within 60-second window"""
    cache_key = get_dedup_cache_key(applicant_id, activity_type, context)
    # Use add() for atomic check-and-set - returns True only if key didn't exist
    # So we return the opposite (True = skip, False = track)
    return not cache.add(cache_key, True, timeout=60)


def get_current_user():
    """Get current user from request context via middleware"""
    try:
        from .middleware import get_current_user as get_user_from_middleware
        return get_user_from_middleware()
    except ImportError:
        return None


# User Authentication Tracking
# ----------------------------

@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    """Track applicant login events for session analytics"""
    try:
        if not hasattr(user, 'applicant_profile'):
            return
            
        applicant = user.applicant_profile
        
        if should_skip_duplicate(applicant.id, 'login', str(user.id)):
            logger.debug(f"Skipping duplicate login tracking for {user.id}")
            return
        
        ActivityTracker.track_login(
            applicant=applicant,
            request=request
        )
        
    except Exception as e:
        logger.error(
            f"Failed to track login for user_id={user.id}: {e}",
            exc_info=True,
            extra={
                'user_id': user.id,
                'event': 'user_login_signal'
            }
        )


@receiver(user_logged_out)
def track_user_logout(sender, request, user, **kwargs):
    """Track applicant logout events"""
    try:
        if not user or not hasattr(user, 'applicant_profile'):
            return
            
        applicant = user.applicant_profile
        
        if should_skip_duplicate(applicant.id, 'logout', str(user.id)):
            logger.debug(f"Skipping duplicate logout tracking for {user.id}")
            return
        
        ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='logout',
            description="User logged out",
            triggered_by=user,
            request=request
        )
        
    except Exception as e:
        logger.error(
            f"Failed to track logout for user_id={getattr(user, 'id', 'unknown')}: {e}",
            exc_info=True,
            extra={
                'user_id': getattr(user, 'id', None),
                'event': 'user_logout_signal'
            }
        )


# Applicant Profile Management
# ----------------------------

@receiver(post_save, sender=Applicant)
def track_applicant_profile_changes(sender, instance, created, **kwargs):
    """Track profile creation and updates for audit trail"""
    
    def do_track():
        try:
            activity_type = 'profile_created' if created else 'profile_updated'
            if should_skip_duplicate(instance.id, activity_type, str(instance.id)):
                logger.debug(f"Skipping duplicate {activity_type} for applicant {instance.id}")
                return
            
            if created:
                ActivityTracker.track_activity(
                    applicant=instance,
                    activity_type='profile_created',
                    description="Profile created",
                    triggered_by=instance.user if instance.user else get_current_user(),
                    metadata={
                        'applicant_id': instance.id,
                    }
                )
            else:
                ActivityTracker.track_activity(
                    applicant=instance,
                    activity_type='profile_updated',
                    description="Profile updated",
                    triggered_by=instance.user if instance.user else get_current_user(),
                    metadata={
                        'applicant_id': instance.id,
                    }
                )
                
        except Exception as e:
            logger.error(
                f"Failed to track applicant profile change: {e}",
                exc_info=True,
                extra={
                    'applicant_id': instance.id,
                    'event': 'profile_change_signal',
                    'created': created
                }
            )
    
    # Execute after database transaction commits
    transaction.on_commit(do_track)


# Application Lifecycle Tracking
# ------------------------------

@receiver(pre_save, sender='applications.Application')
def store_previous_application_status(sender, instance, **kwargs):
    """Cache application status before save to detect changes"""
    try:
        if instance.pk:
            try:
                from applications.models import Application
                current = Application.objects.only('status').get(pk=instance.pk)
                
                # Store in cache for comparison in post_save
                cache_key = get_status_cache_key('Application', instance.pk)
                cache.set(cache_key, current.status, timeout=60)
                logger.debug(f"Cached previous status '{current.status}' for application {instance.pk}")
                
            except Application.DoesNotExist:
                pass
                
    except Exception as e:
        logger.warning(
            f"Could not cache previous status for application {instance.pk}: {e}",
            extra={'application_id': instance.pk}
        )


@receiver(post_save, sender='applications.Application')
def track_application_activities(sender, instance, created, **kwargs):
    """Track application creation, updates, and status changes"""
    
    def do_track():
        try:
            from applications.models import Application
            
            # Find associated applicant
            applicant = None
            if hasattr(instance, 'applicant'):
                applicant = instance.applicant
            elif hasattr(instance, 'user') and hasattr(instance.user, 'applicant_profile'):
                applicant = instance.user.applicant_profile
            
            if not applicant:
                logger.debug(f"No applicant found for application {instance.id}")
                return
            
            # Check for status changes
            cache_key = get_status_cache_key('Application', instance.pk)
            previous_status = cache.get(cache_key)
            
            if previous_status is not None:
                cache.delete(cache_key)
            
            if created:
                if should_skip_duplicate(applicant.id, 'application_started', str(instance.id)):
                    logger.debug(f"Skipping duplicate application_started for {instance.id}")
                    return
                    
                ActivityTracker.track_application_activity(
                    applicant=applicant,
                    activity_type='application_started',
                    application=instance
                )
                
            else:
                # Track status changes specifically
                if previous_status and instance.status != previous_status:
                    dedup_context = f"{instance.id}_{previous_status}_{instance.status}"
                    if should_skip_duplicate(applicant.id, 'status_changed', dedup_context):
                        logger.debug(f"Skipping duplicate status change for {instance.id}")
                        return
                    
                    ActivityTracker.track_activity(
                        applicant=applicant,
                        activity_type='status_changed',
                        description=f"Application status: {previous_status} → {instance.status}",
                        triggered_by=get_current_user(),
                        metadata={
                            'application_id': instance.id,
                            'old_status': previous_status,
                            'new_status': instance.status,
                        }
                    )
                else:
                    # Regular update
                    if should_skip_duplicate(applicant.id, 'application_updated', str(instance.id)):
                        logger.debug(f"Skipping duplicate application_updated for {instance.id}")
                        return
                        
                    ActivityTracker.track_application_activity(
                        applicant=applicant,
                        activity_type='application_updated',
                        application=instance
                    )
                    
        except Exception as e:
            logger.error(
                f"Failed to track application activity: {e}",
                exc_info=True,
                extra={
                    'application_id': instance.id,
                    'created': created,
                    'event': 'application_activity_signal'
                }
            )
    
    # Execute after database transaction commits
    transaction.on_commit(do_track)


# Custom Activity Signals
# -----------------------

from django.dispatch import Signal

# Define custom signals for specific user actions
apartment_viewed = Signal()
building_viewed = Signal()
document_uploaded = Signal()


@receiver(apartment_viewed)
def track_apartment_view_signal(sender, applicant, apartment, request=None, **kwargs):
    """Track apartment viewing behavior for matching analytics"""
    try:
        if should_skip_duplicate(applicant.id, 'apartment_view', str(apartment.id)):
            logger.debug(f"Skipping duplicate apartment view for {apartment.id}")
            return
            
        ActivityTracker.track_apartment_view(
            applicant=applicant,
            apartment=apartment,
            request=request
        )
        
    except Exception as e:
        logger.error(
            f"Failed to track apartment view: {e}",
            exc_info=True,
            extra={
                'applicant_id': applicant.id,
                'apartment_id': apartment.id,
                'event': 'apartment_view_signal'
            }
        )


@receiver(building_viewed)
def track_building_view_signal(sender, applicant, building, request=None, **kwargs):
    """Track building viewing patterns"""
    try:
        if should_skip_duplicate(applicant.id, 'building_view', str(building.id)):
            logger.debug(f"Skipping duplicate building view for {building.id}")
            return
            
        ActivityTracker.track_building_view(
            applicant=applicant,
            building=building,
            request=request
        )
        
    except Exception as e:
        logger.error(
            f"Failed to track building view: {e}",
            exc_info=True,
            extra={
                'applicant_id': applicant.id,
                'building_id': building.id,
                'event': 'building_view_signal'
            }
        )


@receiver(document_uploaded)
def track_document_upload_signal(sender, applicant, document_type, filename, request=None, **kwargs):
    """Track document uploads for compliance and completion tracking"""
    try:
        dedup_context = f"{document_type}_{filename}"
        if should_skip_duplicate(applicant.id, 'document_uploaded', dedup_context):
            logger.debug(f"Skipping duplicate document upload for {filename}")
            return
        
        # Extract file extension only (no full paths for privacy)
        safe_filename = filename.split('/')[-1].split('\\')[-1]
        
        ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='document_uploaded',
            description=f"Uploaded {document_type}",
            triggered_by=applicant.user if hasattr(applicant, 'user') else get_current_user(),
            metadata={
                'document_type': document_type,
                'file_extension': safe_filename.split('.')[-1] if '.' in safe_filename else 'unknown',
            },
            request=request
        )
        
    except Exception as e:
        logger.error(
            f"Failed to track document upload: {e}",
            exc_info=True,
            extra={
                'applicant_id': applicant.id,
                'document_type': document_type,
                'event': 'document_upload_signal'
            }
        )


# Signal Trigger Helpers
# ----------------------

def trigger_apartment_viewed(applicant, apartment, request=None):
    """Manually trigger apartment view tracking from views"""
    try:
        apartment_viewed.send(
            sender=apartment.__class__,
            applicant=applicant,
            apartment=apartment,
            request=request
        )
    except Exception as e:
        logger.error(f"Failed to trigger apartment_viewed signal: {e}", exc_info=True)


def trigger_building_viewed(applicant, building, request=None):
    """Manually trigger building view tracking from views"""
    try:
        building_viewed.send(
            sender=building.__class__,
            applicant=applicant,
            building=building,
            request=request
        )
    except Exception as e:
        logger.error(f"Failed to trigger building_viewed signal: {e}", exc_info=True)


def trigger_document_uploaded(applicant, document_type, filename, request=None):
    """Manually trigger document upload tracking from views"""
    try:
        document_uploaded.send(
            sender=applicant.__class__,
            applicant=applicant,
            document_type=document_type,
            filename=filename,
            request=request
        )
    except Exception as e:
        logger.error(f"Failed to trigger document_uploaded signal: {e}", exc_info=True)