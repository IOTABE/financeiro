from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import Profile
from apps.debts.models import Debt

from .services import mark_plan_stale


@receiver(post_save, sender=Debt, dispatch_uid="plans.mark_stale_on_debt")
def mark_stale_on_debt(sender, instance: Debt, **kwargs) -> None:
    mark_plan_stale(instance.user)


@receiver(post_save, sender=Profile, dispatch_uid="plans.mark_stale_on_profile")
def mark_stale_on_profile(sender, instance: Profile, **kwargs) -> None:
    mark_plan_stale(instance.user)
