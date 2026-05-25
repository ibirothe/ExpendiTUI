from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

APP_NAME = "expenditui"
APP_TITLE = "ExpendiTUI"
EXPENSES_FILENAME = "expenses.json"
INCOME_FILENAME = "income.json"
TAGS_FILENAME = "tags.json"
EMPTY_JSON_OBJECT = "{}\n"
MONEY_PLACES = Decimal("0.01")
ROUNDING_MODE = ROUND_HALF_UP
DEFAULT_FREQUENCY = "monthly"
DEFAULT_TAGS = (
    "Subscription",
    "Media",
    "Sports",
    "Living",
    "Rent",
    "Utilities",
    "Food",
    "Groceries",
    "Restaurant",
    "Transport",
    "Travel",
    "Insurance",
    "Health",
    "Medical",
    "Fitness",
    "Education",
    "Work",
    "Salary",
    "Investment",
    "Savings",
    "Shopping",
    "Clothing",
    "Entertainment",
    "Gaming",
    "Family",
    "Pets",
    "Phone",
    "Internet",
    "Taxes",
    "Gifts",
    "Vacation",
    "Emergency",
    "Misc",
)
MAX_TAGS = 64
MAX_TAG_LENGTH = 64

FREQUENCY_VALUES = (
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
)
