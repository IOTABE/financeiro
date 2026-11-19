from __future__ import annotations

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("notificacoes/", views.notification_list, name="list"),
    path("notificacoes/<uuid:pk>/ler/", views.mark_read, name="mark_read"),
    path("notificacoes/ler-todas/", views.mark_all_read, name="mark_all_read"),
    path("notificacoes/preferencias/", views.preferences, name="preferences"),
]
