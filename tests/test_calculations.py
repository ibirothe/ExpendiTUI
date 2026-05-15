from decimal import Decimal

from recurring_expenses_tui.calculations import monthly_equivalent, total_monthly, total_yearly
from recurring_expenses_tui.models import ExpenseEntry, Frequency


def test_frequency_conversion() -> None:
    assert monthly_equivalent(Decimal("1.00"), Frequency.DAILY) == Decimal("30.42")
    assert monthly_equivalent(Decimal("1.00"), Frequency.WEEKLY) == Decimal("4.33")
    assert monthly_equivalent(Decimal("1.00"), Frequency.BIWEEKLY) == Decimal("2.17")
    assert monthly_equivalent(Decimal("1.00"), Frequency.MONTHLY) == Decimal("1.00")
    assert monthly_equivalent(Decimal("12.00"), Frequency.QUARTERLY) == Decimal("4.00")
    assert monthly_equivalent(Decimal("12.00"), Frequency.SEMIANNUAL) == Decimal("2.00")
    assert monthly_equivalent(Decimal("12.00"), Frequency.ANNUAL) == Decimal("1.00")


def test_monthly_and_yearly_totals() -> None:
    expenses = {
        "rent": ExpenseEntry(amount="1200.00", frequency="monthly"),
        "insurance": ExpenseEntry(amount="600.00", frequency="annual"),
        "gym": ExpenseEntry(amount="25.00", frequency="monthly"),
    }

    assert total_monthly(expenses) == Decimal("1275.00")
    assert total_yearly(expenses) == Decimal("15300.00")
