from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.core.services import financial_overview


def landing(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "core/landing.html")


@login_required
def dashboard(request):
    overview = financial_overview(request.user)
    return render(request, "core/dashboard.html", overview)


@login_required
def onboarding(request):
    overview = financial_overview(request.user)
    return render(request, "core/onboarding.html", overview)


def style_guide(request):
    return render(request, "core/style_guide.html")


def terms(request):
    return render(request, "core/legal.html", {"title": "Termos de uso", "kind": "terms"})


def privacy(request):
    return render(
        request, "core/legal.html", {"title": "Política de privacidade", "kind": "privacy"}
    )


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    checks: dict[str, str] = {}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        cache.set("readyz", "1", timeout=5)
        checks["cache"] = "ok" if cache.get("readyz") == "1" else "error"
    except Exception:
        checks["cache"] = "error"

    status = 200 if all(value == "ok" for value in checks.values()) else 503
    return JsonResponse(
        {"status": "ok" if status == 200 else "degraded", "checks": checks}, status=status
    )
