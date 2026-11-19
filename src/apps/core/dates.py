from __future__ import annotations

import calendar
from datetime import date


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def due_date_in_month(year: int, month: int, due_day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(due_day, last_day))
