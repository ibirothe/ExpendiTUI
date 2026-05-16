from __future__ import annotations

import json

from expenditui.models import EntryType, FinancialEntry
from expenditui.settings_data import SettingsDataManager
from expenditui.tags import TagRegistry
from expenditui.theme import BUILTIN_THEME_ROWS, ThemeManager
from expenditui.visualization import (
    VisualizationConfig,
    VisualizationConfigManager,
)


class FakeApp:
    def __init__(self) -> None:
        self.expenses = {
            "Rent": FinancialEntry(
                amount="1200",
                frequency="monthly",
                tags=["Living"],
            )
        }
        self.income = {
            "Salary": FinancialEntry(
                amount="3200",
                frequency="monthly",
                tags=["Work"],
            )
        }
        self.tag_registry = TagRegistry(["Living", "Work", "Unused"])
        self.theme_manager = object()
        self.visualization_manager = object()
        self.last_error: str | None = None
        self.status_message: str | None = None
        self.status_message_kind = "foreground"
        self.refresh_calls: list[bool] = []
        self.apply_theme_calls = 0

    def set_entries(
        self, entry_type: EntryType, entries: dict[str, FinancialEntry]
    ) -> None:
        if entry_type is EntryType.EXPENSE:
            self.expenses = entries
        else:
            self.income = entries

    def refresh_views(self, *, sync_edit: bool = False) -> None:
        self.refresh_calls.append(sync_edit)

    def apply_theme(self, *, announce: bool = False) -> None:
        del announce
        self.apply_theme_calls += 1


def test_delete_financial_data_persists_empty_datasets(tmp_path, monkeypatch) -> None:
    expenses_path = tmp_path / "expenses.json"
    income_path = tmp_path / "income.json"
    monkeypatch.setattr("expenditui.storage.get_expenses_path", lambda: expenses_path)
    monkeypatch.setattr("expenditui.storage.get_income_path", lambda: income_path)

    app = FakeApp()

    SettingsDataManager(app).delete_financial_data()

    assert app.expenses == {}
    assert app.income == {}
    assert json.loads(expenses_path.read_text(encoding="utf-8")) == {}
    assert json.loads(income_path.read_text(encoding="utf-8")) == {}
    assert app.refresh_calls == [True]


def test_delete_recommended_tags_keeps_only_tags_used_by_entries(
    tmp_path, monkeypatch
) -> None:
    tags_path = tmp_path / "tags.json"
    monkeypatch.setattr("expenditui.storage.get_tags_path", lambda: tags_path)

    app = FakeApp()

    SettingsDataManager(app).delete_recommended_tags()

    assert app.tag_registry.to_list() == ["Living", "Work"]
    assert json.loads(tags_path.read_text(encoding="utf-8")) == ["Living", "Work"]
    assert app.refresh_calls == [False]


def test_delete_themes_resets_to_builtins_and_first_theme(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps(
            [
                [
                    "Custom",
                    "#101010",
                    "#EFEFEF",
                    "#202020",
                    "#3366FF",
                    "#22AA66",
                    "#DD9900",
                    "#CC3344",
                    "#888888",
                ]
            ]
        ),
        encoding="utf-8",
    )
    app = FakeApp()
    app.theme_manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    SettingsDataManager(app).delete_themes()

    assert not themes_path.exists()
    assert [theme.name for theme in app.theme_manager.themes] == [
        row[0] for row in BUILTIN_THEME_ROWS
    ]
    assert app.theme_manager.active_index == 0
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": BUILTIN_THEME_ROWS[0][0],
        "theme_index": 0,
    }
    assert app.apply_theme_calls == 1
    assert app.refresh_calls == [False]


def test_delete_visualizations_removes_file_and_uses_defaults(tmp_path) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text("{}", encoding="utf-8")
    app = FakeApp()
    app.visualization_manager = VisualizationConfigManager(path=config_path)

    SettingsDataManager(app).delete_visualizations()

    assert not config_path.exists()
    assert app.visualization_manager.config == VisualizationConfig.default()
    assert app.refresh_calls == [False]
