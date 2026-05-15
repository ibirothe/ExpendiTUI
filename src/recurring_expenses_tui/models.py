from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Mapping

from pydantic import BaseModel, ConfigDict, RootModel, ValidationError, field_validator, model_validator

from .constants import FREQUENCY_VALUES, MONEY_PLACES, ROUNDING_MODE


class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class ExpenseEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal
    frequency: Frequency

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


class ExpenseCollection(RootModel[dict[str, ExpenseEntry]]):
    @model_validator(mode="after")
    def validate_names(self) -> "ExpenseCollection":
        normalized: dict[str, ExpenseEntry] = {}
        for raw_name, entry in self.root.items():
            if not isinstance(raw_name, str):
                raise ValueError("Expense names must be strings.")
            name = raw_name.strip()
            if not name:
                raise ValueError("Expense names must be non-empty strings.")
            if name in normalized:
                raise ValueError(f"Duplicate expense name: {name}")
            normalized[name] = entry
        self.root = normalized
        return self


def validate_expense_mapping(data: object) -> dict[str, ExpenseEntry]:
    return ExpenseCollection.model_validate(data).root


def dump_expense_mapping(data: Mapping[str, ExpenseEntry]) -> dict[str, dict[str, object]]:
    validated = validate_expense_mapping(dict(data))
    payload: dict[str, dict[str, object]] = {}
    for name, entry in validated.items():
        amount = entry.amount.quantize(MONEY_PLACES, rounding=ROUNDING_MODE)
        payload[name] = {
            "amount": int(amount) if amount == amount.to_integral() else float(amount),
            "frequency": entry.frequency.value,
        }
    return payload


__all__ = [
    "ExpenseCollection",
    "ExpenseEntry",
    "Frequency",
    "ValidationError",
    "dump_expense_mapping",
    "validate_expense_mapping",
]
