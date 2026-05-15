from __future__ import annotations

import json
import logging

from recurring_expenses_tui.app import RecurringExpensesApp
from recurring_expenses_tui.theme import AppTheme, BUILTIN_THEME_ROWS, ThemeManager
from textual.css.stylesheet import Stylesheet


def build_theme_row(name: str, accent: str = "#3366FF") -> list[str]:
    return [
        name,
        "#101010",
        "#EFEFEF",
        "#202020",
        accent,
        "#22AA66",
        "#DD9900",
        "#CC3344",
        "#888888",
    ]


def test_theme_manager_loads_valid_rows_and_skips_invalid_rows(
    tmp_path, caplog
) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps(
            [
                build_theme_row("Alpha"),
                ["Broken", "#NOTHEX"],
                build_theme_row("Beta", accent="#6633FF"),
            ]
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    assert [theme.name for theme in manager.themes] == ["Alpha", "Beta"]
    assert "Skipping invalid theme definition" in caplog.text


def test_theme_manager_falls_back_to_built_in_defaults_when_file_is_missing(
    tmp_path,
) -> None:
    manager = ThemeManager(
        themes_path=tmp_path / "missing-themes.json",
        state_path=tmp_path / "ui-state.json",
    )

    assert [theme.name for theme in manager.themes] == [
        row[0] for row in BUILTIN_THEME_ROWS
    ]
    assert [theme.name for theme in manager.themes] == [
        "Dreamy",
        "Sandstone",
        "Nord",
    ]
    assert manager.active_index == 0


def test_theme_manager_prefers_persisted_name_over_index(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps([build_theme_row("Alpha"), build_theme_row("Beta")]),
        encoding="utf-8",
    )
    state_path.write_text(
        json.dumps({"theme_name": "Beta", "theme_index": 0}),
        encoding="utf-8",
    )

    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    assert manager.active_theme.name == "Beta"
    assert manager.active_index == 1


def test_theme_manager_resets_out_of_bounds_persisted_selection(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(json.dumps([build_theme_row("Only")]), encoding="utf-8")
    state_path.write_text(
        json.dumps({"theme_name": "Missing", "theme_index": 99}),
        encoding="utf-8",
    )

    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    assert manager.active_index == 0
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": "Only",
        "theme_index": 0,
    }


def test_cycle_next_wraps_and_persists_selection(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps([build_theme_row("Alpha"), build_theme_row("Beta")]),
        encoding="utf-8",
    )
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    manager.cycle_next()
    assert manager.active_theme.name == "Beta"
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": "Beta",
        "theme_index": 1,
    }

    manager.cycle_next()
    assert manager.active_theme.name == "Alpha"


def test_theme_blend_returns_stable_hex_color() -> None:
    theme = AppTheme.from_row(build_theme_row("Blend"), source="test")

    blended = theme.blend("accent", "background", 0.5)

    assert blended.startswith("#")
    assert len(blended) == 7


def test_app_build_theme_css_covers_component_styles() -> None:
    app = RecurringExpensesApp()

    css = app._build_theme_css(app.active_theme)

    assert "FooterKey > .footer-key--key" in css
    assert "Input > .input--selection" in css
    assert "DataTable > .datatable--header-cursor" in css
    assert "Underline > .underline--bar" in css


def test_app_build_theme_css_parses_with_textual() -> None:
    app = RecurringExpensesApp()
    stylesheet = Stylesheet()
    stylesheet.add_source(
        app._build_theme_css(app.active_theme), read_from=("test.css", "theme")
    )

    stylesheet.parse()
