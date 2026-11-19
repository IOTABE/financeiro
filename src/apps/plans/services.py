from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounts.models import Profile
from apps.core.dates import month_start
from apps.debts.models import Debt
from apps.plans.engine import DebtInput, PlanInput, compare_strategies, simulate
from apps.plans.engine.rates import money, pmt
from apps.plans.models import Plan, PlanItem, PlanPayment, PlanSchedule, Simulation

from .constants import DEFAULT_MAX_MONTHS, ENGINE_VERSION

ZERO = Decimal("0")


def _profile_budget(
    profile: Profile, income_factor=Decimal("1"), expense_factor=Decimal("1")
) -> Decimal:
    net = money(profile.net_income)
    piso = money(max(profile.essential_expenses or ZERO, profile.min_existential or ZERO))
    other = money(profile.other_planned_expenses)
    return money(net * income_factor - piso * expense_factor - other * expense_factor)


def _active_debts(user):
    return Debt.objects.filter(
        user=user,
        status__in=[Debt.Status.ACTIVE, Debt.Status.LATE],
        deleted_at__isnull=True,
    ).order_by("due_day", "-current_balance")


def _debt_inputs(user) -> tuple[DebtInput, ...]:
    return tuple(
        DebtInput(
            id=str(debt.pk),
            name=str(debt),
            balance=money(debt.current_balance),
            monthly_rate=debt.monthly_rate,
            minimum_payment=money(debt.minimum_payment),
            due_day=debt.due_day,
            priority_locked=debt.priority_locked,
        )
        for debt in _active_debts(user)
    )


def _snapshot(
    *,
    profile: Profile,
    debts: tuple[DebtInput, ...],
    plan_input: PlanInput,
    label: str,
) -> dict:
    return {
        "generated_at": timezone.now().isoformat(),
        "engine_version": ENGINE_VERSION,
        "label": label,
        "strategy": plan_input.strategy,
        "start_month": plan_input.start_month.isoformat(),
        "monthly_available": str(plan_input.monthly_available),
        "extra_payment": str(plan_input.extra_payment),
        "extra_payment_months": plan_input.extra_payment_months,
        "profile": {
            "gross_income": str(profile.gross_income or ZERO),
            "net_income": str(profile.net_income or ZERO),
            "essential_expenses": str(profile.essential_expenses or ZERO),
            "min_existential": str(profile.min_existential or ZERO),
            "other_planned_expenses": str(profile.other_planned_expenses or ZERO),
        },
        "debts": [
            {
                "id": debt.id,
                "name": debt.name,
                "balance": str(debt.balance),
                "monthly_rate": str(debt.monthly_rate),
                "minimum_payment": str(debt.minimum_payment),
                "due_day": debt.due_day,
                "priority_locked": debt.priority_locked,
            }
            for debt in debts
        ],
    }


def build_plan_input(
    user,
    *,
    strategy: str = "hybrid",
    start_month: date | None = None,
    extra_payment: Decimal = ZERO,
    extra_payment_months: int = 0,
    label: str = "",
) -> tuple[PlanInput, dict, Profile]:
    profile, _ = Profile.objects.get_or_create(user=user)
    debts = _debt_inputs(user)
    monthly_available = _profile_budget(profile)
    plan_input = PlanInput(
        monthly_available=monthly_available,
        debts=debts,
        strategy=strategy,
        start_month=month_start(start_month or timezone.localdate()),
        extra_payment=money(extra_payment),
        extra_payment_months=max(0, int(extra_payment_months)),
        max_months=DEFAULT_MAX_MONTHS,
    )
    snapshot = _snapshot(profile=profile, debts=debts, plan_input=plan_input, label=label)
    return plan_input, snapshot, profile


