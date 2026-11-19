from __future__ import annotations

from django.apps import AppConfig


class PlansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.plans"
    verbose_name = "Planos"

    def ready(self) -> None:
        from . import signals  # noqa: F401
