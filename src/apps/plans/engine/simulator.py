from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from apps.core.dates import add_months

from .ordering import order_debts
from .rates import money
from .types import (
    Payoff,
    PlanInput,
    PlanResult,
    ScheduleEntry,
    Warning,
)

ZERO = Decimal("0")
RESIDUAL = Decimal("0.005")
LONG_PLAN_MONTHS = 60


def _empty_result(plan: PlanInput, reason: str, warnings=()) -> PlanResult:
    return PlanResult(
        status="infeasible",
        strategy=plan.strategy,
        monthly_available=money(plan.monthly_available),
        order=(),
        schedule=(),
        payoffs=(),
        total_interest=ZERO,
        total_paid=ZERO,
        months=0,
        debt_free_date=None,
        first_payment_month=None,
        first_payment_amount=ZERO,
        first_payoff=None,
        warnings=tuple(warnings)
        + (
            Warning(
                code="W_INFEASIBLE",
                severity="critical",
                message=reason,
            ),
        ),
        has_quick_wins=False,
        infeasible_reason=reason,
    )


def _extra_for_month(plan: PlanInput, month: int) -> Decimal:
    extra = money(plan.extra_payment)
    if extra <= 0:
        return ZERO
    if plan.extra_payment_months <= 0:
        return extra if month == 1 else ZERO
    return extra if month <= plan.extra_payment_months else ZERO


def simulate(plan: PlanInput) -> PlanResult:
    if plan.strategy not in {"avalanche", "snowball", "hybrid"}:
        raise ValueError(f"Estratégia inválida: {plan.strategy}")

    debts = tuple(debt for debt in plan.debts if debt.balance > 0)
    if not debts:
        return _empty_result(plan, "Nenhuma dívida ativa para incluir no plano.")

    monthly_available = money(plan.monthly_available)
    total_debt = money(sum((debt.balance for debt in debts), ZERO))
    minimums = money(sum((debt.minimum_payment for debt in debts), ZERO))
    surplus = money(monthly_available - minimums)

    if monthly_available <= 0:
        return _empty_result(
            plan,
            "O orçamento disponível para dívidas é zero. Ajuste o perfil financeiro.",
        )
    if surplus < 0:
        return _empty_result(
            plan,
            "As parcelas mínimas não cabem no orçamento disponível. Reduza despesas, "
            "aumente a renda ou renegocie antes de gerar o plano.",
        )

    order, has_quick_wins = order_debts(debts, plan.strategy, surplus, total_debt)
    debt_map = {debt.id: debt for debt in debts}
    state = {debt.id: {"balance": money(debt.balance)} for debt in debts}

    warnings: list[Warning] = []
    for debt in debts:
        interest = money(debt.balance * debt.monthly_rate)
        if debt.minimum_payment <= interest:
            warnings.append(
                Warning(
                    code="W_NEGATIVE_AMORT",
                    severity="critical",
                    message=(
                        f"{debt.name}: a parcela mínima ({debt.minimum_payment}) não cobre "
                        f"os juros do mês ({interest}). O saldo tende a crescer."
                    ),
                    debt_id=debt.id,
                )
            )
    if any(debt.priority_locked is not None for debt in debts):
        warnings.append(
            Warning(
                code="W_LOCKED_DEBT",
                severity="info",
                message="Há dívida(s) com prioridade manual; isso pode custar mais juros.",
            )
        )

    schedule: list[ScheduleEntry] = []
    payoffs: list[Payoff] = []
    total_interest = ZERO
    total_paid = ZERO
    first_payment_month: int | None = None
    first_payment_amount = ZERO
    first_payoff: Payoff | None = None
    max_monthly_payment = ZERO
    previous_total = total_debt
    growth_streak = 0
    growth_warned = False
    month = 0
    finished = False

    while month < plan.max_months:
        month += 1
        month_date = add_months(plan.start_month, month - 1)
        interest_by_debt: dict[str, Decimal] = {}
        payments: dict[str, Decimal] = {debt.id: ZERO for debt in debts}

        for item in order:
            debt = debt_map[item.debt_id]
            balance = state[debt.id]["balance"]
            if balance > 0:
                interest = money(balance * debt.monthly_rate)
                state[debt.id]["balance"] = money(balance + interest)
                total_interest += interest
                interest_by_debt[debt.id] = interest
            else:
                interest_by_debt[debt.id] = ZERO

        available = monthly_available + _extra_for_month(plan, month)

        for item in order:
            debt = debt_map[item.debt_id]
            balance = state[debt.id]["balance"]
            if balance <= 0 or available <= 0:
                continue
            payment = min(debt.minimum_payment, balance, available)
            payment = money(payment)
            state[debt.id]["balance"] = money(balance - payment)
            available = money(available - payment)
            payments[debt.id] += payment

        for item in order:
            if available <= 0:
                break
            debt = debt_map[item.debt_id]
            balance = state[debt.id]["balance"]
            if balance <= 0:
                continue
            payment = money(min(available, balance))
            state[debt.id]["balance"] = money(balance - payment)
            available = money(available - payment)
            payments[debt.id] += payment

        month_paid = ZERO
        for item in order:
            debt = debt_map[item.debt_id]
            payment = payments[debt.id]
            interest = interest_by_debt.get(debt.id, ZERO)
            closing = state[debt.id]["balance"]
            if closing <= RESIDUAL:
                closing = ZERO
                state[debt.id]["balance"] = ZERO
            interest_paid = min(interest, payment)
            principal = money(payment - interest_paid)
            capitalized = money(interest - interest_paid)
            if interest > 0 or payment > 0 or closing > 0:
                schedule.append(
                    ScheduleEntry(
                        month_index=month,
                        month=month_date,
                        debt_id=debt.id,
                        payment=money(payment),
                        interest=money(interest),
                        principal=principal,
                        capitalized_interest=capitalized,
                        closing_balance=money(closing),
                    )
                )
            month_paid += payment
            if closing == 0:
                existing = {payoff.debt_id for payoff in payoffs}
                if debt.id not in existing:
                    payoff = Payoff(debt_id=debt.id, month_index=month, month=month_date)
                    payoffs.append(payoff)
                    if first_payoff is None:
                        first_payoff = payoff

        total_paid = money(total_paid + month_paid)
        if first_payment_month is None and month_paid > 0:
            first_payment_month = month
            first_payment_amount = money(month_paid)
        max_monthly_payment = max(max_monthly_payment, money(month_paid))

        current_total = money(sum((state[debt.id]["balance"] for debt in debts), ZERO))
        if current_total > previous_total + RESIDUAL:
            growth_streak += 1
            if growth_streak >= 3 and not growth_warned:
                warnings.append(
                    Warning(
                        code="W_AGGREGATE_GROWTH",
                        severity="critical",
                        message=(
                            "A dívida total está crescendo. O orçamento não cobre os juros "
                            "do conjunto; revise o plano ou renegocie."
                        ),
                    )
                )
                growth_warned = True
        else:
            growth_streak = 0
        previous_total = current_total

        if all(state[debt.id]["balance"] <= RESIDUAL for debt in debts):
            finished = True
            break

    if not finished:
        warnings.append(
            Warning(
                code="W_TERM_EXCEEDED",
                severity="critical",
                message=(
                    f"O plano não terminou em {plan.max_months} meses. "
                    "Considere renegociar ou aumentar o valor mensal."
                ),
            )
        )
        status = "term_exceeded"
        debt_free_date = None
    else:
        status = "ok"
        debt_free_date = add_months(plan.start_month, month)

    if finished and month > LONG_PLAN_MONTHS:
        warnings.append(
            Warning(
                code="W_LONG_PLAN",
                severity="warning",
                message=(
                    f"O plano leva {month} meses (mais de 5 anos). "
                    "Considere renegociar prazos ou taxas."
                ),
            )
        )

    return PlanResult(
        status=status,
        strategy=plan.strategy,
        monthly_available=monthly_available,
        order=order,
        schedule=tuple(schedule),
        payoffs=tuple(payoffs),
        total_interest=money(total_interest),
        total_paid=money(total_paid),
        months=month,
        debt_free_date=debt_free_date,
        first_payment_month=first_payment_month,
        first_payment_amount=money(first_payment_amount),
        first_payoff=first_payoff,
        warnings=tuple(warnings),
        has_quick_wins=has_quick_wins,
        max_monthly_payment=money(max_monthly_payment),
    )


