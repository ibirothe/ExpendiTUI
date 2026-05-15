from __future__ import annotations

from decimal import Decimal
from typing import Mapping

from .constants import MONEY_PLACES, ROUNDING_MODE
from .models import ExpenseEntry, Frequency

MONTHS_PER_YEAR = Decimal("12")
FREQUENCY_TO_MONTHLY_FACTOR = {
    Frequency.DAILY: Decimal("365") / MONTHS_PER_YEAR,
    Frequency.WEEKLY: Decimal("52") / MONTHS_PER_YEAR,
    Frequency.BIWEEKLY: Decimal("26") / MONTHS_PER_YEAR,
    Frequency.MONTHLY: Decimal("1"),
    Frequency.QUARTERLY: Decimal("1") / Decimal("3"),
    Frequency.SEMIANNUAL: Decimal("1") / Decimal("6"),
    Frequency.ANNUAL: Decimal("1") / MONTHS_PER_YEAR,
}


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUNDING_MODE)


def _monthly_equivalent_precise(amount: Decimal, frequency: Frequency) -> Decimal:
    return amount * FREQUENCY_TO_MONTHLY_FACTOR[frequency]


def monthly_equivalent(amount: Decimal, frequency: Frequency) -> Decimal:
    return quantize_money(_monthly_equivalent_precise(amount, frequency))


def yearly_equivalent(amount: Decimal, frequency: Frequency) -> Decimal:
    return quantize_money(
        _monthly_equivalent_precise(amount, frequency) * MONTHS_PER_YEAR
    )


def total_monthly(data: Mapping[str, ExpenseEntry]) -> Decimal:
    total = sum(
        (
            _monthly_equivalent_precise(entry.amount, entry.frequency)
            for entry in data.values()
        ),
        Decimal("0"),
    )
    return quantize_money(total)


def total_yearly(data: Mapping[str, ExpenseEntry]) -> Decimal:
    return quantize_money(total_monthly(data) * MONTHS_PER_YEAR)