def _result_summary(result) -> dict:
    return {
        "status": result.status,
        "strategy": result.strategy,
        "monthly_available": str(result.monthly_available),
        "total_interest": str(result.total_interest),
        "total_paid": str(result.total_paid),
        "months": result.months,
        "debt_free_date": result.debt_free_date.isoformat() if result.debt_free_date else None,
        "first_payment_month": result.first_payment_month,
        "first_payment_amount": str(result.first_payment_amount),
        "max_monthly_payment": str(result.max_monthly_payment),
        "has_quick_wins": result.has_quick_wins,
        "infeasible_reason": result.infeasible_reason,
        "warnings": [
            {
                "code": warning.code,
                "severity": warning.severity,
                "message": warning.message,
                "debt_id": warning.debt_id,
            }
            for warning in result.warnings
        ],
        "order": [
            {"debt_id": item.debt_id, "priority": item.priority, "reason": item.reason}
            for item in result.order
        ],
        "payoffs": [
            {
                "debt_id": payoff.debt_id,
                "month_index": payoff.month_index,
                "month": payoff.month.isoformat(),
            }
            for payoff in result.payoffs
        ],
    }


def generate_plan(
    user,
    *,
    strategy: str = "hybrid",
    start_month: date | None = None,
    extra_payment: Decimal = ZERO,
    extra_payment_months: int = 0,
    label: str = "",
    plan_input: PlanInput | None = None,
    snapshot: dict | None = None,
) -> Plan:
    if plan_input is None:
        plan_input, snapshot, _ = build_plan_input(
            user,
            strategy=strategy,
            start_month=start_month,
            extra_payment=extra_payment,
            extra_payment_months=extra_payment_months,
            label=label,
        )
    elif snapshot is None:
        _, snapshot, _ = build_plan_input(user, strategy=strategy, start_month=start_month)

    result = simulate(plan_input)
    status_map = {
        "ok": Plan.Status.ACTIVE,
        "infeasible": Plan.Status.INFEASIBLE,
        "term_exceeded": Plan.Status.TERM_EXCEEDED,
    }
    plan_status = status_map[result.status]
    debt_objects = {str(debt.pk): debt for debt in _active_debts(user)}
    debt_names = {debt_id: str(debt) for debt_id, debt in debt_objects.items()}
    for debt in plan_input.debts:
        debt_names.setdefault(debt.id, debt.name)

    with db_transaction.atomic():
        Plan.objects.filter(user=user, status=Plan.Status.ACTIVE).update(
            status=Plan.Status.ARCHIVED, updated_at=timezone.now()
        )
        plan = Plan.objects.create(
            user=user,
            label=label,
            strategy=plan_input.strategy,
            status=plan_status,
            engine_version=ENGINE_VERSION,
            input_snapshot=snapshot or {},
            summary=_result_summary(result),
            monthly_available=result.monthly_available,
            total_interest=result.total_interest,
            total_paid=result.total_paid,
            months_to_payoff=result.months or None,
            debt_free_date=result.debt_free_date,
            infeasible_reason=result.infeasible_reason,
        )

        if result.status in {"ok", "term_exceeded"}:
            by_debt: dict[str, list] = defaultdict(list)
            for entry in result.schedule:
                by_debt[entry.debt_id].append(entry)

            items = []
            for order_item in result.order:
                entries = by_debt.get(order_item.debt_id, [])
                payoff_month = next(
                    (entry.month for entry in entries if entry.closing_balance == 0),
                    None,
                )
                items.append(
                    PlanItem(
                        plan=plan,
                        debt=debt_objects.get(order_item.debt_id),
                        debt_name=debt_names.get(order_item.debt_id, "Dívida"),
                        priority_order=order_item.priority,
                        reason=order_item.reason,
                        projected_payoff_month=payoff_month,
                        projected_interest=money(sum((e.interest for e in entries), ZERO)),
                        projected_total_paid=money(sum((e.payment for e in entries), ZERO)),
                    )
                )
            PlanItem.objects.bulk_create(items)

            schedules = [
                PlanSchedule(
                    plan=plan,
                    debt=debt_objects.get(entry.debt_id),
                    debt_name=debt_names.get(entry.debt_id, "Dívida"),
                    competence_month=entry.month,
                    payment=entry.payment,
                    interest=entry.interest,
                    principal=entry.principal,
                    capitalized_interest=entry.capitalized_interest,
                    closing_balance=entry.closing_balance,
                )
                for entry in result.schedule
            ]
            PlanSchedule.objects.bulk_create(schedules, batch_size=1000)

    return plan


def current_plan(user) -> Plan | None:
    return (
        Plan.objects.filter(user=user, status__in=[Plan.Status.ACTIVE, Plan.Status.STALE])
        .order_by("-generated_at")
        .first()
    )


