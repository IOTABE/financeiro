from __future__ import annotations

from django.urls import path

from . import views

app_name = "debts"

urlpatterns = [
    path("dividas/", views.debt_list, name="list"),
    path("dividas/nova/", views.debt_create, name="create"),
    path("dividas/<uuid:pk>/", views.debt_detail, name="detail"),
    path("dividas/<uuid:pk>/editar/", views.debt_update, name="update"),
    path("dividas/<uuid:pk>/pagamento/", views.debt_pay, name="pay"),
    path("dividas/<uuid:pk>/excluir/", views.debt_delete, name="delete"),
]
