from __future__ import annotations

import json
import logging

from expenditui.app import ExpendiTUIApp
import pytest

from expenditui.theme import (
    AppTheme,
    BUILTIN_THEME_ROWS,
    MAX_THEME_NAME_LENGTH,
    THEME_SLOT_NAMES,
    ThemeManager,
)
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


def build_theme_colors(accent: str = "#3366FF") -> list[str]:
    return build_theme_row("Draft", accent=accent)[1:]


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


def test_create_theme_persists_and_activates_new_theme(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(json.dumps([build_theme_row("Alpha")]), encoding="utf-8")
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    theme = manager.create_theme(
        "  Ocean Dark  ",
        [color.lower() for color in build_theme_colors(accent="#2EC4B6")],
    )

    assert theme.name == "Ocean Dark"
    assert manager.active_theme.name == "Ocean Dark"
    assert json.loads(themes_path.read_text(encoding="utf-8")) == [
        build_theme_row("Alpha"),
        build_theme_row("Ocean Dark", accent="#2EC4B6"),
    ]
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": "Ocean Dark",
        "theme_index": 1,
    }


def test_first_theme_mutation_materializes_built_in_themes(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    manager.create_theme("Custom", build_theme_colors(), activate=False)

    persisted = json.loads(themes_path.read_text(encoding="utf-8"))
    assert [row[0] for row in persisted] == [
        *(row[0] for row in BUILTIN_THEME_ROWS),
        "Custom",
    ]
    assert manager.active_theme.name == "Dreamy"


def test_update_theme_validates_persists_and_refreshes_active_name(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps([build_theme_row("Alpha"), build_theme_row("Beta")]),
        encoding="utf-8",
    )
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)
    manager.set_active(1)

    manager.update_theme(1, "Beta Prime", build_theme_colors(accent="#112233"))

    assert manager.active_theme.name == "Beta Prime"
    assert manager.active_theme.accent == "#112233"
    assert json.loads(themes_path.read_text(encoding="utf-8"))[1] == build_theme_row(
        "Beta Prime", accent="#112233"
    )
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": "Beta Prime",
        "theme_index": 1,
    }


def test_delete_active_theme_selects_next_available_theme(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps(
            [
                build_theme_row("Alpha"),
                build_theme_row("Beta"),
                build_theme_row("Gamma"),
            ]
        ),
        encoding="utf-8",
    )
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)
    manager.set_active(1)

    removed = manager.delete_theme(1)

    assert removed.name == "Beta"
    assert [theme.name for theme in manager.themes] == ["Alpha", "Gamma"]
    assert manager.active_theme.name == "Gamma"
    assert json.loads(state_path.read_text(encoding="utf-8")) == {
        "theme_name": "Gamma",
        "theme_index": 1,
    }


def test_delete_theme_before_active_preserves_active_theme_name(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(
        json.dumps(
            [
                build_theme_row("Alpha"),
                build_theme_row("Beta"),
                build_theme_row("Gamma"),
            ]
        ),
        encoding="utf-8",
    )
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)
    manager.set_active(2)

    manager.delete_theme(0)

    assert [theme.name for theme in manager.themes] == ["Beta", "Gamma"]
    assert manager.active_theme.name == "Gamma"
    assert manager.active_index == 1


def test_delete_theme_rejects_final_remaining_theme(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(json.dumps([build_theme_row("Only")]), encoding="utf-8")
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    with pytest.raises(ValueError, match="At least one theme"):
        manager.delete_theme(0)

    assert [theme.name for theme in manager.themes] == ["Only"]
    assert json.loads(themes_path.read_text(encoding="utf-8")) == [
        build_theme_row("Only")
    ]


def test_theme_crud_rejects_duplicate_names_case_insensitively(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(json.dumps([build_theme_row("Alpha")]), encoding="utf-8")
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    with pytest.raises(ValueError, match="already exists"):
        manager.create_theme(" alpha ", build_theme_colors())


def test_theme_crud_rejects_invalid_names_and_form_colors(tmp_path) -> None:
    themes_path = tmp_path / "themes.json"
    state_path = tmp_path / "ui-state.json"
    themes_path.write_text(json.dumps([build_theme_row("Alpha")]), encoding="utf-8")
    manager = ThemeManager(themes_path=themes_path, state_path=state_path)

    with pytest.raises(ValueError, match="required"):
        manager.create_theme("   ", build_theme_colors())

    with pytest.raises(ValueError, match=f"{MAX_THEME_NAME_LENGTH} characters"):
        manager.create_theme("x" * (MAX_THEME_NAME_LENGTH + 1), build_theme_colors())

    invalid_colors = build_theme_colors()
    invalid_colors[THEME_SLOT_NAMES.index("accent")] = "#ABC"
    with pytest.raises(ValueError, match="Accent must be a #RRGGBB hex color"):
        manager.create_theme("Short Hex", invalid_colors)

    invalid_colors = build_theme_colors()
    invalid_colors[THEME_SLOT_NAMES.index("error")] = "#GGGGGG"
    with pytest.raises(ValueError, match="Error must be a #RRGGBB hex color"):
        manager.create_theme("Bad Hex", invalid_colors)


def test_theme_blend_returns_stable_hex_color() -> None:
    theme = AppTheme.from_row(build_theme_row("Blend"), source="test")

    blended = theme.blend("accent", "background", 0.5)

    assert blended.startswith("#")
    assert len(blended) == 7


def test_app_build_theme_css_covers_component_styles() -> None:
    app = ExpendiTUIApp()

    css = app._build_theme_css(app.active_theme)

    assert "FooterKey > .footer-key--key" in css
    assert "Input > .input--selection" in css
    assert "DataTable > .datatable--header-cursor" in css
    assert "Underline > .underline--bar" in css


def test_app_build_theme_css_parses_with_textual() -> None:
    app = ExpendiTUIApp()
    stylesheet = Stylesheet()
    stylesheet.add_source(
        app._build_theme_css(app.active_theme), read_from=("test.css", "theme")
    )

    stylesheet.parse()
