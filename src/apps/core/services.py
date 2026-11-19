from __future__ import annotations

from django.utils import timezone

from apps.accounts.models import Profile
from apps.accounts.services import financial_health
from apps.debts.services import debt_summary
from apps.finance.models import Account, Recurrence, Transaction
from apps.finance.services import monthly_summary
from apps.plans.services import adherence_summary, current_plan, latest_plan


def financial_overview(user) -> dict:
    profile, _ = Profile.objects.get_or_create(user=user)
    debts = debt_summary(user)
    health = financial_health(profile, debts["total_minimum"])
    month = monthly_summary(user)
    plan = current_plan(user) or latest_plan(user)

    alerts = list(health["alerts"])
    for debt in debts["negative_amortization"]:
        alerts.append(
            {
                "code": "W_NEGATIVE_AMORT",
                "severity": "critical",
                "message": f"{debt}: a parcela mínima não cobre os juros do mês.",
            }
        )
    if debts["late_count"]:
        alerts.append(
            {
                "code": "W_LATE_DEBT",
                "severity": "critical",
                "message": f"{debts['late_count']} dívida(s) em atraso precisam de atenção.",
            }
        )
    if not month["transaction_count"]:
        alerts.append(
            {
                "code": "W_NO_TRANSACTIONS",
                "severity": "info",
                "message": "Registre sua primeira receita ou despesa para acompanhar o mês.",
            }
        )
    if not debts["count"]:
        alerts.append(
            {
                "code": "W_NO_DEBTS",
                "severity": "info",
                "message": "Cadastre suas dívidas para o plano de regularização ficar completo.",
            }
        )

    has_account = Account.objects.filter(user=user, archived_at__isnull=True).exists()
    has_transactions = Transaction.objects.filter(user=user, deleted_at__isnull=True).exists()
    has_debts = debts["count"] > 0
    has_plan = bool(plan and plan.status in {"active", "stale"})
    steps = [
        {"key": "profile", "label": "Completar perfil financeiro", "done": health["has_income"]},
        {"key": "account", "label": "Criar uma conta", "done": has_account},
        {
            "key": "transaction",
            "label": "Registrar uma receita ou despesa",
            "done": has_transactions,
        },
        {"key": "debt", "label": "Cadastrar uma dívida", "done": has_debts},
        {"key": "plan", "label": "Gerar plano de regularização", "done": has_plan},
    ]
    done_steps = sum(1 for step in steps if step["done"])

    recent = (
        Transaction.objects.filter(user=user, deleted_at__isnull=True)
        .select_related("category", "account")
        .order_by("-transaction_date", "-created_at")[:6]
    )
    upcoming = (
        Transaction.objects.filter(
            user=user,
            deleted_at__isnull=True,
            status=Transaction.Status.PENDING,
        )
        .select_related("category", "account")
        .order_by("transaction_date")[:5]
    )
    recurrences = Recurrence.objects.filter(user=user, is_active=True).count()
    plan_adherence = (
        adherence_summary(plan) if plan else {"due": 0, "paid": 0, "pending": 0, "pct": 0}
    )

    return {
        "profile": profile,
        "health": health,
        "month": month,
        "debts": debts,
        "plan": plan,
        "plan_adherence": plan_adherence,
        "has_plan": has_plan,
        "alerts": alerts,
        "steps": steps,
        "progress": int(done_steps / len(steps) * 100),
        "done_steps": done_steps,
        "total_steps": len(steps),
        "has_account": has_account,
        "has_transactions": has_transactions,
        "has_debts": has_debts,
        "recent_transactions": recent,
        "upcoming_transactions": upcoming,
        "recurrence_count": recurrences,
        "recurrences": recurrences,
        "today": timezone.localdate(),
    }
