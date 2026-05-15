import json
from decimal import Decimal

import pytest

from recurring_expenses_tui.app import RecurringExpensesApp
from recurring_expenses_tui.models import ExpenseEntry
from recurring_expenses_tui.storage import StorageError, load_expenses, save_expenses


def test_load_missing_file_creates_empty_json(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_expenses()

    assert loaded == {}
    assert expenses_path.exists()
    assert json.loads(expenses_path.read_text(encoding="utf-8")) == {}


def test_json_load_save_behavior(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

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
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

    loaded = load_expenses()

    assert loaded["rent"].amount == Decimal("1200.00")
    assert loaded["internet"].amount == Decimal("49.99")
    assert loaded["internet"].frequency.value == "monthly"


def test_save_expenses_writes_json_with_at_most_two_decimal_places(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

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


def test_valid_json_load_save_roundtrip(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

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


def test_invalid_json_is_reported(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

    with pytest.raises(StorageError, match="Invalid JSON"):
        load_expenses()


def test_invalid_entry_is_reported(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text(
        json.dumps({"rent": {"amount": -5, "frequency": "monthly"}}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)

    with pytest.raises(StorageError, match="Invalid expense data"):
        load_expenses()


def test_app_load_state_handles_invalid_json_without_crashing(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    expenses_path.write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setattr("recurring_expenses_tui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("recurring_expenses_tui.app.get_expenses_path", lambda: expenses_path)

    app = RecurringExpensesApp()

    error = app.load_state()

    assert error is not None
    assert "Invalid JSON" in error
    assert app.expenses == {}
    assert app.last_error == error
