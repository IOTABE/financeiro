from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.dates import month_start

from .forms import (
    AccountForm,
    CategoryForm,
    InstallmentForm,
    RecurrenceForm,
    TransactionForm,
)
from .models import Account, Category, Recurrence, Transaction
from .services import materialize_user_recurrences


def _owned(request, model, pk):
    try:
        return get_object_or_404(model, pk=pk, user=request.user)
    except (ValidationError, Http404):
        raise Http404 from None


def _transaction_queryset(request):
    qs = (
        Transaction.objects.filter(user=request.user, deleted_at__isnull=True)
        .select_related("category", "account", "installment_group")
        .order_by("-transaction_date", "-created_at")
    )
    today = timezone.localdate()
    start = request.GET.get("from") or month_start(today).isoformat()
    end = request.GET.get("to") or today.isoformat()
    kind = request.GET.get("kind") or ""
    status = request.GET.get("status") or ""
    category = request.GET.get("category") or ""
    account = request.GET.get("account") or ""
    query = (request.GET.get("q") or "").strip()

    try:
        start_date = date.fromisoformat(start)
    except ValueError:
        start_date = month_start(today)
    try:
        end_date = date.fromisoformat(end)
    except ValueError:
        end_date = today

    qs = qs.filter(transaction_date__gte=start_date, transaction_date__lte=end_date)
    if kind in {Transaction.Kind.INCOME, Transaction.Kind.EXPENSE}:
        qs = qs.filter(kind=kind)
    if status in {Transaction.Status.PENDING, Transaction.Status.PAID, Transaction.Status.CANCELED}:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category_id=category)
    if account:
        qs = qs.filter(account_id=account)
    if query:
        qs = qs.filter(description__icontains=query)

    return qs, {
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "kind": kind,
        "status": status,
        "category": category,
        "account": account,
        "q": query,
    }


@login_required
def transaction_list(request):
    qs, filters = _transaction_queryset(request)
    paid = Q(status=Transaction.Status.PAID)
    totals = qs.aggregate(
        income=Sum("amount", filter=paid & Q(kind=Transaction.Kind.INCOME)),
        expense=Sum("amount", filter=paid & Q(kind=Transaction.Kind.EXPENSE)),
    )
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "finance/transaction_list.html",
        {
            "page": page,
            "filters": filters,
            "categories": Category.objects.filter(
                user=request.user, archived_at__isnull=True
            ).order_by("kind", "name"),
            "accounts": Account.objects.filter(
                user=request.user, archived_at__isnull=True
            ).order_by("name"),
            "income": totals["income"] or 0,
            "expense": totals["expense"] or 0,
            "balance": (totals["income"] or 0) - (totals["expense"] or 0),
            "today": timezone.localdate(),
        },
    )


@login_required
def transaction_create(request):
    form = TransactionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lançamento registrado.")
        return redirect("finance:transactions")
    return render(
        request,
        "finance/transaction_form.html",
        {"form": form, "title": "Novo lançamento", "mode": "single"},
    )


