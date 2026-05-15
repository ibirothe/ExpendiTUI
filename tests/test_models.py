import pytest

from expenditui.constants import MAX_TAG_LENGTH, MAX_TAGS
from expenditui.models import ExpenseCollection, ExpenseEntry


def test_valid_model_parsing_with_tags() -> None:
    parsed = ExpenseCollection.model_validate(
        {
            "rent": {"amount": 1200.00, "frequency": "monthly"},
            "salary": {
                "amount": "3200.00",
                "frequency": "monthly",
                "tags": ["Work", "Salary"],
            },
        }
    )

    assert parsed.root["rent"].amount == 1200
    assert parsed.root["rent"].tags == []
    assert parsed.root["salary"].tags == ["Work", "Salary"]


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


def test_blank_and_excessive_tags_are_rejected() -> None:
    with pytest.raises(Exception):
        ExpenseEntry(amount="10.00", frequency="monthly", tags=["", "home"])

    with pytest.raises(Exception):
        ExpenseEntry(
            amount="10.00",
            frequency="monthly",
            tags=["x" * (MAX_TAG_LENGTH + 1)],
        )


def test_control_characters_and_excess_tag_count_are_rejected() -> None:
    with pytest.raises(Exception):
        ExpenseEntry(amount="10.00", frequency="monthly", tags=["Food\nTruck"])

    with pytest.raises(Exception):
        ExpenseEntry(
            amount="10.00",
            frequency="monthly",
            tags=[f"Tag {index}" for index in range(MAX_TAGS + 1)],
        )


def test_duplicate_tags_are_normalized() -> None:
    entry = ExpenseEntry(
        amount="10.00",
        frequency="monthly",
        tags=["Home", "home", " Bills "],
    )

    assert entry.tags == ["Home", "Bills"]
