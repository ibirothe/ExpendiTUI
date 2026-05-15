from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

APP_NAME = "recurring-expenses-tui"
APP_TITLE = "Recurring Finance TUI"
EXPENSES_FILENAME = "expenses.json"
INCOME_FILENAME = "income.json"
EMPTY_JSON_OBJECT = "{}\n"
MONEY_PLACES = Decimal("0.01")
ROUNDING_MODE = ROUND_HALF_UP
DEFAULT_FREQUENCY = "monthly"
MAX_TAGS = 10
MAX_TAG_LENGTH = 32

FREQUENCY_VALUES = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
)
