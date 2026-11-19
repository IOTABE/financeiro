from __future__ import annotations

import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .services import materialize_user_recurrences

logger = logging.getLogger("apps.finance")


@shared_task
def materialize_recurrences() -> int:
    total = 0
    for user in get_user_model().objects.filter(is_active=True).iterator():
        total += materialize_user_recurrences(user)
    logger.info("recurrences.materialized", extra={"count": total})
    return total
