from __future__ import annotations

from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("transacoes/", views.transaction_list, name="transactions"),
    path("transacoes/nova/", views.transaction_create, name="transaction_create"),
    path("transacoes/parcelada/", views.installment_create, name="installment_create"),
    path("transacoes/<uuid:pk>/editar/", views.transaction_update, name="transaction_update"),
    path("transacoes/<uuid:pk>/excluir/", views.transaction_delete, name="transaction_delete"),
    path("transacoes/<uuid:pk>/status/", views.transaction_toggle, name="transaction_toggle"),
    path("categorias/", views.category_list, name="categories"),
    path("categorias/nova/", views.category_create, name="category_create"),
    path("categorias/<uuid:pk>/editar/", views.category_update, name="category_update"),
    path("categorias/<uuid:pk>/arquivar/", views.category_archive, name="category_archive"),
    path("contas/", views.account_list, name="accounts"),
    path("contas/nova/", views.account_create, name="account_create"),
    path("contas/<uuid:pk>/editar/", views.account_update, name="account_update"),
    path("contas/<uuid:pk>/arquivar/", views.account_archive, name="account_archive"),
    path("recorrencias/", views.recurrence_list, name="recurrences"),
    path("recorrencias/nova/", views.recurrence_create, name="recurrence_create"),
    path("recorrencias/<uuid:pk>/editar/", views.recurrence_update, name="recurrence_update"),
    path("recorrencias/<uuid:pk>/status/", views.recurrence_toggle, name="recurrence_toggle"),
]
