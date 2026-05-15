import pytest

from recurring_expenses_tui.models import ExpenseCollection, ExpenseEntry


def test_valid_model_parsing() -> None:
    parsed = ExpenseCollection.model_validate(
        {
            "rent": {"amount": 1200.00, "frequency": "monthly"},
            "insurance": {"amount": "600.00", "frequency": "annual"},
        }
    )

    assert parsed.root["rent"].amount == 1200
    assert parsed.root["insurance"].frequency.value == "annual"


def test_invalid_amount_rejection() -> None:
    with pytest.raises(Exception):
        ExpenseEntry(amount="-1.00", frequency="monthly")

    with pytest.raises(Exception):
        ExpenseEntry(amount="1.999", frequency="monthly")


def test_invalid_frequency_rejection() -> None:
    with pytest.raises(Exception):
        ExpenseEntry(amount="10.00", frequency="yearly")


def test_blank_name_rejection() -> None:
    with pytest.raises(Exception):
        ExpenseCollection.model_validate(
            {"   ": {"amount": "10.00", "frequency": "monthly"}}
        )
