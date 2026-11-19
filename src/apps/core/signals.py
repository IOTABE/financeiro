from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import log_event


@receiver(user_logged_in, dispatch_uid="core.audit.login")
def audit_login(sender, request, user, **kwargs) -> None:
    log_event(event="auth.login", user=user, request=request)


@receiver(user_logged_out, dispatch_uid="core.audit.logout")
def audit_logout(sender, request, user, **kwargs) -> None:
    if user:
        log_event(event="auth.logout", user=user, request=request)


@receiver(user_login_failed, dispatch_uid="core.audit.login_failed")
def audit_login_failed(sender, credentials, request=None, **kwargs) -> None:
    log_event(
        event="auth.login_failed",
        request=request,
        metadata={"identifier": "redacted"},
    )