@login_required
def transaction_update(request, pk):
    transaction = _owned(request, Transaction, pk)
    form = TransactionForm(request.POST or None, instance=transaction, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lançamento atualizado.")
        return redirect("finance:transactions")
    return render(
        request,
        "finance/transaction_form.html",
        {"form": form, "title": "Editar lançamento", "mode": "single", "object": transaction},
    )


@login_required
@require_POST
def transaction_delete(request, pk):
    transaction = _owned(request, Transaction, pk)
    transaction.deleted_at = timezone.now()
    transaction.save(update_fields=["deleted_at", "updated_at"])
    messages.success(request, "Lançamento removido.")
    return redirect("finance:transactions")


@login_required
@require_POST
def transaction_toggle(request, pk):
    transaction = _owned(request, Transaction, pk)
    if transaction.status == Transaction.Status.PAID:
        transaction.status = Transaction.Status.PENDING
        transaction.paid_at = None
    else:
        transaction.status = Transaction.Status.PAID
        transaction.paid_at = transaction.transaction_date
    transaction.save(update_fields=["status", "paid_at", "updated_at"])
    messages.success(request, "Status atualizado.")
    return redirect("finance:transactions")


@login_required
def installment_create(request):
    form = InstallmentForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Compra parcelada registrada.")
        return redirect("finance:transactions")
    return render(
        request,
        "finance/transaction_form.html",
        {"form": form, "title": "Compra parcelada", "mode": "installment"},
    )


@login_required
def recurrence_list(request):
    recurrences = Recurrence.objects.filter(user=request.user).order_by("-is_active", "description")
    return render(request, "finance/recurrence_list.html", {"recurrences": recurrences})


@login_required
def recurrence_create(request):
    form = RecurrenceForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        materialize_user_recurrences(request.user)
        messages.success(request, "Recorrência criada e ocorrências do mês geradas.")
        return redirect("finance:recurrences")
    return render(
        request,
        "finance/recurrence_form.html",
        {"form": form, "title": "Nova recorrência"},
    )


@login_required
def recurrence_update(request, pk):
    recurrence = _owned(request, Recurrence, pk)
    form = RecurrenceForm(request.POST or None, instance=recurrence, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Recorrência atualizada.")
        return redirect("finance:recurrences")
    return render(
        request,
        "finance/recurrence_form.html",
        {"form": form, "title": "Editar recorrência", "object": recurrence},
    )


@login_required
@require_POST
def recurrence_toggle(request, pk):
    recurrence = _owned(request, Recurrence, pk)
    recurrence.is_active = not recurrence.is_active
    recurrence.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "Recorrência atualizada.")
    return redirect("finance:recurrences")


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).order_by("kind", "name")
    return render(
        request,
        "finance/category_list.html",
        {
            "categories": categories,
            "income_categories": categories.filter(
                kind=Category.Kind.INCOME, archived_at__isnull=True
            ),
            "expense_categories": categories.filter(
                kind=Category.Kind.EXPENSE, archived_at__isnull=True
            ),
            "archived": categories.filter(archived_at__isnull=False),
        },
    )


@login_required
def category_create(request):
    form = CategoryForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoria criada.")
        return redirect("finance:categories")
    return render(request, "finance/category_form.html", {"form": form, "title": "Nova categoria"})


@login_required
def category_update(request, pk):
    category = _owned(request, Category, pk)
    form = CategoryForm(request.POST or None, instance=category, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Categoria atualizada.")
        return redirect("finance:categories")
    return render(
        request,
        "finance/category_form.html",
        {"form": form, "title": "Editar categoria", "object": category},
    )


@login_required
@require_POST
def category_archive(request, pk):
    category = _owned(request, Category, pk)
    category.archived_at = timezone.now()
    category.save(update_fields=["archived_at", "updated_at"])
    messages.success(request, "Categoria arquivada.")
    return redirect("finance:categories")


@login_required
def account_list(request):
    accounts = Account.objects.filter(user=request.user).order_by("archived_at", "name")
    return render(request, "finance/account_list.html", {"accounts": accounts})


@login_required
def account_create(request):
    form = AccountForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Conta criada.")
        return redirect("finance:accounts")
    return render(request, "finance/account_form.html", {"form": form, "title": "Nova conta"})


@login_required
def account_update(request, pk):
    account = _owned(request, Account, pk)
    form = AccountForm(request.POST or None, instance=account, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Conta atualizada.")
        return redirect("finance:accounts")
    return render(
        request,
        "finance/account_form.html",
        {"form": form, "title": "Editar conta", "object": account},
    )


@login_required
@require_POST
def account_archive(request, pk):
    account = _owned(request, Account, pk)
    account.archived_at = timezone.now()
    account.save(update_fields=["archived_at", "updated_at"])
    messages.success(request, "Conta arquivada.")
    return redirect("finance:accounts")
