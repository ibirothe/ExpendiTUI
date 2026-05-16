from __future__ import annotations

from enum import Enum

from rich.console import Group
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Input, Static

from ..calculations import (
    monthly_equivalent,
    savings_monthly,
    savings_yearly,
    total_monthly,
    total_yearly,
    yearly_equivalent,
)
from ..filtering import EntryFilterService, FilteredEntry
from ..models import EntryType
from ..theme import AppTheme

NO_MATCHING_ENTRIES_MESSAGE = "No matching entries found."
ENTRY_TYPE_SORT_ORDER = {EntryType.EXPENSE: 0, EntryType.INCOME: 1}


def format_money(value) -> str:
    return f"{value:.2f}"


class OverviewSortMode(str, Enum):
    ORIGINAL = "original"
    PRIMARY_TAG = "primary_tag"
    ANNUALIZED_COST = "annualized_cost"
    ALPHABETICAL = "alphabetical"

    @property
    def display_name(self) -> str:
        return {
            OverviewSortMode.ORIGINAL: "Original",
            OverviewSortMode.PRIMARY_TAG: "Primary Tag",
            OverviewSortMode.ANNUALIZED_COST: "Annualized Cost",
            OverviewSortMode.ALPHABETICAL: "Alphabetical",
        }[self]


SORT_MODE_SEQUENCE = (
    OverviewSortMode.ORIGINAL,
    OverviewSortMode.PRIMARY_TAG,
    OverviewSortMode.ANNUALIZED_COST,
    OverviewSortMode.ALPHABETICAL,
)


