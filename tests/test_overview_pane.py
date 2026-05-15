from __future__ import annotations

import inspect

from expenditui.screens.overview import OverviewPane


def test_page_actions_target_overview_table(monkeypatch) -> None:
    pane = OverviewPane()
    calls: list[str] = []

    class FakeTable:
        def action_page_up(self) -> None:
            calls.append("up")

        def action_page_down(self) -> None:
            calls.append("down")

    monkeypatch.setattr(pane, "query_one", lambda selector, *_args: FakeTable())

    pane.page_up()
    pane.page_down()

    assert calls == ["up", "down"]


def test_overview_layout_places_summary_sections_before_scrollable_table() -> None:
    compose_source = inspect.getsource(OverviewPane.compose)
    theme_source = inspect.getsource(OverviewPane.apply_theme)

    totals_index = compose_source.index("overview-totals-section")
    visualization_index = compose_source.index("overview-visualization-section")
    table_index = compose_source.index('DataTable(id="overview-table")')

    assert totals_index < visualization_index < table_index
    assert ".overview-section" in OverviewPane.CSS
    assert "min-height: 3;" in OverviewPane.CSS
    assert "#overview-table" in OverviewPane.CSS
    assert "height: 1fr;" in OverviewPane.CSS
    assert "min-height: 0;" in OverviewPane.CSS
    assert 'theme.blend("warning", "surface", 0.18)' in theme_source
    assert 'theme.blend("accent", "surface", 0.18)' in theme_source
    assert 'styles.border = ("round", theme.warning)' in theme_source
    assert 'styles.border = ("round", theme.accent)' in theme_source