def _metrics(result: PlanResult) -> dict:
    return {
        "status": result.status,
        "months": result.months,
        "total_interest": str(result.total_interest),
        "total_paid": str(result.total_paid),
        "first_payment_month": result.first_payment_month,
        "first_payoff_month": result.first_payoff.month_index if result.first_payoff else None,
        "first_payoff_debt_id": result.first_payoff.debt_id if result.first_payoff else None,
        "has_quick_wins": result.has_quick_wins,
        "max_monthly_payment": str(result.max_monthly_payment),
        "debt_free_date": result.debt_free_date.isoformat() if result.debt_free_date else None,
        "warnings": [
            {"code": warning.code, "severity": warning.severity, "message": warning.message}
            for warning in result.warnings
        ],
    }


def compare_strategies(plan: PlanInput) -> dict:
    results = {
        strategy: simulate(replace(plan, strategy=strategy))
        for strategy in ("avalanche", "snowball", "hybrid")
    }
    metrics = {strategy: _metrics(result) for strategy, result in results.items()}
    feasible = [result for result in results.values() if result.status == "ok"]

    if not feasible:
        recommendation = None
        reason = "O orçamento não fecha em nenhuma estratégia. Revise despesas, renda ou renegocie."
    elif results["hybrid"].status == "ok" and results["hybrid"].has_quick_wins:
        recommendation = "hybrid"
        reason = (
            "A híbrida entrega vitórias rápidas sem abrir mão da economia de juros "
            "nas dívidas mais caras."
        )
    elif results["avalanche"].status == "ok":
        recommendation = "avalanche"
        reason = (
            "Não há dívida pequena o suficiente para uma vitória rápida; "
            "a avalanche tende a economizar mais juros."
        )
    else:
        recommendation = feasible[0].strategy
        reason = "A estratégia viável com menor risco é a recomendada."

    return {
        "strategies": metrics,
        "recommendation": recommendation,
        "reason": reason,
    }
