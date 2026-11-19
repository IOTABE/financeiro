from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models import Profile

CENT = Decimal("0.01")
ZERO = Decimal("0")


def money(value: Decimal | int | str | None) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def financial_health(profile: Profile, minimum_payments: Decimal = ZERO) -> dict[str, object]:
    """Compute the Phase 1 financial diagnosis.

    Debt payments are passed explicitly so the same service can be reused when
    debts arrive in Phase 2.
    """
    net = money(profile.net_income)
    gross = money(profile.gross_income)
    essentials = money(profile.essential_expenses)
    min_existential = money(profile.min_existential)
    other_planned = money(profile.other_planned_expenses)
    minimums = money(minimum_payments)

    essential_floor = max(essentials, min_existential)
    debt_budget = money(net - essential_floor - other_planned)
    free_cash = money(debt_budget - minimums)

    commitment = (minimums / net) if net > 0 else None
    dti_base = gross if gross > 0 else net
    dti = (minimums / dti_base) if dti_base > 0 else None

    alerts: list[dict[str, str]] = []
    if net <= 0:
        risk = "unknown"
    elif free_cash < 0 or (commitment is not None and commitment > Decimal("0.50")):
        risk = "critical"
    elif commitment is not None and commitment > Decimal("0.30"):
        risk = "attention"
    else:
        risk = "healthy"

    if net <= 0:
        alerts.append(
            {
                "code": "W_PROFILE_INCOMPLETE",
                "severity": "info",
                "message": "Informe sua renda para calcular o diagnóstico.",
            }
        )
    elif debt_budget <= 0:
        alerts.append(
            {
                "code": "W_BUDGET_NEGATIVE",
                "severity": "critical",
                "message": "Seu orçamento não fecha. Vamos ajustar o essencial?",
            }
        )
    if commitment is not None and commitment > Decimal("0.50"):
        alerts.append(
            {
                "code": "W_COMMITMENT_CRITICAL",
                "severity": "critical",
                "message": "Mais da metade da renda está comprometida com dívidas.",
            }
        )
    elif commitment is not None and commitment > Decimal("0.30"):
        alerts.append(
            {
                "code": "W_COMMITMENT_ATTENTION",
                "severity": "warning",
                "message": "Evite novas dívidas e priorize a quitação.",
            }
        )

    risk_labels = {
        "healthy": "Saudável",
        "attention": "Atenção",
        "critical": "Crítico",
        "unknown": "A definir",
    }

    return {
        "risk_label": risk_labels[risk],
        "net_income": net,
        "gross_income": gross,
        "essential_floor": money(essential_floor),
        "other_planned_expenses": other_planned,
        "debt_budget": debt_budget,
        "minimum_payments": minimums,
        "free_cash": free_cash,
        "commitment_ratio": commitment,
        "commitment_pct": (commitment * 100) if commitment is not None else None,
        "dti_ratio": dti,
        "dti_pct": (dti * 100) if dti is not None else None,
        "risk_level": risk,
        "alerts": alerts,
        "has_income": net > 0,
    }