def latest_plan(user) -> Plan | None:
    return Plan.objects.filter(user=user).order_by("-generated_at").first()


def mark_plan_stale(user) -> int:
    return Plan.objects.filter(user=user, status=Plan.Status.ACTIVE).update(
        status=Plan.Status.STALE, updated_at=timezone.now()
    )


def compare_for_user(user, *, start_month: date | None = None) -> dict:
    plan_input, _, _ = build_plan_input(user, strategy="hybrid", start_month=start_month)
    comparison = compare_strategies(plan_input)
    comparison["monthly_available"] = str(plan_input.monthly_available)
    comparison["debt_count"] = len(plan_input.debts)
    return comparison


def recalculate_plan(plan: Plan) -> Plan:
    snapshot = plan.input_snapshot or {}
    start = snapshot.get("start_month")
    start_month = date.fromisoformat(start) if start else None
    extra = Decimal(snapshot.get("extra_payment", "0") or "0")
    months = int(snapshot.get("extra_payment_months", 0) or 0)

    scenario = snapshot.get("scenario")
    if scenario:
        plan_input, base_snapshot, profile = build_plan_input(
            plan.user,
            strategy=plan.strategy,
            start_month=start_month,
            label=plan.label,
        )
        plan_input = _apply_scenario(
            plan_input,
            kind=scenario.get("kind", ""),
            params=scenario.get("params", {}),
            profile=profile,
        )
        scenario_snapshot = {**base_snapshot, "scenario": scenario}
        new_plan = generate_plan(
            plan.user,
            strategy=plan_input.strategy,
            start_month=plan_input.start_month,
            label=plan.label,
            plan_input=plan_input,
            snapshot=scenario_snapshot,
        )
    else:
        new_plan = generate_plan(
            plan.user,
            strategy=plan.strategy,
            start_month=start_month,
            extra_payment=extra,
            extra_payment_months=months,
            label=plan.label,
        )

    if plan.pk != new_plan.pk:
        Plan.objects.filter(pk=plan.pk).update(
            status=Plan.Status.ARCHIVED, updated_at=timezone.now()
        )
    return new_plan


def _apply_scenario(
    plan_input: PlanInput,
    *,
    kind: str,
    params: dict,
    profile: Profile,
) -> PlanInput:
    if kind == Simulation.Kind.EXPENSE_CUT:
        cut = money(params.get("expense_cut", "0"))
        if cut <= 0:
            raise ValueError("Informe um valor de corte maior que zero.")
        return replace(plan_input, monthly_available=money(plan_input.monthly_available + cut))

    if kind == Simulation.Kind.EXTRA_INCOME:
        extra = money(params.get("extra_income", "0"))
        if extra <= 0:
            raise ValueError("Informe um valor de renda extra maior que zero.")
        months = max(0, int(params.get("extra_income_months", 0) or 0))
        return replace(
            plan_input,
            extra_payment=money(plan_input.extra_payment + extra),
            extra_payment_months=months,
        )

    if kind == Simulation.Kind.CONSERVATIVE:
        income_factor = Decimal(str(params.get("income_factor", "0.8")))
        expense_factor = Decimal(str(params.get("expense_factor", "1.1")))
        conservative_budget = _profile_budget(profile, income_factor, expense_factor)
        return replace(plan_input, monthly_available=max(ZERO, conservative_budget))

    if kind == Simulation.Kind.RENEGOTIATION:
        debt_id = str(params.get("debt_id", ""))
        target = next((debt for debt in plan_input.debts if debt.id == debt_id), None)
        if target is None:
            raise ValueError("Escolha uma dívida válida para simular a renegociação.")
        discount = Decimal(str(params.get("discount_percent", "0") or "0")) / Decimal("100")
        entry = money(params.get("entry_payment", "0") or "0")
        new_balance = money(target.balance * (Decimal(1) - discount) - entry)
        new_balance = max(ZERO, new_balance)
        rate_percent = params.get("new_rate_percent")
        new_rate = (
            Decimal(str(rate_percent)) / Decimal("100")
            if rate_percent not in (None, "")
            else target.monthly_rate
        )
        term = int(params.get("new_term_months", 0) or 0)
        new_minimum = (
            money(pmt(new_balance, new_rate, term))
            if term > 0 and new_balance > 0
            else target.minimum_payment
        )
        updated = replace(
            target,
            name=f"{target.name} (renegociada)",
            balance=new_balance,
            monthly_rate=new_rate,
            minimum_payment=new_minimum,
        )
        debts = tuple(updated if debt.id == target.id else debt for debt in plan_input.debts)
        return replace(plan_input, debts=debts)

    raise ValueError("Tipo de simulação inválido.")


