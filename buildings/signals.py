"""
Signal handlers for the Buildings app.

Wires up automatic neighbourhood data refresh whenever a new
Building is saved with coordinates.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='buildings.Building')
def trigger_neighbourhood_refresh_on_create(sender, instance, created, **kwargs):
    """
    Fire a Celery task to populate neighbourhood data whenever a new Building
    is created that has lat/lng coordinates.

    Also re-fires if an existing building's coordinates are set for the
    first time (i.e., was previously missing coords and now has them).
    """
    # Only act when coordinates are present
    if not instance.latitude or not instance.longitude:
        return

    # Fire on creation, OR when scores are still missing (e.g. coords were
    # added to an existing building that had none before)
    should_refresh = created or instance.walk_score is None

    if not should_refresh:
        return

    # Import here to avoid circular imports at module load time
    from buildings.tasks import refresh_neighbourhood_data

    logger.info(
        f"[neighbourhood] Queuing refresh for Building {instance.pk} "
        f"({instance.name}) — created={created}."
    )

    # Queue with a short delay so the DB transaction has time to commit
    # before the Celery worker tries to fetch the building.
    refresh_neighbourhood_data.apply_async(
        args=[instance.pk],
        countdown=5,   # 5-second delay
    )
