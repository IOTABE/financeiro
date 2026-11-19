from __future__ import annotations

from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("plano/", views.current, name="current"),
    path("plano/gerar/", views.generate, name="generate"),
    path("plano/comparar/", views.compare, name="compare"),
    path("plano/simulador/", views.simulate, name="simulator"),
    path("plano/simulacao/<uuid:pk>/", views.simulation_detail, name="simulation_detail"),
    path(
        "plano/simulacao/<uuid:pk>/aplicar/",
        views.apply_simulation_view,
        name="apply_simulation",
    ),
    path("plano/<uuid:pk>/", views.detail, name="detail"),
    path("plano/<uuid:pk>/recalcular/", views.recalculate, name="recalculate"),
    path("plano/calendario/<int:pk>/pagar/", views.schedule_pay, name="schedule_pay"),
]
