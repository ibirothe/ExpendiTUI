from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

APP_NAME = "recurring-expenses-tui"
APP_TITLE = "Recurring Expenses TUI"
DEFAULT_FILENAME = "expenses.json"
EMPTY_JSON_OBJECT = "{}\n"
MONEY_PLACES = Decimal("0.01")
ROUNDING_MODE = ROUND_HALF_UP
DEFAULT_FREQUENCY = "monthly"

FREQUENCY_VALUES = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
)
