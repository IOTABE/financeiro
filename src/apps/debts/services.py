from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from .models import Debt, DebtPayment

CENT = Decimal("0.01")
ZERO = Decimal("0")


def money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def active_debts(user):
    return Debt.objects.filter(
        user=user,
        status__in=[Debt.Status.ACTIVE, Debt.Status.LATE],
        deleted_at__isnull=True,
    )


def debt_summary(user) -> dict:
    debts = list(active_debts(user).order_by("due_day", "-current_balance"))
    total_balance = money(sum((debt.current_balance for debt in debts), ZERO))
    total_minimum = money(sum((debt.minimum_payment for debt in debts), ZERO))
    negative = [debt for debt in debts if debt.has_negative_amortization]
    late = [debt for debt in debts if debt.status == Debt.Status.LATE]
    today = timezone.localdate()
    upcoming = [debt for debt in debts if debt.due_day >= today.day]
    nearest = (upcoming or debts)[0] if debts else None
    return {
        "debts": debts,
        "count": len(debts),
        "total_balance": total_balance,
        "total_minimum": total_minimum,
        "negative_amortization": negative,
        "late_count": len(late),
        "next_due": nearest,
    }


def record_payment(
    *,
    debt: Debt,
    amount: Decimal,
    paid_at: date | None = None,
    kind: str = DebtPayment.Kind.EXTRA,
    note: str = "",
    idempotency_key: str = "",
) -> DebtPayment:
    """Apply a payment and return the persisted record.

    Payments are capped at the total owed (balance + accrued interest). If the
    payment does not cover interest, the remainder is capitalized in the balance.
    """
    paid_at = paid_at or timezone.localdate()
    value = money(amount)
    if value <= 0:
        raise ValueError("O valor do pagamento deve ser maior que zero.")

    with db_transaction.atomic():
        locked = Debt.objects.select_for_update().get(pk=debt.pk)
        if idempotency_key:
            existing = DebtPayment.objects.filter(
                user=locked.user, idempotency_key=idempotency_key
            ).first()
            if existing:
                return existing

        interest = money(locked.current_balance * locked.monthly_rate)
        total_owed = locked.current_balance + interest
        if value > total_owed:
            value = total_owed

        interest_paid = min(interest, value)
        principal_paid = value - interest_paid
        new_balance = locked.current_balance + (interest - interest_paid) - principal_paid
        if new_balance <= Decimal("0.005"):
            new_balance = ZERO

        locked.current_balance = money(new_balance)
        if locked.current_balance == 0:
            locked.status = Debt.Status.PAID
        locked.save(update_fields=["current_balance", "status", "updated_at"])

        return DebtPayment.objects.create(
            user=locked.user,
            debt=locked,
            amount=value,
            principal_amount=money(principal_paid),
            interest_amount=money(interest_paid),
            paid_at=paid_at,
            kind=kind,
            note=note,
            idempotency_key=idempotency_key,
        )
