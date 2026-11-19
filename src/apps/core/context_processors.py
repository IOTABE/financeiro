from __future__ import annotations

from django.conf import settings


def app_meta(request):
    return {
        "APP_NAME": settings.APP_NAME,
        "APP_VERSION": settings.APP_VERSION,
        "APP_CURRENCY": settings.APP_CURRENCY,
    }
