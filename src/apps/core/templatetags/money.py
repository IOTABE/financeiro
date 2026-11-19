from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def brl(value) -> str:
    if value in (None, ""):
        return "R$ 0,00"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return f"R$ {number_format(amount, decimal_pos=2, use_l10n=True, force_grouping=True)}"


@register.filter
def percent(value, digits: int = 2) -> str:
    if value in (None, ""):
        return "—"
    try:
        amount = Decimal(value) * Decimal("100")
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    return f"{number_format(amount, decimal_pos=int(digits), use_l10n=True, force_grouping=True)}%"
