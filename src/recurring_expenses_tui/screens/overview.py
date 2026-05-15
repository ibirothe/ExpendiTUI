from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from ..calculations import (
    monthly_equivalent,
    total_monthly,
    total_yearly,
    yearly_equivalent,
)
from ..constants import APP_TITLE
from ..theme import AppTheme


def format_money(value) -> str:
    return f"{value:.2f}"


class OverviewPane(Vertical):
    CSS = """
    OverviewPane {
        height: 1fr;
    }

    #overview-title {
        content-align: center middle;
        height: 3;
        text-style: bold;
    }

    #overview-table {
        height: 1fr;
    }

    #overview-totals {
        height: auto;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(APP_TITLE, id="overview-title")
        yield DataTable(id="overview-table")
        yield Static(id="overview-totals")

    def on_mount(self) -> None:
        table = self.query_one("#overview-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "Name", "Amount", "Frequency", "Monthly Equivalent", "Yearly Equivalent"
        )
        self.refresh_view()

    def on_screen_resume(self) -> None:
        self.refresh_view()

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        self.query_one("#overview-title", Static).set_styles(
            background=theme.surface,
            color=theme.accent,
        )
        self.query_one("#overview-table", DataTable).set_styles(
            background=theme.surface,
            color=theme.foreground,
        )
        self.query_one("#overview-totals", Static).set_styles(
            background=theme.background,
            color=theme.foreground,
        )
        self.refresh_view()

    def refresh_view(self) -> None:
        table = self.query_one("#overview-table", DataTable)
        table.clear(columns=False)

        expenses = self.app.expenses
        for name, entry in expenses.items():
            table.add_row(
                name,
                format_money(entry.amount),
                entry.frequency.value,
                format_money(monthly_equivalent(entry.amount, entry.frequency)),
                format_money(yearly_equivalent(entry.amount, entry.frequency)),
            )

        monthly_total = total_monthly(expenses)
        yearly_total = total_yearly(expenses)
        totals = Text()
        totals.append(
            f"Total monthly base cost: {format_money(monthly_total)}\n",
            style=self.app.theme_rich_style("success", bold=True),
        )
        totals.append(
            f"Total yearly base cost: {format_money(yearly_total)}",
            style=self.app.theme_rich_style("accent", bold=True),
        )
        self.query_one("#overview-totals", Static).update(totals)
