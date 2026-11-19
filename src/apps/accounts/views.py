from __future__ import annotations

import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, PasswordResetView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from apps.core.audit import client_ip, log_event
from apps.core.ratelimit import check_rate_limit

from .forms import DeleteAccountForm, EmailAuthenticationForm, ProfileForm, RegisterForm
from .models import Consent, Profile
from .services import financial_health


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("core:dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not check_rate_limit(
            request,
            key="register",
            limit=settings.REGISTER_RATE_LIMIT,
            window_seconds=3600,
        ):
            messages.error(request, "Muitas contas criadas. Tente novamente mais tarde.")
            return self.render_to_response(self.get_context_data(), status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        ip_hash = _hash(_client_ip(self.request))
        ua_hash = _hash(self.request.META.get("HTTP_USER_AGENT", ""))
        Consent.objects.bulk_create(
            [
                Consent(
                    user=user,
                    kind=Consent.Kind.TERMS,
                    version="1.0",
                    accepted=True,
                    ip_hash=ip_hash,
                    user_agent_hash=ua_hash,
                ),
                Consent(
                    user=user,
                    kind=Consent.Kind.PRIVACY,
                    version="1.0",
                    accepted=True,
                    ip_hash=ip_hash,
                    user_agent_hash=ua_hash,
                ),
            ]
        )
        log_event(event="account.created", user=user, request=self.request)
        login(self.request, user)
        messages.success(
            self.request,
            "Conta criada. Agora vamos entender sua situação financeira.",
        )
        return response


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if not check_rate_limit(
            request,
            key="login",
            limit=settings.LOGIN_RATE_LIMIT,
            window_seconds=900,
            identifier=f"{client_ip(request)}:{request.POST.get('username', '').lower()}",
        ):
            messages.error(request, "Muitas tentativas. Tente novamente em 15 minutos.")
            return self.render_to_response(self.get_context_data(), status=429)
        return super().post(request, *args, **kwargs)


class RateLimitedPasswordResetView(PasswordResetView):
    def post(self, request, *args, **kwargs):
        if not check_rate_limit(
            request,
            key="password-reset",
            limit=settings.PASSWORD_RESET_RATE_LIMIT,
            window_seconds=3600,
        ):
            messages.error(request, "Muitas solicitações. Tente novamente mais tarde.")
            return self.render_to_response(self.get_context_data(), status=429)
        return super().post(request, *args, **kwargs)


class ProfileView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("core:dashboard")

    def get_object(self, queryset=None):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["health"] = financial_health(self.object)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("complete_onboarding") == "1":
            self.object.onboarding_completed_at = timezone.now()
            self.object.save(update_fields=["onboarding_completed_at", "updated_at"])
        messages.success(self.request, "Perfil financeiro atualizado.")
        return response


@login_required
def my_data(request):
    consents = request.user.consents.order_by("-accepted_at")
    return render(
        request,
        "accounts/my_data.html",
        {"delete_form": DeleteAccountForm(), "consents": consents},
    )


@login_required
@require_POST
def delete_account(request):
    form = DeleteAccountForm(request.POST)
    if not form.is_valid():
        consents = request.user.consents.order_by("-accepted_at")
        return render(
            request,
            "accounts/my_data.html",
            {"delete_form": form, "consents": consents},
            status=400,
        )
    if not request.user.check_password(form.cleaned_data["password"]):
        form.add_error("password", "Senha incorreta.")
        consents = request.user.consents.order_by("-accepted_at")
        return render(
            request,
            "accounts/my_data.html",
            {"delete_form": form, "consents": consents},
            status=400,
        )
    user = request.user
    log_event(
        event="account.deleted",
        user=user,
        request=request,
        entity_type="user",
        entity_id=str(user.pk),
    )
    logout(request)
    user.delete()
    return redirect("/?deleted=1")
