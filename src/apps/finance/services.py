from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.dates import add_months, due_date_in_month, month_start

from .models import Account, Category, InstallmentGroup, Recurrence, Transaction

CENT = Decimal("0.01")
ZERO = Decimal("0")

DEFAULT_CATEGORIES: tuple[tuple[str, str, bool], ...] = (
    ("Salário", Category.Kind.INCOME, False),
    ("Freelance", Category.Kind.INCOME, False),
    ("Outros ganhos", Category.Kind.INCOME, False),
    ("Moradia", Category.Kind.EXPENSE, True),
    ("Alimentação", Category.Kind.EXPENSE, True),
    ("Transporte", Category.Kind.EXPENSE, True),
    ("Saúde", Category.Kind.EXPENSE, True),
    ("Educação", Category.Kind.EXPENSE, False),
    ("Lazer", Category.Kind.EXPENSE, False),
    ("Assinaturas", Category.Kind.EXPENSE, False),
    ("Outros gastos", Category.Kind.EXPENSE, False),
)


def money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def ensure_finance_setup(user) -> None:
    """Seed default categories and a main account once per user."""
    if not Category.objects.filter(user=user).exists():
        Category.objects.bulk_create(
            [
                Category(
                    user=user,
                    name=name,
                    kind=kind,
                    is_essential=essential,
                    is_system=True,
                )
                for name, kind, essential in DEFAULT_CATEGORIES
            ],
            ignore_conflicts=True,
        )
    if not Account.objects.filter(user=user).exists():
        Account.objects.create(user=user, name="Conta principal", type=Account.Type.CHECKING)


def monthly_summary(user, month: date | None = None) -> dict:
    month = month_start(month or timezone.localdate())
    base = Transaction.objects.filter(user=user, competence_month=month, deleted_at__isnull=True)
    paid = base.filter(status=Transaction.Status.PAID)

    income = (
        paid.filter(kind=Transaction.Kind.INCOME).aggregate(total=Sum("amount"))["total"] or ZERO
    )
    expense = (
        paid.filter(kind=Transaction.Kind.EXPENSE).aggregate(total=Sum("amount"))["total"] or ZERO
    )
    pending_income = (
        base.filter(kind=Transaction.Kind.INCOME, status=Transaction.Status.PENDING).aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )
    pending_expense = (
        base.filter(kind=Transaction.Kind.EXPENSE, status=Transaction.Status.PENDING).aggregate(
            total=Sum("amount")
        )["total"]
        or ZERO
    )
    by_category = list(
        paid.filter(kind=Transaction.Kind.EXPENSE)
        .values("category__name", "category__color")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    return {
        "month": month,
        "income": money(income),
        "expense": money(expense),
        "balance": money(income - expense),
        "pending_income": money(pending_income),
        "pending_expense": money(pending_expense),
        "by_category": by_category,
        "transaction_count": base.count(),
    }


def create_installment_plan(
    *,
    user,
    description: str,
    total_amount: Decimal,
    installments: int,
    first_due_date: date,
    kind: str = Transaction.Kind.EXPENSE,
    category: Category | None = None,
    account: Account | None = None,
) -> InstallmentGroup:
    total = money(total_amount)
    if installments < 2 or installments > 360:
        raise ValueError("O número de parcelas deve estar entre 2 e 360.")
    if total <= 0:
        raise ValueError("O valor total deve ser maior que zero.")

    with db_transaction.atomic():
        group = InstallmentGroup.objects.create(
            user=user,
            description=description,
            total_amount=total,
            installments=installments,
            first_due_date=first_due_date,
            category=category,
            account=account,
        )
        base = (total / installments).quantize(CENT, rounding=ROUND_HALF_UP)
        amounts = [base] * (installments - 1)
        amounts.append(total - sum(amounts))

        for index, amount in enumerate(amounts, start=1):
            due = add_months(first_due_date, index - 1)
            Transaction.objects.create(
                user=user,
                account=account,
                category=category,
                installment_group=group,
                installment_number=index,
                kind=kind,
                amount=amount,
                description=f"{description} ({index}/{installments})",
                transaction_date=due,
                competence_month=month_start(due),
                status=Transaction.Status.PENDING,
                idempotency_key=f"inst:{group.id}:{index}",
            )
    return group


def first_due_date(start_date: date, due_day: int) -> date:
    candidate = due_date_in_month(start_date.year, start_date.month, due_day)
    if candidate < start_date:
        candidate = add_months(candidate, 1)
    return candidate


def create_recurrence(
    *,
    user,
    description: str,
    kind: str,
    amount: Decimal,
    due_day: int,
    start_date: date,
    end_date: date | None = None,
    category: Category | None = None,
    account: Account | None = None,
    is_active: bool = True,
) -> Recurrence:
    next_run = first_due_date(start_date, due_day)
    return Recurrence.objects.create(
        user=user,
        description=description,
        kind=kind,
        amount=money(amount),
        due_day=due_day,
        start_date=start_date,
        end_date=end_date,
        category=category,
        account=account,
        next_run=next_run,
        is_active=is_active,
    )


def materialize_recurrence(recurrence: Recurrence, until_date: date | None = None) -> int:
    until_date = until_date or timezone.localdate()
    created_count = 0
    with db_transaction.atomic():
        current = Recurrence.objects.select_for_update().get(pk=recurrence.pk)
        while current.is_active and current.next_run <= until_date:
            if current.end_date and current.next_run > current.end_date:
                current.is_active = False
                current.save(update_fields=["is_active", "updated_at"])
                break

            due = current.next_run
            _, created = Transaction.objects.get_or_create(
                recurrence=current,
                competence_month=month_start(due),
                defaults={
                    "user": current.user,
                    "account": current.account,
                    "category": current.category,
                    "kind": current.kind,
                    "amount": current.amount,
                    "description": current.description,
                    "transaction_date": due,
                    "status": Transaction.Status.PENDING,
                },
            )
            if created:
                created_count += 1
            current.next_run = add_months(due, 1)
            current.save(update_fields=["next_run", "updated_at"])
    return created_count


def materialize_user_recurrences(user, until_date: date | None = None) -> int:
    total = 0
    for recurrence in Recurrence.objects.filter(user=user, is_active=True):
        total += materialize_recurrence(recurrence, until_date)
    return total
