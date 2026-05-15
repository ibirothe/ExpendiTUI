from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)

from .constants import (
    MAX_TAG_LENGTH,
    MAX_TAGS,
    MONEY_PLACES,
    ROUNDING_MODE,
)


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class EntryType(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"

    @property
    def display_name(self) -> str:
        return "Expense" if self is EntryType.EXPENSE else "Income"

    @property
    def plural_name(self) -> str:
        return "expenses" if self is EntryType.EXPENSE else "income"


class FinancialEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal
    frequency: Frequency
    tags: list[str] = Field(default_factory=list)

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int | str):
            try:
                return Decimal(str(value))
            except InvalidOperation as exc:
                raise ValueError("Amount must be a decimal number.") from exc
        if isinstance(value, float):
            try:
                return Decimal(str(value))
            except InvalidOperation as exc:
                raise ValueError("Amount must be a decimal number.") from exc
        raise ValueError("Amount must be a decimal number.")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        if value.is_nan() or value.is_infinite():
            raise ValueError("Amount must be a finite decimal number.")
        if value < 0:
            raise ValueError("Amount must be non-negative.")
        if value.as_tuple().exponent < -2:
            raise ValueError("Amount must use at most 2 decimal places.")
        return value.quantize(MONEY_PLACES, rounding=ROUNDING_MODE)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Tags must be a list.")

        normalized: list[str] = []
        seen: set[str] = set()
        for raw_tag in value:
            if not isinstance(raw_tag, str):
                raise ValueError("Each tag must be a string.")
            tag = raw_tag.strip()
            if not tag:
                raise ValueError("Tags must be non-empty strings.")
            if len(tag) > MAX_TAG_LENGTH:
                raise ValueError(
                    f"Tags must be at most {MAX_TAG_LENGTH} characters long."
                )
            tag_key = tag.casefold()
            if tag_key in seen:
                continue
            seen.add(tag_key)
            normalized.append(tag)

        if len(normalized) > MAX_TAGS:
            raise ValueError(f"Tags must contain at most {MAX_TAGS} values.")
        return normalized


ExpenseEntry = FinancialEntry
IncomeEntry = FinancialEntry


def normalize_entry_name(raw_name: object) -> str:
    if not isinstance(raw_name, str):
        raise ValueError("Entry names must be strings.")
    name = raw_name.strip()
    if not name:
        raise ValueError("Entry names must be non-empty strings.")
    return name


class FinancialEntryCollection(RootModel[dict[str, FinancialEntry]]):
    @model_validator(mode="after")
    def validate_names(self) -> "FinancialEntryCollection":
        normalized: dict[str, FinancialEntry] = {}
        for raw_name, entry in self.root.items():
            name = normalize_entry_name(raw_name)
            if name in normalized:
                raise ValueError(f"Duplicate entry name: {name}")
            normalized[name] = entry
        self.root = normalized
        return self


ExpenseCollection = FinancialEntryCollection
IncomeCollection = FinancialEntryCollection


def validate_financial_mapping(data: object) -> dict[str, FinancialEntry]:
    if not isinstance(data, Mapping):
        raise ValueError("Expected a JSON object mapping names to entries.")
    return FinancialEntryCollection.model_validate(data).root


def validate_expense_mapping(data: object) -> dict[str, ExpenseEntry]:
    return validate_financial_mapping(data)


def dump_financial_mapping(
    data: Mapping[str, FinancialEntry],
) -> dict[str, dict[str, object]]:
    validated = validate_financial_mapping(dict(data))
    payload: dict[str, dict[str, object]] = {}
    for name, entry in validated.items():
        amount = entry.amount.quantize(MONEY_PLACES, rounding=ROUNDING_MODE)
        serialized: dict[str, object] = {
            "amount": int(amount) if amount == amount.to_integral() else float(amount),
            "frequency": entry.frequency.value,
        }
        if entry.tags:
            serialized["tags"] = entry.tags
        payload[name] = serialized
    return payload


def dump_expense_mapping(
    data: Mapping[str, ExpenseEntry],
) -> dict[str, dict[str, object]]:
    return dump_financial_mapping(data)


__all__ = [
    "EntryType",
    "ExpenseCollection",
    "ExpenseEntry",
    "FinancialEntry",
    "FinancialEntryCollection",
    "Frequency",
    "IncomeCollection",
    "IncomeEntry",
    "ValidationError",
    "dump_expense_mapping",
    "dump_financial_mapping",
    "normalize_entry_name",
    "validate_expense_mapping",
    "validate_financial_mapping",
]
