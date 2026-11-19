from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import ensure_finance_setup

User = get_user_model()


@receiver(post_save, sender=User)
def seed_finance_for_new_user(sender, instance, created: bool, **kwargs) -> None:
    if created:
        ensure_finance_setup(instance)
