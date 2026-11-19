from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True)
class DebtInput:
    id: str
    name: str
    balance: Decimal
    monthly_rate: Decimal
    minimum_payment: Decimal
    due_day: int
    priority_locked: int | None = None


@dataclass(frozen=True)
class PlanInput:
    monthly_available: Decimal
    debts: tuple[DebtInput, ...]
    strategy: str = "hybrid"
    start_month: date = field(default_factory=lambda: date.today().replace(day=1))
    extra_payment: Decimal = ZERO
    extra_payment_months: int = 0
    max_months: int = 600


@dataclass(frozen=True)
class Warning:
    code: str
    severity: str
    message: str
    debt_id: str | None = None


@dataclass(frozen=True)
class OrderItem:
    debt_id: str
    priority: int
    reason: str


@dataclass(frozen=True)
class ScheduleEntry:
    month_index: int
    month: date
    debt_id: str
    payment: Decimal
    interest: Decimal
    principal: Decimal
    capitalized_interest: Decimal
    closing_balance: Decimal


@dataclass(frozen=True)
class Payoff:
    debt_id: str
    month_index: int
    month: date


@dataclass(frozen=True)
class PlanResult:
    status: str
    strategy: str
    monthly_available: Decimal
    order: tuple[OrderItem, ...]
    schedule: tuple[ScheduleEntry, ...]
    payoffs: tuple[Payoff, ...]
    total_interest: Decimal
    total_paid: Decimal
    months: int
    debt_free_date: date | None
    first_payment_month: int | None
    first_payment_amount: Decimal
    first_payoff: Payoff | None
    warnings: tuple[Warning, ...]
    has_quick_wins: bool
    infeasible_reason: str = ""
    max_monthly_payment: Decimal = ZERO
