from __future__ import annotations

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("relatorios/", views.monthly, name="monthly"),
    path("relatorios/exportar/json/", views.export_json, name="export_json"),
    path("relatorios/exportar/csv/", views.export_csv, name="export_csv"),
]
