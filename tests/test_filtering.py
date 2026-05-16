from __future__ import annotations

from decimal import Decimal

from expenditui.filtering import EntryFilterService
from expenditui.models import EntryType, FinancialEntry, Frequency


def make_entry(*, tags: list[str] | None = None) -> FinancialEntry:
    return FinancialEntry(
        amount=Decimal("10.00"),
        frequency=Frequency.MONTHLY,
        tags=tags or [],
    )


def row_keys(rows) -> list[tuple[EntryType, str]]:
    return [(row.entry_type, row.name) for row in rows]


def test_filter_returns_all_entries_for_empty_or_whitespace_query() -> None:
    service = EntryFilterService()
    expenses = {"Rent": make_entry(tags=["Housing"])}
    income = {"Salary": make_entry(tags=["Work"])}

    assert row_keys(
        service.filter_entries(expenses=expenses, income=income, query="")
    ) == [(EntryType.EXPENSE, "Rent"), (EntryType.INCOME, "Salary")]
    assert row_keys(
        service.filter_entries(expenses=expenses, income=income, query="   ")
    ) == [(EntryType.EXPENSE, "Rent"), (EntryType.INCOME, "Salary")]


def test_filter_matches_names_case_insensitively_with_partial_substrings() -> None:
    service = EntryFilterService()
    expenses = {
        "Grocery Shopping": make_entry(tags=["Food"]),
        "Rent": make_entry(tags=["Housing"]),
    }

    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="groc")
    ) == [(EntryType.EXPENSE, "Grocery Shopping")]
    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="RENT")
    ) == [(EntryType.EXPENSE, "Rent")]


def test_filter_matches_tags_case_insensitively_with_partial_substrings() -> None:
    service = EntryFilterService()
    expenses = {
        "Streaming": make_entry(tags=["Subscription", "Fun"]),
        "Grocery Shopping": make_entry(tags=["Food"]),
        "Rent": make_entry(tags=["Housing"]),
    }

    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="sub")
    ) == [(EntryType.EXPENSE, "Streaming")]
    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="FOOD")
    ) == [(EntryType.EXPENSE, "Grocery Shopping")]


def test_filter_handles_entries_without_tags_and_special_characters() -> None:
    service = EntryFilterService()
    expenses = {
        "Coffee": make_entry(),
        "Cafe Membership": make_entry(tags=["Cafe", "☕"]),
        "Build Tools": make_entry(tags=["dev/tools"]),
    }

    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="☕")
    ) == [(EntryType.EXPENSE, "Cafe Membership")]
    assert row_keys(
        service.filter_entries(expenses=expenses, income={}, query="/tools")
    ) == [(EntryType.EXPENSE, "Build Tools")]
    assert (
        row_keys(service.filter_entries(expenses=expenses, income={}, query="missing"))
        == []
    )
