"""
Activity Tracking Service
=========================

Centralized service for tracking applicant activities across the platform.
Creates comprehensive audit trails for CRM analytics and compliance.
"""

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from .models import ApplicantActivity, Applicant
import logging
import hashlib
import json

User = get_user_model()
logger = logging.getLogger(__name__)

# Async processing support (optional)
try:
    from .tasks import track_activity_async
    from celery import current_app
    from celery.exceptions import TimeoutError
    CELERY_INSTALLED = True
except ImportError:
    CELERY_INSTALLED = False
    logger.warning("Celery not installed - activity tracking will be synchronous")
    # Define TimeoutError for non-Celery environments
    TimeoutError = TimeoutError

def is_celery_working():
    """Check if background task processing is available"""
    if not CELERY_INSTALLED:
        return False
    
    # Use Django cache for thread-safe worker health status
    cache_key = 'celery_health_status'
    cached_result = cache.get(cache_key)
    
    if cached_result is not None:
        return cached_result
    
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=1.0)
        stats = inspector.stats()
        
        # Cache result for 30 seconds
        is_healthy = bool(stats)
        cache.set(cache_key, is_healthy, timeout=30)
        
        if is_healthy:
            logger.debug("Celery workers detected and healthy")
        else:
            logger.debug("No Celery workers detected")
        return is_healthy
            
    except Exception as e:
        logger.debug(f"Celery health check failed: {e}")
        # Cache failure state briefly
        cache.set(cache_key, False, timeout=10)
        return False


