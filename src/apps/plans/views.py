from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.audit import log_event
from apps.debts.models import Debt

from .forms import PlanGenerateForm, SimulationForm
from .models import Plan, PlanSchedule, Simulation
from .services import (
    adherence_summary,
    apply_simulation,
    compare_for_user,
    current_plan,
    generate_plan,
    latest_plan,
    mark_schedule_paid,
    recalculate_plan,
    simulate_scenario,
)


def _owned(request, model, pk):
    try:
        return get_object_or_404(model, pk=pk, user=request.user)
    except (ValidationError, Http404):
        raise Http404 from None


def _has_debts(user) -> bool:
    return Debt.objects.filter(
        user=user,
        status__in=[Debt.Status.ACTIVE, Debt.Status.LATE],
        deleted_at__isnull=True,
    ).exists()


def _render_plan(request, plan: Plan):
    schedule_qs = plan.schedule.select_related("debt", "adherence").order_by(
        "competence_month", "id"
    )
    page = Paginator(schedule_qs, 60).get_page(request.GET.get("page"))
    totals = schedule_qs.aggregate(
        payments=Sum("payment"),
        interest=Sum("interest"),
        principal=Sum("principal"),
    )
    return render(
        request,
        "plans/plan_detail.html",
        {
            "plan": plan,
            "items": plan.items.all(),
            "page": page,
            "totals": totals,
            "warnings": (plan.summary or {}).get("warnings", []),
            "generate_form": PlanGenerateForm(),
            "has_debts": _has_debts(request.user),
            "adherence": adherence_summary(plan),
            "today": timezone.localdate(),
        },
    )


@login_required
def current(request):
    plan = current_plan(request.user) or latest_plan(request.user)
    if plan is None:
        return render(
            request,
            "plans/start.html",
            {"form": PlanGenerateForm(), "has_debts": _has_debts(request.user)},
        )
    return _render_plan(request, plan)


@login_required
def detail(request, pk):
    plan = _owned(request, Plan, pk)
    return _render_plan(request, plan)


@login_required
def generate(request):
    if request.method != "POST":
        return redirect("plans:current")
    form = PlanGenerateForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Não foi possível gerar o plano. Confira os dados.")
        return render(
            request,
            "plans/start.html",
            {"form": form, "has_debts": _has_debts(request.user)},
        )
    plan = generate_plan(
        request.user,
        strategy=form.cleaned_data["strategy"],
        start_month=form.cleaned_data["start_month"],
        extra_payment=form.cleaned_data["extra_payment"],
        extra_payment_months=form.cleaned_data["extra_payment_months"],
    )
    log_event(
        event="plan.generated",
        user=request.user,
        request=request,
        entity_type="plan",
        entity_id=str(plan.pk),
        metadata={"strategy": plan.strategy, "status": plan.status},
    )
    if plan.status == Plan.Status.ACTIVE:
        messages.success(request, "Plano de regularização gerado.")
    else:
        messages.warning(
            request,
            "O plano foi registrado, mas precisa de ajustes para ser viável.",
        )
    return redirect("plans:detail", pk=plan.pk)


@login_required
def compare(request):
    comparison = compare_for_user(request.user)
    return render(
        request,
        "plans/compare.html",
        {
            "comparison": comparison,
            "form": PlanGenerateForm(),
            "start_month": timezone.localdate().replace(day=1),
            "has_debts": _has_debts(request.user),
        },
    )


@login_required
@require_POST
def recalculate(request, pk):
    plan = _owned(request, Plan, pk)
    try:
        new_plan = recalculate_plan(plan)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("plans:detail", pk=plan.pk)
    log_event(
        event="plan.recalculated",
        user=request.user,
        request=request,
        entity_type="plan",
        entity_id=str(new_plan.pk),
    )
    messages.success(request, "Plano recalculado com os dados atuais.")
    return redirect("plans:detail", pk=new_plan.pk)


@login_required
def simulate(request):
    base_plan = current_plan(request.user)
    if request.method == "POST":
        form = SimulationForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                simulation = simulate_scenario(
                    request.user,
                    kind=form.cleaned_data["kind"],
                    params=form.get_params(),
                    name=form.cleaned_data["name"],
                    base_plan=base_plan,
                )
            except ValueError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, "Cenário simulado.")
                return redirect("plans:simulation_detail", pk=simulation.pk)
    else:
        form = SimulationForm(user=request.user)
    return render(
        request,
        "plans/simulator.html",
        {"form": form, "base_plan": base_plan},
    )


@login_required
def simulation_detail(request, pk):
    simulation = _owned(request, Simulation, pk)
    summary = simulation.result_summary or {}
    return render(
        request,
        "plans/simulation_detail.html",
        {
            "simulation": simulation,
            "baseline": summary.get("baseline", {}),
            "scenario": summary.get("scenario", {}),
            "delta": summary.get("delta", {}),
        },
    )


@login_required
@require_POST
def apply_simulation_view(request, pk):
    simulation = _owned(request, Simulation, pk)
    try:
        plan = apply_simulation(simulation)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("plans:simulation_detail", pk=simulation.pk)
    log_event(
        event="plan.simulation_applied",
        user=request.user,
        request=request,
        entity_type="plan",
        entity_id=str(plan.pk),
        metadata={"simulation_id": str(simulation.pk)},
    )
    messages.success(request, "Cenário transformado em plano.")
    return redirect("plans:detail", pk=plan.pk)


@login_required
@require_POST
def schedule_pay(request, pk):
    schedule = get_object_or_404(
        PlanSchedule.objects.select_related("plan"), pk=pk, plan__user=request.user
    )
    try:
        payment = mark_schedule_paid(user=request.user, schedule=schedule)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        log_event(
            event="plan.schedule_paid",
            user=request.user,
            request=request,
            entity_type="plan_schedule",
            entity_id=str(schedule.pk),
            metadata={"plan_id": str(schedule.plan_id)},
        )
        messages.success(
            request,
            f"Parcela de {payment.amount} marcada como paga.",
        )
    return redirect("plans:detail", pk=schedule.plan_id)
