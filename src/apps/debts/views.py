from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Profile
from apps.accounts.services import financial_health
from apps.core.audit import log_event

from .forms import DebtForm, DebtPaymentForm
from .models import Debt
from .services import debt_summary, record_payment


def _owned(request, pk) -> Debt:
    try:
        return get_object_or_404(Debt, pk=pk, user=request.user, deleted_at__isnull=True)
    except (ValidationError, Http404):
        raise Http404 from None


@login_required
def debt_list(request):
    summary = debt_summary(request.user)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    health = financial_health(profile, summary["total_minimum"])
    all_debts = Debt.objects.filter(user=request.user, deleted_at__isnull=True).order_by(
        "status", "due_day"
    )
    return render(
        request,
        "debts/debt_list.html",
        {
            "summary": summary,
            "debts": all_debts,
            "commitment_pct": health["commitment_pct"],
        },
    )


@login_required
def debt_create(request):
    form = DebtForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        debt = form.save(commit=False)
        debt.user = request.user
        debt.save()
        messages.success(request, "Dívida cadastrada.")
        return redirect("debts:list")
    return render(request, "debts/debt_form.html", {"form": form, "title": "Nova dívida"})


@login_required
def debt_update(request, pk):
    debt = _owned(request, pk)
    form = DebtForm(request.POST or None, instance=debt)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dívida atualizada.")
        return redirect("debts:detail", pk=debt.pk)
    return render(
        request,
        "debts/debt_form.html",
        {"form": form, "title": "Editar dívida", "object": debt},
    )


@login_required
def debt_detail(request, pk):
    debt = _owned(request, pk)
    payment_form = DebtPaymentForm()
    payments = debt.payments.order_by("-paid_at", "-created_at")
    return render(
        request,
        "debts/debt_detail.html",
        {
            "debt": debt,
            "payment_form": payment_form,
            "payments": payments,
        },
    )


@login_required
@require_POST
def debt_pay(request, pk):
    debt = _owned(request, pk)
    form = DebtPaymentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Não foi possível registrar o pagamento. Confira os dados.")
        return render(
            request,
            "debts/debt_detail.html",
            {
                "debt": debt,
                "payment_form": form,
                "payments": debt.payments.order_by("-paid_at", "-created_at"),
            },
        )
    try:
        record_payment(
            debt=debt,
            amount=form.cleaned_data["amount"],
            paid_at=form.cleaned_data["paid_at"],
            kind=form.cleaned_data["kind"],
            note=form.cleaned_data["note"],
            idempotency_key=form.cleaned_data.get("idempotency_key", ""),
        )
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("debts:detail", pk=debt.pk)
    log_event(
        event="debt.payment_created",
        user=request.user,
        request=request,
        entity_type="debt",
        entity_id=str(debt.pk),
    )
    messages.success(request, "Pagamento registrado.")
    return redirect("debts:detail", pk=debt.pk)


@login_required
@require_POST
def debt_delete(request, pk):
    debt = _owned(request, pk)
    debt.deleted_at = timezone.now()
    debt.save(update_fields=["deleted_at", "updated_at"])
    messages.success(request, "Dívida removida.")
    return redirect("debts:list")
