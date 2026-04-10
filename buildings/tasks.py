"""
Celery Tasks for Buildings App
================================

Asynchronous tasks for background processing of building-related operations.
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='buildings.refresh_neighbourhood_data',
    max_retries=3,
    default_retry_delay=30,   # 30s between retries (API rate limits)
    acks_late=True,
    ignore_result=True,
)
def refresh_neighbourhood_data(self, building_id):
    """
    Asynchronously refresh neighbourhood data (walk/transit/bike scores +
    nearby schools) for a single building via Google Places API (New).

    Triggered automatically on Building creation via post_save signal,
    and can also be dispatched manually from the Django admin action.

    Args:
        building_id: Primary key of the Building to refresh.
    """
    from buildings.models import Building
    from buildings.neighborhood_service import NeighborhoodService

    try:
        building = Building.objects.get(pk=building_id)
    except Building.DoesNotExist:
        logger.warning(
            f"[neighbourhood] Building {building_id} not found — skipping refresh."
        )
        return

    if not building.latitude or not building.longitude:
        logger.warning(
            f"[neighbourhood] Building {building_id} ({building.name}) has no "
            f"coordinates — skipping refresh."
        )
        return

    logger.info(
        f"[neighbourhood] Starting refresh for Building {building_id} ({building.name})."
    )

    try:
        success = NeighborhoodService.update_building_data(building_id)
        if success:
            logger.info(
                f"[neighbourhood] Refresh complete for Building {building_id} "
                f"({building.name})."
            )
        else:
            logger.warning(
                f"[neighbourhood] Refresh returned False for Building {building_id}."
            )
    except Exception as exc:
        logger.error(
            f"[neighbourhood] Refresh failed for Building {building_id}: {exc}"
        )
        # Retry on transient errors (network/API timeouts)
        raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
