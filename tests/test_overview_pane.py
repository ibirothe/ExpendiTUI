from __future__ import annotations

import asyncio
import inspect
from decimal import Decimal

from expenditui.app import ExpendiTUIApp
from expenditui.models import FinancialEntry, Frequency
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


def test_overview_layout_keeps_summary_and_visualization_visible_when_height_is_tight() -> (
    None
):
    async def run() -> None:
        app = ExpendiTUIApp()
        app.expenses = {
            f"expense-{index}": FinancialEntry(
                amount=Decimal("10.00"),
                frequency=Frequency.MONTHLY,
                tags=[],
            )
            for index in range(20)
        }
        app.income = {
            "salary": FinancialEntry(
                amount=Decimal("1000.00"),
                frequency=Frequency.MONTHLY,
                tags=[],
            )
        }

        async with app.run_test(size=(100, 20)):
            overview = app.query_one(OverviewPane)
            totals_section = overview.query_one("#overview-totals-section")
            visualization_section = overview.query_one(
                "#overview-visualization-section"
            )
            table = overview.query_one("#overview-table")

            assert totals_section.size.height > 0
            assert totals_section.size.height == totals_section.virtual_size.height
            assert visualization_section.size.height > 0
            assert (
                visualization_section.size.height
                == visualization_section.virtual_size.height
            )
            assert table.size.height < table.virtual_size.height
            assert (
                table.size.height
                < totals_section.size.height + visualization_section.size.height
            )

    asyncio.run(run())


def test_overview_layout_places_summary_sections_before_scrollable_table() -> None:
    compose_source = inspect.getsource(OverviewPane.compose)
    theme_source = inspect.getsource(OverviewPane.apply_theme)

    totals_index = compose_source.index("overview-totals-section")
    visualization_index = compose_source.index("overview-visualization-section")
    table_index = compose_source.index('DataTable(id="overview-table")')

    assert totals_index < visualization_index < table_index
    assert ".overview-section" in OverviewPane.DEFAULT_CSS
    assert "min-height: 3;" in OverviewPane.DEFAULT_CSS
    assert "#overview-table" in OverviewPane.DEFAULT_CSS
    assert "height: 1fr;" in OverviewPane.DEFAULT_CSS
    assert "min-height: 0;" in OverviewPane.DEFAULT_CSS
    assert 'theme.blend("warning", "surface", 0.18)' in theme_source
    assert 'theme.blend("accent", "surface", 0.18)' in theme_source
    assert 'styles.border = ("round", theme.warning)' in theme_source
    assert 'styles.border = ("round", theme.accent)' in theme_source
