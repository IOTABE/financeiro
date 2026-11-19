from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.audit import log_event

from .services import export_payload, monthly_report, transactions_csv


@login_required
def monthly(request):
    month_param = request.GET.get("month", "")
    try:
        month = date.fromisoformat(f"{month_param}-01") if month_param else None
    except ValueError:
        month = None
    report = monthly_report(request.user, month)
    return render(request, "reports/monthly.html", report)


@login_required
def export_json(request):
    payload = export_payload(request.user)
    log_event(
        event="data.exported",
        user=request.user,
        request=request,
        metadata={"format": "json"},
    )
    response = JsonResponse(
        payload,
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )
    filename = f"clareza-dados-{timezone.localdate():%Y-%m-%d}.json"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def export_csv(request):
    content = transactions_csv(request.user)
    log_event(
        event="data.exported",
        user=request.user,
        request=request,
        metadata={"format": "csv"},
    )
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    filename = f"clareza-transacoes-{timezone.localdate():%Y-%m-%d}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