class ActivityTracker:
    """
    Service for tracking and logging applicant activities
    """
    
    # Activity deduplication windows (in seconds)
    DEDUP_WINDOWS = {
        # Browsing activities - prevent spam
        'apartment_viewed': 60,
        'building_viewed': 60,
        'property_search': 30,
        'application_viewed': 60,
        
        # Critical events - never deduplicate
        'application_submitted': 0,
        'application_started': 0,
        'payment_completed': 0,
        'document_uploaded': 0,
        
        # Session events
        'login': 300,  # 5 minutes
        'logout': 300,
        
        # Profile changes
        'profile_updated': 10,
        
        # Default
        'default': 60
    }
    
    @staticmethod
    def _get_dedup_key(applicant_id, activity_type, metadata):
        """Generate unique key for duplicate detection"""
        # Extract object identifiers from metadata
        object_id = None
        if metadata:
            object_id = (
                metadata.get('apartment_id') or 
                metadata.get('building_id') or
                metadata.get('application_id') or
                metadata.get('document_id')
            )
        
        # Build cache key
        key_parts = [
            'activity',
            str(applicant_id),
            activity_type
        ]
        
        if object_id:
            key_parts.append(str(object_id))
        else:
            # Hash metadata for consistent keys using SHA256 for better security
            metadata_str = json.dumps(metadata or {}, sort_keys=True)
            metadata_hash = hashlib.sha256(metadata_str.encode()).hexdigest()[:8]
            key_parts.append(metadata_hash)
        
        return ':'.join(key_parts)
    
    @staticmethod
    def _should_track(applicant_id, activity_type, metadata):
        """Check if activity is duplicate within deduplication window"""
        # Get window for this activity type
        dedup_window = ActivityTracker.DEDUP_WINDOWS.get(
            activity_type,
            ActivityTracker.DEDUP_WINDOWS['default']
        )
        
        # Critical activities always tracked
        if dedup_window == 0:
            return True
        
        # Check for recent duplicate
        cache_key = ActivityTracker._get_dedup_key(applicant_id, activity_type, metadata)
        
        # Use add() for atomic check-and-set
        # Returns True only if key didn't exist
        if not cache.add(cache_key, True, dedup_window):
            logger.debug(f"Skipping duplicate activity: {cache_key}")
            return False
        
        return True
    
    @staticmethod
    def track_activity(
        applicant,
        activity_type,
        description,
        triggered_by=None,
        metadata=None,
        request=None,
        force_track=False,
        async_mode=None
    ):
        """
        Record an applicant activity for audit trail and analytics.
        
        Args:
            applicant: The applicant performing the activity
            activity_type: Category of activity (e.g., 'login', 'apartment_viewed')
            description: Human-readable description
            triggered_by: User who initiated the action (if different from applicant)
            metadata: Additional context data
            request: HTTP request for IP/browser tracking
            force_track: Bypass duplicate detection
            async_mode: Background processing preference
        
        Returns:
            Activity record or None if skipped
        """
        try:
            # Handle both Applicant and User objects
            if hasattr(applicant, 'applicant_profile'):
                applicant = applicant.applicant_profile
            elif not isinstance(applicant, Applicant):
                logger.error(f"Invalid applicant object: {type(applicant)}")
                return None
            
            # Skip duplicates unless forced
            if not force_track:
                if not ActivityTracker._should_track(applicant.id, activity_type, metadata):
                    return None
            
            # Extract request context for security logging
            ip_address = None
            user_agent = None
            if request:
                ip_address = ActivityTracker.get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Determine processing mode
            use_async = ActivityTracker._should_use_async(activity_type, async_mode)
            celery_working = is_celery_working() if use_async else False
            
            if use_async and celery_working:
                # Background processing for non-critical activities
                try:
                    from .tasks import track_activity_async
                    
                    task = track_activity_async.delay(
                        applicant_id=applicant.id,
                        activity_type=activity_type,
                        description=description,
                        triggered_by_id=triggered_by.id if triggered_by else None,
                        metadata=metadata,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        force_track=force_track
                    )
                    
                    # Wait briefly for task completion
                    timeout_seconds = getattr(settings, 'ACTIVITY_TRACKING_TIMEOUT', 5.0)
                    
                    try:
                        activity_id = task.get(timeout=timeout_seconds)
                        if activity_id:
                            activity = ApplicantActivity.objects.get(id=activity_id)
                            logger.debug(f"Async activity tracked: {activity}")
                            return activity
                    except TimeoutError:
                        logger.warning(f"Activity tracking timeout ({timeout_seconds}s) for {activity_type}, falling back to sync")
                    except ApplicantActivity.DoesNotExist:
                        logger.error(f"Activity {activity_id} not found after async creation")
                    
                except Exception as e:
                    logger.warning(f"Failed to queue async activity: {e}")
            
            # Synchronous tracking (default or fallback)
            activity = ApplicantActivity.objects.create(
                applicant=applicant,
                activity_type=activity_type,
                description=description,
                triggered_by=triggered_by,
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(f"Tracked activity (sync): {activity}")
            return activity
            
        except Exception as e:
            logger.error(f"Failed to track activity: {e}")
            return None
    
    @staticmethod
    def _should_use_async(activity_type, async_mode=None):
        """Determine if activity should be processed in background"""
        # Explicit preference
        if async_mode is not None:
            return async_mode
        
        # Critical activities must be synchronous for data integrity
        SYNC_REQUIRED = {
            'payment_completed',
            'payment_failed',
            'application_submitted',
            'document_uploaded',
            'legal_agreement_signed'
        }
        
        if activity_type in SYNC_REQUIRED:
            return False
        
        # Use system default
        use_async = getattr(settings, 'ACTIVITY_TRACKING_ASYNC', True)
        return use_async
    
    @staticmethod
    def get_client_ip(request):
        """Extract and validate client IP address from request"""
        import ipaddress
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP from the comma-separated list
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Validate IP address
        if ip:
            try:
                # This validates both IPv4 and IPv6 addresses
                ipaddress.ip_address(ip)
                return ip
            except ValueError:
                logger.warning(f"Invalid IP address detected: {ip}")
                return None
        return None
    
    @staticmethod
    def track_profile_update(applicant, updated_fields, triggered_by=None, request=None):
        """Record profile field changes"""
        description = f"Updated profile fields: {', '.join(updated_fields)}"
        metadata = {'updated_fields': updated_fields}
        
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='profile_updated',
            description=description,
            triggered_by=triggered_by,
            metadata=metadata,
            request=request
        )
    
    @staticmethod
    def track_apartment_view(applicant, apartment, request=None):
        """Record apartment viewing for interest analytics"""
        description = f"Viewed apartment: {apartment.building.name} Unit {apartment.unit_number}"
        metadata = {
            'apartment_id': apartment.id,
            'building_id': apartment.building.id,
            'building_name': apartment.building.name,
            'unit_number': apartment.unit_number,
            'rent_price': str(apartment.rent_price)
        }
        
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='apartment_viewed',
            description=description,
            triggered_by=applicant.user if hasattr(applicant, 'user') else None,
            metadata=metadata,
            request=request
        )
    
    @staticmethod
    def track_building_view(applicant, building, request=None):
        """Record building interest for marketing insights"""
        description = f"Viewed building: {building.name}"
        
        # Safely get neighborhood name
        neighborhood_name = None
        if hasattr(building, 'neighborhood'):
            neighborhood = building.neighborhood
            if neighborhood:
                # Handle both string and object neighborhoods
                neighborhood_name = neighborhood if isinstance(neighborhood, str) else getattr(neighborhood, 'name', None)
        
        metadata = {
            'building_id': building.id,
            'building_name': building.name,
            'neighborhood': neighborhood_name
        }
        
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='building_viewed',
            description=description,
            triggered_by=applicant.user if hasattr(applicant, 'user') else None,
            metadata=metadata,
            request=request
        )
    
    @staticmethod
    def track_login(applicant, request=None):
        """Record user authentication for security audit"""
        description = f"{applicant.first_name} {applicant.last_name} logged in"
        
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type='login',
            description=description,
            triggered_by=applicant.user if hasattr(applicant, 'user') else None,
            request=request
        )
    
    @staticmethod
    def track_application_activity(applicant, activity_type, application=None, request=None):
        """Record application lifecycle events"""
        activity_descriptions = {
            'application_started': 'Started new application',
            'application_updated': 'Updated application',
            'application_submitted': 'Submitted application',
            'application_viewed': 'Viewed application status'
        }
        
        description = activity_descriptions.get(activity_type, 'Application activity')
        metadata = {}
        
        if application:
            description += f" for {application.building.name if hasattr(application, 'building') else 'property'}"
            metadata = {
                'application_id': application.id,
                'status': getattr(application, 'status', 'unknown')
            }
        
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type=activity_type,
            description=description,
            triggered_by=applicant.user if hasattr(applicant, 'user') else None,
            metadata=metadata,
            request=request
        )
    
    @staticmethod
    def track_crm_activity(applicant, activity_type, description, broker, metadata=None):
        """Record broker/admin actions on applicant profiles"""
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type=activity_type,
            description=description,
            triggered_by=broker,
            metadata=metadata
        )
    
    @staticmethod
    def get_recent_activities(applicant, limit=50):
        """Retrieve applicant's recent activity history"""
        return ApplicantActivity.objects.filter(
            applicant=applicant
        ).select_related(
            'triggered_by'
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def get_activity_summary(applicant, days=30):
        """Generate activity analytics for reporting"""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        activities = ApplicantActivity.objects.filter(
            applicant=applicant,
            created_at__gte=cutoff_date
        )
        
        summary = {}
        for activity in activities:
            activity_type = activity.get_activity_type_display()
            summary[activity_type] = summary.get(activity_type, 0) + 1
        
        return {
            'total_activities': activities.count(),
            'activity_breakdown': summary,
            'most_recent': activities.order_by('-created_at').first(),
            'period_days': days
        }


# Convenience Functions
# ---------------------

def track_activity(applicant, activity_type, description, **kwargs):
    """Quick activity tracking helper"""
    return ActivityTracker.track_activity(
        applicant=applicant,
        activity_type=activity_type,
        description=description,
        **kwargs
    )


def track_user_action(user, activity_type, description, **kwargs):
    """Track activity for a user account"""
    try:
        if hasattr(user, 'applicant_profile'):
            return ActivityTracker.track_activity(
                applicant=user.applicant_profile,
                activity_type=activity_type,
                description=description,
                triggered_by=user,
                **kwargs
            )
    except Exception as e:
        logger.error(f"Failed to track user action: {e}")
        return None