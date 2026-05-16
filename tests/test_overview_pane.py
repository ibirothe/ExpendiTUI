from __future__ import annotations

import asyncio
import inspect
from decimal import Decimal

from textual.widgets import DataTable, Input

from expenditui.app import EDIT_TAB, ExpendiTUIApp
from expenditui.models import EntryType, FinancialEntry, Frequency
from expenditui.screens.edit import EditPane
from expenditui.screens.overview import NO_MATCHING_ENTRIES_MESSAGE, OverviewPane
from expenditui.visualization import VisualizationConfig


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


def test_overview_search_filters_rows_and_renders_no_results() -> None:
    async def run() -> None:
        app = ExpendiTUIApp()
        app.load_state = lambda: None  # type: ignore[method-assign]

        async with app.run_test(size=(120, 30)):
            app.expenses = {
                "Grocery Shopping": FinancialEntry(
                    amount=Decimal("75.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Food"],
                ),
                "Streaming": FinancialEntry(
                    amount=Decimal("12.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Subscription"],
                ),
            }
            app.income = {
                "Salary": FinancialEntry(
                    amount=Decimal("1000.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Work"],
                )
            }
            overview = app.query_one(OverviewPane)
            search = overview.query_one("#overview-search", Input)
            table = overview.query_one("#overview-table", DataTable)

            overview.refresh_view()
            assert table.row_count == 3

            overview.on_input_changed(Input.Changed(search, "food"))
            assert table.row_count == 1
            assert table.get_row_at(0)[1] == "Grocery Shopping"

            overview.on_input_changed(Input.Changed(search, "sub"))
            assert table.row_count == 1
            assert table.get_row_at(0)[1] == "Streaming"

            overview.on_input_changed(Input.Changed(search, "missing"))
            assert table.row_count == 1
            assert table.get_row_at(0)[0] == NO_MATCHING_ENTRIES_MESSAGE

            overview.on_input_changed(Input.Changed(search, "   "))
            assert table.row_count == 3

    asyncio.run(run())


def test_overview_search_shortcut_and_escape_focus_behavior() -> None:
    async def run() -> None:
        app = ExpendiTUIApp()
        app.load_state = lambda: None  # type: ignore[method-assign]

        async with app.run_test(size=(120, 30)) as pilot:
            overview = app.query_one(OverviewPane)
            search = overview.query_one("#overview-search", Input)
            table = overview.query_one("#overview-table", DataTable)

            assert search.has_class("hidden")

            await pilot.press("/")
            assert app.focused is search
            assert not search.has_class("hidden")

            overview.on_input_changed(Input.Changed(search, "missing"))
            assert table.row_count == 1
            assert table.get_row_at(0)[0] == NO_MATCHING_ENTRIES_MESSAGE

            await pilot.press("escape")
            assert app.focused is table
            assert search.has_class("hidden")
            assert search.value == ""
            assert overview.search_query == ""

    asyncio.run(run())


def test_overview_selection_clamps_when_filter_hides_selected_row() -> None:
    async def run() -> None:
        app = ExpendiTUIApp()
        app.load_state = lambda: None  # type: ignore[method-assign]

        async with app.run_test(size=(120, 30)):
            app.expenses = {
                "Rent": FinancialEntry(
                    amount=Decimal("900.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Housing"],
                ),
                "Streaming": FinancialEntry(
                    amount=Decimal("12.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Subscription"],
                ),
            }
            app.income = {}
            overview = app.query_one(OverviewPane)
            search = overview.query_one("#overview-search", Input)
            table = overview.query_one("#overview-table", DataTable)

            overview.refresh_view()
            table.move_cursor(row=1, column=0, animate=False)
            overview.selected_row_identity = (
                overview.visible_entries[1].entry_type,
                "Streaming",
            )

            overview.on_input_changed(Input.Changed(search, "rent"))

            assert table.row_count == 1
            assert table.cursor_row == 0
            assert table.get_row_at(0)[1] == "Rent"

    asyncio.run(run())


def test_enter_on_overview_row_opens_matching_edit_row() -> None:
    async def run() -> None:
        app = ExpendiTUIApp()
        app.load_state = lambda: None  # type: ignore[method-assign]

        async with app.run_test(size=(120, 30)) as pilot:
            app.expenses = {}
            app.income = {
                "Salary": FinancialEntry(
                    amount=Decimal("1000.00"),
                    frequency=Frequency.MONTHLY,
                    tags=["Work"],
                )
            }
            overview = app.query_one(OverviewPane)
            table = overview.query_one("#overview-table", DataTable)

            overview.refresh_view()
            table.focus()
            await pilot.press("enter")

            edit = app.query_one(EditPane)
            assert app.active_tab_id == EDIT_TAB
            assert edit.active_dataset is EntryType.INCOME
            assert edit.selected_name == "Salary"

    asyncio.run(run())


def test_overview_layout_keeps_summary_and_visualization_visible_when_height_is_tight() -> (
    None
):
    async def run() -> None:
        app = ExpendiTUIApp()
        app.visualization_manager.config = VisualizationConfig.default()
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


def test_overview_layout_hides_visualization_section_when_config_is_disabled() -> None:
    async def run() -> None:
        app = ExpendiTUIApp()
        app.visualization_manager.config = VisualizationConfig.disabled()

        async with app.run_test(size=(100, 20)):
            overview = app.query_one(OverviewPane)
            totals_section = overview.query_one("#overview-totals-section")
            visualization_section = overview.query_one(
                "#overview-visualization-section"
            )
            table = overview.query_one("#overview-table")

            assert totals_section.size.height > 0
            assert visualization_section.display is False
            assert table.size.height > 0

    asyncio.run(run())


def test_overview_layout_places_summary_sections_before_scrollable_table() -> None:
    compose_source = inspect.getsource(OverviewPane.compose)
    mount_source = inspect.getsource(OverviewPane.on_mount)
    theme_source = inspect.getsource(OverviewPane.apply_theme)

    totals_index = compose_source.index("overview-totals-section")
    visualization_index = compose_source.index("overview-visualization-section")
    search_index = compose_source.index("overview-search")
    table_index = compose_source.index('DataTable(id="overview-table")')

    assert totals_index < visualization_index < search_index < table_index
    assert ".overview-section" in OverviewPane.DEFAULT_CSS
    assert "min-height: 3;" in OverviewPane.DEFAULT_CSS
    assert "#overview-search" in OverviewPane.DEFAULT_CSS
    assert "#overview-table" in OverviewPane.DEFAULT_CSS
    assert '"Tags"' in mount_source
    assert "height: 1fr;" in OverviewPane.DEFAULT_CSS
    assert "min-height: 0;" in OverviewPane.DEFAULT_CSS
    assert 'theme.blend("warning", "surface", 0.18)' in theme_source
    assert 'theme.blend("accent", "surface", 0.18)' in theme_source
    assert 'styles.border = ("round", theme.warning)' in theme_source
    assert 'styles.border = ("round", theme.accent)' in theme_source
