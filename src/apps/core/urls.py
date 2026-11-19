from __future__ import annotations

from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("app/", views.dashboard, name="dashboard"),
    path("comecar/", views.onboarding, name="onboarding"),
    path("estilo/", views.style_guide, name="style_guide"),
    path("termos/", views.terms, name="terms"),
    path("privacidade/", views.privacy, name="privacy"),
]