class OverviewPane(Vertical):
    DEFAULT_CSS = """
    OverviewPane {
        height: 1fr;
        min-height: 0;
    }

    #overview-title {
        content-align: center middle;
        height: 3;
        text-style: bold;
    }

    .overview-section {
        height: auto;
        margin: 1 2 0 2;
        padding: 0;
        min-height: 3;
    }

    #overview-totals-section {
        margin-top: 1;
    }

    #overview-visualization-section,
    #overview-totals-section {
        height: auto;
    }

    #overview-visualization {
        height: auto;
        padding: 1 2;
    }

    #overview-totals {
        height: auto;
        padding: 1 2 0 2;
    }

    #overview-search {
        height: 3;
        margin: 1 2 0 2;
    }

    .hidden {
        display: none;
    }

    #overview-table {
        height: 1fr;
        min-height: 0;
        margin: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="overview-totals-section", classes="overview-section"):
            yield Static(id="overview-totals")
        with Vertical(id="overview-visualization-section", classes="overview-section"):
            yield Static(id="overview-visualization")
        yield Input(
            placeholder="Search entries or tags",
            id="overview-search",
            classes="hidden",
        )
        yield DataTable(id="overview-table")

    def __init__(self) -> None:
        super().__init__()
        self.search_query = ""
        self.search_visible = False
        self.filter_service = EntryFilterService()
        self.visible_entries: list[FilteredEntry] = []
        self.selected_row_identity: tuple[EntryType, str] | None = None
        self.sort_mode = OverviewSortMode.ORIGINAL

    def on_mount(self) -> None:
        table = self.query_one("#overview-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "Type",
            "Name",
            "Amount",
            "Frequency",
            "Monthly Equivalent",
            "Yearly Equivalent",
            "Tags",
        )
        self.refresh_view()

    def on_screen_resume(self) -> None:
        self.refresh_view()

    def apply_theme(self, theme: AppTheme) -> None:
        totals_background = theme.blend("warning", "surface", 0.18)
        visualization_background = theme.blend("accent", "surface", 0.18)
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        totals_section = self.query_one("#overview-totals-section", Vertical)
        totals_section.set_styles(
            background=totals_background,
            color=theme.foreground,
        )
        totals_section.styles.border = ("round", theme.warning)
        visualization_section = self.query_one(
            "#overview-visualization-section", Vertical
        )
        visualization_section.set_styles(
            background=visualization_background,
            color=theme.foreground,
        )
        visualization_section.styles.border = ("round", theme.accent)
        self.query_one("#overview-table", DataTable).set_styles(
            background=theme.surface,
            color=theme.foreground,
        )
        self.query_one("#overview-search", Input).set_styles(
            background=theme.surface,
            color=theme.foreground,
        )
        self.query_one("#overview-visualization", Static).set_styles(
            background=visualization_background,
            color=theme.foreground,
        )
        self.query_one("#overview-totals", Static).set_styles(
            background=totals_background,
            color=theme.foreground,
        )
        self.refresh_view()

    def on_resize(self, event: events.Resize) -> None:
        del event
        self._refresh_visualization()

    def refresh_view(self) -> None:
        table = self.query_one("#overview-table", DataTable)
        previous_identity = self.selected_row_identity or self._cursor_identity()
        table.clear(columns=False)

        expenses = self.app.expenses
        income = self.app.income
        self.visible_entries = self.filter_service.filter_entries(
            expenses=expenses,
            income=income,
            query=self.search_query,
        )
        self.visible_entries = self._sort_entries(self.visible_entries)
        for index, row in enumerate(self.visible_entries):
            entry = row.entry
            table.add_row(
                row.entry_type.display_name,
                row.name,
                format_money(entry.amount),
                entry.frequency.value,
                format_money(monthly_equivalent(entry.amount, entry.frequency)),
                format_money(yearly_equivalent(entry.amount, entry.frequency)),
                ", ".join(entry.tags),
                key=f"row-{index}",
            )
        if not self.visible_entries and self.filter_service.normalize_query(
            self.search_query
        ):
            table.add_row(
                NO_MATCHING_ENTRIES_MESSAGE,
                "",
                "",
                "",
                "",
                "",
                "",
                key="no-results",
            )
        self._restore_table_selection(previous_identity)

        monthly_expenses = total_monthly(expenses)
        yearly_expenses = total_yearly(expenses)
        monthly_income = total_monthly(income)
        yearly_income = total_yearly(income)
        monthly_savings = savings_monthly(income, expenses)
        yearly_savings = savings_yearly(income, expenses)
        self._refresh_visualization()
        totals = Text()
        totals.append(
            f"Monthly expenses: {format_money(monthly_expenses)}\n",
            style=self.app.theme_rich_style("warning", bold=True),
        )
        totals.append(
            f"Monthly income: {format_money(monthly_income)}\n",
            style=self.app.theme_rich_style("success", bold=True),
        )
        totals.append(
            f"Monthly savings: {format_money(monthly_savings)}\n",
            style=self.app.theme_rich_style("accent", bold=True),
        )
        totals.append(
            f"Yearly expenses: {format_money(yearly_expenses)}\n",
            style=self.app.theme_rich_style("warning", bold=True),
        )
        totals.append(
            f"Yearly income: {format_money(yearly_income)}\n",
            style=self.app.theme_rich_style("success", bold=True),
        )
        totals.append(
            f"Yearly savings: {format_money(yearly_savings)}",
            style=self.app.theme_rich_style("accent", bold=True),
        )
        self.query_one("#overview-totals", Static).update(totals)

    def focus_search(self) -> None:
        self.show_search()
        search = self.query_one("#overview-search", Input)
        search.focus()

    @property
    def search_has_focus(self) -> bool:
        return self.app.focused is self.query_one("#overview-search", Input)

    @property
    def selected_entry_identity(self) -> tuple[EntryType, str] | None:
        return self.selected_row_identity or self._cursor_identity()

    def focus_table(self) -> None:
        table = self.query_one("#overview-table", DataTable)
        table.focus()

    def show_search(self) -> None:
        self.search_visible = True
        self.query_one("#overview-search", Input).set_class(False, "hidden")

    def hide_search(self, *, clear: bool = True, focus_table: bool = True) -> None:
        search = self.query_one("#overview-search", Input)
        self.search_visible = False
        search.set_class(True, "hidden")
        if clear:
            self.search_query = ""
            search.value = ""
            self.refresh_view()
        if focus_table:
            self.focus_table()

    def page_up(self) -> None:
        self.query_one("#overview-table", DataTable).action_page_up()

    def page_down(self) -> None:
        self.query_one("#overview-table", DataTable).action_page_down()

    def toggle_sort_mode(self) -> None:
        current_index = SORT_MODE_SEQUENCE.index(self.sort_mode)
        next_index = (current_index + 1) % len(SORT_MODE_SEQUENCE)
        self.sort_mode = SORT_MODE_SEQUENCE[next_index]
        self.refresh_view()
        self.app.refresh_message_area()

    @property
    def sort_status_label(self) -> str:
        return f"Sort: {self.sort_mode.display_name}"

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "overview-search":
            return
        self.search_query = event.value
        self.refresh_view()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._set_selected_identity_from_event(event.row_key)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._set_selected_identity_from_event(event.row_key)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape" and self.search_has_focus:
            event.stop()
            event.prevent_default()
            self.hide_search()
            return
        if event.key == "enter" and not self.search_has_focus:
            event.stop()
            event.prevent_default()
            self.app.open_overview_selection_in_edit()

    def _refresh_visualization(self) -> None:
        section = self.query_one("#overview-visualization-section", Vertical)
        widget = self.query_one("#overview-visualization", Static)
        available_width = widget.size.width or self.size.width or self.app.size.width
        result = self.app.render_overview_visualization(available_width)

        lines = [*result.lines, *result.legend]
        if not lines:
            section.display = False
            widget.update("")
            return
        section.display = True
        widget.update(Group(*lines))

    def _cursor_identity(self) -> tuple[EntryType, str] | None:
        table = self.query_one("#overview-table", DataTable)
        cursor_row = table.cursor_row
        if 0 <= cursor_row < len(self.visible_entries):
            row = self.visible_entries[cursor_row]
            return (row.entry_type, row.name)
        return None

    def _sort_entries(self, rows: list[FilteredEntry]) -> list[FilteredEntry]:
        if self.sort_mode is OverviewSortMode.ORIGINAL:
            return rows
        if self.sort_mode is OverviewSortMode.PRIMARY_TAG:
            return sorted(
                rows,
                key=lambda row: (
                    row.entry.tags[0].casefold() if row.entry.tags else "\U0010ffff",
                    row.name.casefold(),
                    ENTRY_TYPE_SORT_ORDER[row.entry_type],
                ),
            )
        if self.sort_mode is OverviewSortMode.ANNUALIZED_COST:
            return sorted(
                rows,
                key=lambda row: (
                    -yearly_equivalent(row.entry.amount, row.entry.frequency),
                    row.name.casefold(),
                    ENTRY_TYPE_SORT_ORDER[row.entry_type],
                ),
            )
        return sorted(
            rows,
            key=lambda row: (
                row.name.casefold(),
                ENTRY_TYPE_SORT_ORDER[row.entry_type],
            ),
        )

    def _restore_table_selection(
        self, previous_identity: tuple[EntryType, str] | None
    ) -> None:
        table = self.query_one("#overview-table", DataTable)
        if not self.visible_entries:
            self.selected_row_identity = None
            return

        target_index = 0
        if previous_identity is not None:
            for index, row in enumerate(self.visible_entries):
                if (row.entry_type, row.name) == previous_identity:
                    target_index = index
                    break

        table.move_cursor(row=target_index, column=0, animate=False)
        row = self.visible_entries[target_index]
        self.selected_row_identity = (row.entry_type, row.name)

    def _set_selected_identity_from_event(self, row_key: object) -> None:
        value = getattr(row_key, "value", row_key)
        if value is None or value == "no-results":
            self.selected_row_identity = None
            return
        try:
            index = int(str(value).removeprefix("row-"))
        except ValueError:
            return
        if 0 <= index < len(self.visible_entries):
            row = self.visible_entries[index]
            self.selected_row_identity = (row.entry_type, row.name)
