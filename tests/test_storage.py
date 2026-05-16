import json
from decimal import Decimal

import pytest

from expenditui.app import ExpendiTUIApp
from expenditui.constants import DEFAULT_TAGS
from expenditui.models import EntryType, ExpenseEntry
from expenditui.storage import (
    StorageError,
    load_entries,
    load_expenses,
    load_income,
    load_tag_registry,
    save_expenses,
    save_income,
    save_tag_registry,
)
from expenditui.tags import TagRegistry, normalize_tag_key, validate_tag


def test_load_missing_file_creates_empty_json(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_expenses()

    assert loaded == {}
    assert expenses_path.exists()
    assert json.loads(expenses_path.read_text(encoding="utf-8")) == {}


def test_missing_income_file_is_created(tmp_path, monkeypatch) -> None:
    income_path = tmp_path / "income.json"
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)

    loaded = load_income()

    assert loaded == {}
    assert income_path.exists()
    assert json.loads(income_path.read_text(encoding="utf-8")) == {}


def test_json_load_save_behavior(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    save_expenses(
        {
            "rent": ExpenseEntry(amount="1200.00", frequency="monthly"),
            "insurance": ExpenseEntry(amount="600.00", frequency="annual"),
        }
    )

    saved_text = expenses_path.read_text(encoding="utf-8")
    assert saved_text.startswith("{\n  ")
    loaded = load_expenses()
    assert loaded["rent"].amount == 1200
    assert loaded["insurance"].frequency.value == "annual"


def test_income_load_save_roundtrip_with_tags(tmp_path, monkeypatch) -> None:
    income_path = tmp_path / "income.json"
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)

    save_income(
        {
            "salary": ExpenseEntry(
                amount="3200.00",
                frequency="monthly",
                tags=["Work", "Salary"],
            )
        }
    )

    loaded = load_income()

    assert loaded["salary"].amount == Decimal("3200.00")
    assert loaded["salary"].tags == ["Work", "Salary"]


