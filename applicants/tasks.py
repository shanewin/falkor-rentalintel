"""
Celery Tasks for Applicants App
================================

Asynchronous tasks for background processing of applicant-related operations.
"""

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.db import models
import logging
import json

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='applicants.track_activity_async',
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,  # Ensure task completion even if worker crashes
    ignore_result=True  # Don't store result - we don't need it
)
def track_activity_async(
    self,
    applicant_id,
    activity_type,
    description,
    triggered_by_id=None,
    metadata=None,
    ip_address=None,
    user_agent=None,
    force_track=False
):
    """
    Asynchronously track an activity for an applicant.
    
    This task processes activity tracking in the background to avoid
    blocking HTTP requests. It includes retry logic for resilience.
    
    Args:
        applicant_id: ID of the Applicant instance
        activity_type: One of the ACTIVITY_TYPES choices
        description: Human-readable description
        triggered_by_id: ID of the User who triggered the activity (optional)
        metadata: Additional context data (dict)
        ip_address: Client IP address
        user_agent: Client user agent string
        force_track: Bypass deduplication (use sparingly)
    """
    try:
        from .models import ApplicantActivity, Applicant
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Load the applicant
        try:
            applicant = Applicant.objects.get(id=applicant_id)
        except Applicant.DoesNotExist:
            logger.error(f"Applicant {applicant_id} not found for activity tracking")
            return
        
        # Load the triggered_by user if provided
        triggered_by = None
        if triggered_by_id:
            try:
                triggered_by = User.objects.get(id=triggered_by_id)
            except User.DoesNotExist:
                logger.warning(f"User {triggered_by_id} not found for activity tracking")
        
        # Deduplication already handled by track_activity() - don't check again
        # Create activity record
        activity = ApplicantActivity.objects.create(
            applicant=applicant,
            activity_type=activity_type,
            description=description,
            triggered_by=triggered_by,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent or ''
        )
        
        logger.info(f"Async tracked activity: {activity}")
        return activity.id
        
    except Exception as e:
        logger.error(f"Failed to track activity asynchronously: {e}")
        # Retry the task if it's a transient error
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=5 * (self.request.retries + 1))
        else:
            # Max retries exceeded, log and give up
            logger.error(f"Max retries exceeded for activity tracking: {e}")
            return None


@shared_task(
    bind=True,
    name='applicants.bulk_track_activities',
    max_retries=2,
    default_retry_delay=10
)
def bulk_track_activities(self, activities_data):
    """
    Track multiple activities in a single background job.
    Useful for batch processing from imports or migrations.
    
    Args:
        activities_data: List of dicts with activity information
    """
    from .models import ApplicantActivity
    
    successful = 0
    failed = 0
    
    for activity_data in activities_data:
        try:
            track_activity_async.delay(**activity_data)
            successful += 1
        except Exception as e:
            logger.error(f"Failed to queue activity: {e}")
            failed += 1
    
    logger.info(f"Bulk activity tracking: {successful} queued, {failed} failed")
    return {'successful': successful, 'failed': failed}


@shared_task(
    name='applicants.cleanup_old_activities',
    ignore_result=True
)
def cleanup_old_activities(days_to_keep=None, activity_types=None, dry_run=True):
    """
    MANUAL cleanup task for old activity records.
    
    This task should ONLY be run manually after careful consideration
    of data retention requirements, compliance needs, and business analytics.
    
    Args:
        days_to_keep: Number of days to keep (required to prevent accidental deletion)
        activity_types: List of specific activity types to clean up (optional)
        dry_run: If True, only report what would be deleted without deleting
    
    Returns:
        Dict with deletion counts and details
    """
    from datetime import timedelta
    from .models import ApplicantActivity
    
    if days_to_keep is None:
        logger.error("cleanup_old_activities called without days_to_keep - aborting")
        return {'error': 'days_to_keep is required'}
    
    if days_to_keep < 30:
        logger.error(f"Refusing to delete activities newer than 30 days (got {days_to_keep})")
        return {'error': 'Minimum retention period is 30 days'}
    
    # Business-critical activities that should NEVER be auto-deleted
    PROTECTED_TYPES = {
        'payment_completed',
        'payment_failed', 
        'application_submitted',
        'legal_agreement_signed',
        'document_uploaded',
        'status_changed'
    }
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Build the queryset
    queryset = ApplicantActivity.objects.filter(created_at__lt=cutoff_date)
    
    # Never delete protected types
    queryset = queryset.exclude(activity_type__in=PROTECTED_TYPES)
    
    # If specific activity types provided, only delete those
    if activity_types:
        queryset = queryset.filter(activity_type__in=activity_types)
    
    # Get count before deletion
    count = queryset.count()
    
    if dry_run:
        # Report what would be deleted without actually deleting
        sample = list(queryset.values('activity_type').annotate(
            count=models.Count('id')
        ).order_by('-count')[:10])
        
        logger.info(f"DRY RUN: Would delete {count} activities older than {days_to_keep} days")
        return {
            'dry_run': True,
            'would_delete': count,
            'cutoff_date': cutoff_date.isoformat(),
            'breakdown': sample
        }
    else:
        # Actually delete the records
        queryset.delete()
        logger.info(f"Deleted {count} activities older than {days_to_keep} days")
        return {
            'dry_run': False,
            'deleted': count,
            'cutoff_date': cutoff_date.isoformat()
        }