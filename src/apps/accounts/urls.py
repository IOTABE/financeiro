from __future__ import annotations

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    EmailLoginView,
    ProfileView,
    RateLimitedPasswordResetView,
    RegisterView,
    delete_account,
    my_data,
)

app_name = "accounts"

urlpatterns = [
    path("cadastro/", RegisterView.as_view(), name="register"),
    path("entrar/", EmailLoginView.as_view(), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("perfil/", ProfileView.as_view(), name="profile"),
    path("meus-dados/", my_data, name="my_data"),
    path("excluir/", delete_account, name="delete_account"),
    path(
        "senha/redefinir/",
        RateLimitedPasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "senha/redefinir/enviado/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "senha/redefinir/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "senha/redefinir/concluido/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
