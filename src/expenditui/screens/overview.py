from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from ..calculations import (
    monthly_equivalent,
    savings_monthly,
    savings_yearly,
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
            "Type",
            "Name",
            "Amount",
            "Frequency",
            "Monthly Equivalent",
            "Yearly Equivalent",
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
        income = self.app.income
        for name, entry in expenses.items():
            table.add_row(
                "Expense",
                name,
                format_money(entry.amount),
                entry.frequency.value,
                format_money(monthly_equivalent(entry.amount, entry.frequency)),
                format_money(yearly_equivalent(entry.amount, entry.frequency)),
            )
        for name, entry in income.items():
            table.add_row(
                "Income",
                name,
                format_money(entry.amount),
                entry.frequency.value,
                format_money(monthly_equivalent(entry.amount, entry.frequency)),
                format_money(yearly_equivalent(entry.amount, entry.frequency)),
            )

        monthly_expenses = total_monthly(expenses)
        yearly_expenses = total_yearly(expenses)
        monthly_income = total_monthly(income)
        yearly_income = total_yearly(income)
        monthly_savings = savings_monthly(income, expenses)
        yearly_savings = savings_yearly(income, expenses)
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
