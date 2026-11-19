from __future__ import annotations

import logging

from celery import shared_task

from .services import send_due_reminders as run_due_reminders

logger = logging.getLogger("apps.notifications")


@shared_task
def send_due_reminders() -> int:
    count = run_due_reminders()
    logger.info("notifications.due_reminders", extra={"count": count})
    return count
