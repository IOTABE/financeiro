from __future__ import annotations

from decimal import Decimal

from .types import DebtInput, OrderItem

ZERO = Decimal("0")
TEN_PERCENT = Decimal("0.10")
QUICK_WIN_SHARE = Decimal("0.15")
MAX_QUICK_WINS = 3


def _avalanche_key(debt: DebtInput):
    return (-debt.monthly_rate, debt.balance, debt.due_day, debt.id)


def _snowball_key(debt: DebtInput):
    return (debt.balance, -debt.monthly_rate, debt.due_day, debt.id)


def order_debts(
    debts: tuple[DebtInput, ...] | list[DebtInput],
    strategy: str,
    surplus: Decimal,
    total_debt: Decimal,
) -> tuple[tuple[OrderItem, ...], bool]:
    locked = sorted(
        [debt for debt in debts if debt.priority_locked is not None],
        key=lambda debt: (debt.priority_locked, debt.id),
    )
    unlocked = [debt for debt in debts if debt.priority_locked is None]

    if strategy == "avalanche":
        ordered = sorted(unlocked, key=_avalanche_key)
        quick_wins: list[DebtInput] = []
    elif strategy == "snowball":
        ordered = sorted(unlocked, key=_snowball_key)
        quick_wins = []
    elif strategy == "hybrid":
        candidates = [
            debt
            for debt in unlocked
            if debt.balance <= 2 * max(surplus, ZERO) or debt.balance <= TEN_PERCENT * total_debt
        ]
        candidates.sort(key=_snowball_key)
        quick_wins = []
        used_share = ZERO
        for debt in candidates:
            if len(quick_wins) >= MAX_QUICK_WINS:
                break
            if total_debt > 0 and used_share + debt.balance > QUICK_WIN_SHARE * total_debt:
                continue
            quick_wins.append(debt)
            used_share += debt.balance
        quick_ids = {debt.id for debt in quick_wins}
        ordered = quick_wins + sorted(
            [debt for debt in unlocked if debt.id not in quick_ids], key=_avalanche_key
        )
    else:
        raise ValueError(f"Estratégia inválida: {strategy}")

    items: list[OrderItem] = []
    priority = 1
    for debt in locked:
        items.append(
            OrderItem(
                debt_id=debt.id,
                priority=priority,
                reason="Ordem definida manualmente por você.",
            )
        )
        priority += 1

    quick_ids = {debt.id for debt in quick_wins}
    for debt in ordered:
        if debt.id in quick_ids:
            reason = (
                f"Vitória rápida: saldo de {debt.balance} com taxa de "
                f"{debt.monthly_rate * 100:.2f}% a.m."
            )
        elif strategy == "snowball":
            reason = f"Menor saldo ({debt.balance}) entre as dívidas restantes."
        elif strategy == "hybrid":
            reason = f"Maior taxa efetiva ({debt.monthly_rate * 100:.2f}% a.m.) após as vitórias rápidas."
        else:
            reason = f"Maior taxa efetiva ({debt.monthly_rate * 100:.2f}% a.m.)."
        items.append(OrderItem(debt_id=debt.id, priority=priority, reason=reason))
        priority += 1

    return tuple(items), bool(quick_wins)
