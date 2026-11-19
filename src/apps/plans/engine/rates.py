from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")


def money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_rate_from_annual(annual: Decimal) -> Decimal:
    return (Decimal(1) + Decimal(annual)) ** (Decimal(1) / Decimal(12)) - Decimal(1)


def annual_rate_from_monthly(monthly: Decimal) -> Decimal:
    return (Decimal(1) + Decimal(monthly)) ** Decimal(12) - Decimal(1)


def pmt(principal: Decimal, rate: Decimal, periods: int) -> Decimal:
    principal = Decimal(principal)
    rate = Decimal(rate)
    if periods <= 0:
        raise ValueError("O número de períodos deve ser maior que zero.")
    if rate == 0:
        return principal / periods
    factor = (Decimal(1) + rate) ** (-periods)
    return principal * rate / (Decimal(1) - factor)


def implied_rate(
    principal: Decimal, payment: Decimal, periods: int, tolerance=Decimal("0.00000001")
):
    """Bisection solver for the monthly rate implied by a fixed payment."""
    principal = Decimal(principal)
    payment = Decimal(payment)
    if principal <= 0 or payment <= 0 or periods <= 0:
        raise ValueError("Principal, pagamento e períodos devem ser positivos.")

    low = Decimal("0")
    high = Decimal("1")
    for _ in range(120):
        middle = (low + high) / Decimal(2)
        try:
            estimate = pmt(principal, middle, periods)
        except (OverflowError, ZeroDivisionError):
            high = middle
            continue
        if abs(estimate - payment) < tolerance:
            return middle
        if estimate > payment:
            high = middle
        else:
            low = middle
    return (low + high) / Decimal(2)
