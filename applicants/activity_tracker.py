"""
Activity Tracking Service
========================

Centralized service for tracking applicant activities across the platform.
This service creates comprehensive logs of user behavior for CRM purposes.
"""

from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import ApplicantActivity, Applicant
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class ActivityTracker:
    """
    Service for tracking and logging applicant activities
    """
    
    @staticmethod
    def track_activity(
        applicant,
        activity_type,
        description,
        triggered_by=None,
        metadata=None,
        request=None
    ):
        """
        Track an activity for an applicant
        
        Args:
            applicant: Applicant instance or user with applicant profile
            activity_type: One of the ACTIVITY_TYPES choices
            description: Human-readable description
            triggered_by: User who triggered the activity (optional)
            metadata: Additional context data (dict)
            request: HTTP request object for IP/user agent tracking
        """
        try:
            # Handle both Applicant objects and User objects
            if hasattr(applicant, 'applicant_profile'):
                applicant = applicant.applicant_profile
            elif not isinstance(applicant, Applicant):
                logger.error(f"Invalid applicant object: {type(applicant)}")
                return None
            
            # Extract request context
            ip_address = None
            user_agent = None
            if request:
                ip_address = ActivityTracker.get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Create activity record
            activity = ApplicantActivity.objects.create(
                applicant=applicant,
                activity_type=activity_type,
                description=description,
                triggered_by=triggered_by,
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            logger.info(f"Tracked activity: {activity}")
            return activity
            
        except Exception as e:
            logger.error(f"Failed to track activity: {e}")
            return None
    
    @staticmethod
    def get_client_ip(request):
        """Extract client IP from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @staticmethod
    def track_profile_update(applicant, updated_fields, triggered_by=None, request=None):
        """Track profile updates with field details"""
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
        """Track when applicant views an apartment"""
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
        """Track when applicant views a building"""
        description = f"Viewed building: {building.name}"
        metadata = {
            'building_id': building.id,
            'building_name': building.name,
            'neighborhood': building.neighborhood.name if hasattr(building, 'neighborhood') else None
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
        """Track user login"""
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
        """Track application-related activities"""
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
        """Track CRM activities performed by brokers/admins"""
        return ActivityTracker.track_activity(
            applicant=applicant,
            activity_type=activity_type,
            description=description,
            triggered_by=broker,
            metadata=metadata
        )
    
    @staticmethod
    def get_recent_activities(applicant, limit=50):
        """Get recent activities for an applicant"""
        return ApplicantActivity.objects.filter(
            applicant=applicant
        ).select_related(
            'triggered_by'
        ).order_by('-created_at')[:limit]
    
    @staticmethod
    def get_activity_summary(applicant, days=30):
        """Get activity summary for the last N days"""
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


# Convenience functions for common tracking scenarios
def track_activity(applicant, activity_type, description, **kwargs):
    """Convenience function for basic activity tracking"""
    return ActivityTracker.track_activity(
        applicant=applicant,
        activity_type=activity_type,
        description=description,
        **kwargs
    )


def track_user_action(user, activity_type, description, **kwargs):
    """Track activity for a user (finds their applicant profile)"""
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