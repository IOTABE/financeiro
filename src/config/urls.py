"""Root URL configuration."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path

from apps.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.finance.urls")),
    path("", include("apps.debts.urls")),
    path("", include("apps.plans.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.core.urls")),
    path("conta/", include("apps.accounts.urls")),
    path("healthz", core_views.healthz, name="healthz"),
    path("readyz", core_views.readyz, name="readyz"),
]

admin.site.site_header = "Clareza Financeira — Administração"
admin.site.site_title = "Clareza Financeira"
admin.site.index_title = "Operação"
