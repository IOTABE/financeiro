from __future__ import annotations

import csv
import io
import json
from datetime import date

from django.core import serializers
from django.utils import timezone

from apps.accounts.models import Consent, Profile
from apps.core.dates import month_start
from apps.debts.models import Debt, DebtPayment
from apps.debts.services import debt_summary
from apps.finance.models import Account, Category, InstallmentGroup, Recurrence, Transaction
from apps.finance.services import monthly_summary
from apps.notifications.models import Notification, NotificationPreference
from apps.plans.models import Plan, PlanItem, PlanPayment, PlanSchedule, Simulation
from apps.plans.services import adherence_summary, current_plan, latest_plan

DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _serialize(queryset) -> list[dict]:
    return json.loads(serializers.serialize("json", queryset, use_natural_foreign_keys=True))


def export_payload(user) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    data = {
        "exported_at": timezone.now().isoformat(),
        "app": "Clareza Financeira",
        "user": {
            "email": user.email,
            "full_name": user.full_name,
            "date_joined": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "profile": _serialize([profile]),
        "categories": _serialize(Category.objects.filter(user=user)),
        "accounts": _serialize(Account.objects.filter(user=user)),
        "recurrences": _serialize(Recurrence.objects.filter(user=user)),
        "installment_groups": _serialize(InstallmentGroup.objects.filter(user=user)),
        "transactions": _serialize(Transaction.objects.filter(user=user)),
        "debts": _serialize(Debt.objects.filter(user=user)),
        "debt_payments": _serialize(DebtPayment.objects.filter(user=user)),
        "plans": _serialize(Plan.objects.filter(user=user)),
        "plan_items": _serialize(PlanItem.objects.filter(plan__user=user)),
        "plan_schedules": _serialize(PlanSchedule.objects.filter(plan__user=user)),
        "plan_payments": _serialize(PlanPayment.objects.filter(user=user)),
        "simulations": _serialize(Simulation.objects.filter(user=user)),
        "consents": _serialize(Consent.objects.filter(user=user)),
    }
    data["notification_preferences"] = _serialize(NotificationPreference.objects.filter(user=user))
    data["notifications"] = _serialize(Notification.objects.filter(user=user))
    return data


def _safe_cell(value) -> str:
    text = "" if value is None else str(value)
    if text.startswith(DANGEROUS_PREFIXES):
        return "'" + text
    return text


def transactions_csv(user) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "data",
            "competencia",
            "tipo",
            "descricao",
            "categoria",
            "conta",
            "valor",
            "status",
            "pago_em",
            "parcelamento",
            "recorrencia",
        ]
    )
    queryset = (
        Transaction.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("category", "account", "recurrence", "installment_group")
        .order_by("transaction_date", "id")
    )
    for item in queryset.iterator():
        installment = ""
        if item.installment_group:
            installment = f"{item.installment_number}/{item.installment_group.installments}"
        writer.writerow(
            [
                _safe_cell(item.transaction_date.isoformat()),
                _safe_cell(item.competence_month.isoformat()),
                _safe_cell(item.get_kind_display()),
                _safe_cell(item.description),
                _safe_cell(item.category.name if item.category else ""),
                _safe_cell(item.account.name if item.account else ""),
                _safe_cell(item.amount),
                _safe_cell(item.get_status_display()),
                _safe_cell(item.paid_at.isoformat() if item.paid_at else ""),
                _safe_cell(installment),
                _safe_cell(item.recurrence.description if item.recurrence else ""),
            ]
        )
    return output.getvalue()


def monthly_report(user, month: date | None = None) -> dict:
    month = month_start(month or timezone.localdate())
    summary = monthly_summary(user, month)
    plan = current_plan(user) or latest_plan(user)
    transactions = (
        Transaction.objects.filter(user=user, competence_month=month, deleted_at__isnull=True)
        .select_related("category", "account")
        .order_by("-transaction_date", "-created_at")
    )
    return {
        "month": month,
        "summary": summary,
        "transactions": transactions,
        "debts": debt_summary(user),
        "plan": plan,
        "adherence": adherence_summary(plan) if plan else None,
        "profile": Profile.objects.get_or_create(user=user)[0],
    }