def simulate_scenario(
    user,
    *,
    kind: str,
    params: dict,
    name: str,
    base_plan: Plan | None = None,
    persist: bool = True,
) -> Simulation:
    plan_input, _, profile = build_plan_input(
        user,
        strategy=base_plan.strategy if base_plan else "hybrid",
    )
    baseline = simulate(plan_input)
    scenario_input = _apply_scenario(plan_input, kind=kind, params=params, profile=profile)
    scenario = simulate(scenario_input)

    delta_months = None
    if baseline.status == "ok" and scenario.status == "ok":
        delta_months = scenario.months - baseline.months
    interest_saved = money(baseline.total_interest - scenario.total_interest)
    summary = {
        "baseline": _result_summary(baseline),
        "scenario": _result_summary(scenario),
        "delta": {
            "months": delta_months,
            "interest_saved": str(interest_saved),
            "monthly_available": str(scenario_input.monthly_available),
        },
    }
    if not persist:
        return Simulation(
            user=user,
            base_plan=base_plan,
            name=name,
            kind=kind,
            params=_json_params(params),
            result_summary=summary,
            engine_version=ENGINE_VERSION,
        )
    return Simulation.objects.create(
        user=user,
        base_plan=base_plan,
        name=name,
        kind=kind,
        params=_json_params(params),
        result_summary=summary,
        engine_version=ENGINE_VERSION,
    )


def _json_params(params: dict) -> dict:
    clean = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        clean[key] = str(value) if isinstance(value, Decimal) else value
    return clean


def apply_simulation(simulation: Simulation) -> Plan:
    plan_input, snapshot, profile = build_plan_input(
        simulation.user,
        strategy=simulation.base_plan.strategy if simulation.base_plan else "hybrid",
        label=simulation.name,
    )
    scenario_input = _apply_scenario(
        plan_input,
        kind=simulation.kind,
        params=simulation.params,
        profile=profile,
    )
    scenario_snapshot = {
        **snapshot,
        "scenario": {
            "simulation_id": str(simulation.pk),
            "kind": simulation.kind,
            "name": simulation.name,
            "params": simulation.params,
        },
    }
    plan = generate_plan(
        simulation.user,
        strategy=scenario_input.strategy,
        start_month=scenario_input.start_month,
        extra_payment=scenario_input.extra_payment,
        extra_payment_months=scenario_input.extra_payment_months,
        label=simulation.name,
        plan_input=scenario_input,
        snapshot=scenario_snapshot,
    )
    simulation.applied_at = timezone.now()
    simulation.save(update_fields=["applied_at"])
    return plan


def mark_schedule_paid(
    *,
    user,
    schedule: PlanSchedule,
    amount: Decimal | None = None,
    paid_at: date | None = None,
    note: str = "",
) -> PlanPayment:
    if schedule.plan.user_id != user.pk:
        raise ValueError("Parcela não pertence ao seu plano.")
    if schedule.payment <= 0:
        raise ValueError("Esta parcela não tem valor previsto.")
    existing = PlanPayment.objects.filter(schedule=schedule).first()
    if existing:
        return existing
    value = money(amount if amount is not None else schedule.payment)
    if value <= 0:
        raise ValueError("O valor pago deve ser maior que zero.")
    return PlanPayment.objects.create(
        user=user,
        plan=schedule.plan,
        schedule=schedule,
        amount=value,
        paid_at=paid_at or timezone.localdate(),
        note=note,
    )


def adherence_summary(plan: Plan, today: date | None = None) -> dict:
    today = today or timezone.localdate()
    due_rows = plan.schedule.filter(payment__gt=0, competence_month__lte=month_start(today))
    due = due_rows.count()
    paid = due_rows.filter(adherence__isnull=False).count()
    pct = int(paid / due * 100) if due else 0
    return {
        "due": due,
        "paid": paid,
        "pending": due - paid,
        "pct": pct,
    }