def test_load_expenses_reads_valid_json_file(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text(
        json.dumps(
            {
                "rent": {"amount": 1200, "frequency": "monthly"},
                "internet": {"amount": "49.99", "frequency": "monthly"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_expenses()

    assert loaded["rent"].amount == Decimal("1200.00")
    assert loaded["internet"].amount == Decimal("49.99")
    assert loaded["internet"].frequency.value == "monthly"


def test_save_expenses_writes_json_with_at_most_two_decimal_places(
    tmp_path, monkeypatch
) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    save_expenses(
        {
            "coffee": ExpenseEntry(amount="12.30", frequency="weekly"),
            "hosting": ExpenseEntry(amount="9", frequency="monthly"),
        }
    )

    saved_text = expenses_path.read_text(encoding="utf-8")
    saved = json.loads(saved_text)
    assert saved_text.endswith("\n")
    assert saved_text.startswith("{\n  ")
    assert saved["coffee"]["amount"] == 12.3
    assert saved["hosting"]["amount"] == 9
    assert "tags" not in saved["coffee"]


def test_valid_json_load_save_roundtrip(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    original = {
        "rent": ExpenseEntry(amount="1200.00", frequency="monthly"),
        "insurance": ExpenseEntry(amount="600.50", frequency="annual"),
    }

    save_expenses(original)
    loaded = load_expenses()
    save_expenses(loaded)
    reloaded = load_expenses()

    assert reloaded == loaded
    assert reloaded["insurance"].amount == Decimal("600.50")
    assert reloaded["insurance"].frequency.value == "annual"


def test_entry_order_roundtrips_through_storage(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    income_path = tmp_path / "income.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)

    save_expenses(
        {
            "insurance": ExpenseEntry(amount="600.00", frequency="annual"),
            "rent": ExpenseEntry(amount="1200.00", frequency="monthly"),
        }
    )
    save_income(
        {
            "bonus": ExpenseEntry(amount="500.00", frequency="annual"),
            "salary": ExpenseEntry(amount="3200.00", frequency="monthly"),
        }
    )

    assert list(load_expenses()) == ["insurance", "rent"]
    assert list(load_income()) == ["bonus", "salary"]


def test_invalid_json_is_reported(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    with pytest.raises(StorageError, match="Invalid JSON"):
        load_expenses()


def test_invalid_entries_are_skipped_with_diagnostics(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text(
        json.dumps(
            {
                "rent": {"amount": -5, "frequency": "monthly"},
                "valid": {"amount": 100, "frequency": "monthly"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_entries(EntryType.EXPENSE)

    assert list(loaded.entries) == ["valid"]
    assert len(loaded.diagnostics) == 1
    assert "Skipped 'rent'" in loaded.diagnostics[0]


def test_legacy_expense_rows_without_tags_still_load(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text(
        json.dumps({"rent": {"amount": 1200, "frequency": "monthly"}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_expenses()

    assert loaded["rent"].tags == []


def test_app_load_state_handles_invalid_json_without_crashing(
    tmp_path, monkeypatch
) -> None:
    expenses_path = tmp_path / "expenses.json"
    income_path = tmp_path / "income.json"
    tags_path = tmp_path / "tags.json"
    expenses_path.write_text("{ invalid json", encoding="utf-8")
    income_path.write_text(
        json.dumps({"salary": {"amount": 3200, "frequency": "monthly"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)
    monkeypatch.setattr("expenditui.app.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.app.get_income_path", lambda: income_path)

    app = ExpendiTUIApp()

    error = app.load_state()

    assert error is not None
    assert "Invalid JSON" in error
    assert app.expenses == {}
    assert list(app.income) == ["salary"]
    assert app.last_error == error


def test_missing_tags_file_recovers_with_defaults(tmp_path, monkeypatch) -> None:
    tags_path = tmp_path / "tags.json"
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    result = load_tag_registry()

    assert result.registry.to_list() == sorted(DEFAULT_TAGS, key=str.casefold)
    assert result.needs_save is True
    assert result.diagnostics == []


def test_default_tags_are_valid_and_unique() -> None:
    normalized_keys = [normalize_tag_key(validate_tag(tag)) for tag in DEFAULT_TAGS]

    assert len(normalized_keys) == len(set(normalized_keys))


def test_existing_tags_file_does_not_reseed_deleted_defaults(
    tmp_path, monkeypatch
) -> None:
    tags_path = tmp_path / "tags.json"
    tags_path.write_text(json.dumps(["Custom"], indent=2), encoding="utf-8")
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    result = load_tag_registry()

    assert result.registry.to_list() == ["Custom"]
    assert result.needs_save is False
    assert result.diagnostics == []


def test_existing_empty_tags_array_is_preserved(tmp_path, monkeypatch) -> None:
    tags_path = tmp_path / "tags.json"
    tags_path.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    result = load_tag_registry()

    assert result.registry.to_list() == []
    assert result.needs_save is False
    assert result.diagnostics == []


def test_app_load_state_creates_default_tags_on_first_startup(
    tmp_path, monkeypatch
) -> None:
    expenses_path = tmp_path / "expenses.json"
    income_path = tmp_path / "income.json"
    tags_path = tmp_path / "tags.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)
    monkeypatch.setattr("expenditui.app.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.app.get_income_path", lambda: income_path)

    app = ExpendiTUIApp()

    error = app.load_state()

    assert error is None
    assert tags_path.exists()
    assert json.loads(tags_path.read_text(encoding="utf-8")) == sorted(
        DEFAULT_TAGS,
        key=str.casefold,
    )


def test_malformed_tags_file_recovers_without_crashing(tmp_path, monkeypatch) -> None:
    tags_path = tmp_path / "tags.json"
    tags_path.write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    result = load_tag_registry()

    assert result.registry.to_list() == sorted(DEFAULT_TAGS, key=str.casefold)
    assert result.needs_save is True
    assert "Invalid JSON" in result.diagnostics[0]


def test_invalid_tags_are_skipped_and_duplicates_collapse(
    tmp_path, monkeypatch
) -> None:
    tags_path = tmp_path / "tags.json"
    tags_path.write_text(
        json.dumps(["Food", "food", "", 5, "Travel"], indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    result = load_tag_registry()

    assert "Food" in result.registry
    assert "Travel" in result.registry
    assert result.registry.canonicalize("food") == "Food"
    assert len(result.diagnostics) == 2
    assert result.needs_save is True


def test_save_tag_registry_writes_json_array_atomically(tmp_path, monkeypatch) -> None:
    tags_path = tmp_path / "tags.json"
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    save_tag_registry(TagRegistry(["Travel", "Food"]))

    saved_text = tags_path.read_text(encoding="utf-8")
    assert saved_text.endswith("\n")
    assert json.loads(saved_text) == ["Food", "Travel"]


def test_app_load_state_reconciles_entry_tags_into_registry(
    tmp_path, monkeypatch
) -> None:
    expenses_path = tmp_path / "expenses.json"
    income_path = tmp_path / "income.json"
    tags_path = tmp_path / "tags.json"
    expenses_path.write_text(
        json.dumps(
            {"rent": {"amount": 1200, "frequency": "monthly", "tags": ["Housing"]}},
            indent=2,
        ),
        encoding="utf-8",
    )
    income_path.write_text(
        json.dumps(
            {"salary": {"amount": 3200, "frequency": "monthly", "tags": ["Work"]}},
            indent=2,
        ),
        encoding="utf-8",
    )
    tags_path.write_text(json.dumps(["cash"], indent=2), encoding="utf-8")
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)
    monkeypatch.setattr("expenditui.app.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.app.get_income_path", lambda: income_path)

    app = ExpendiTUIApp()

    error = app.load_state()

    assert error is None
    assert app.get_tag_registry().canonicalize("housing") == "Housing"
    assert app.get_tag_registry().canonicalize("work") == "Work"
    assert json.loads(tags_path.read_text(encoding="utf-8")) == [
        "cash",
        "Housing",
        "Work",
    ]
