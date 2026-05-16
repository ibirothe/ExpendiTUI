from __future__ import annotations

from dataclasses import dataclass

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from ..theme import AppTheme


@dataclass(frozen=True, slots=True)
class ShortcutItem:
    keys: str
    description: str


@dataclass(frozen=True, slots=True)
class ShortcutSection:
    title: str
    accent_slot: str
    rows: tuple[ShortcutItem, ...]


GLOBAL_SHORTCUTS = ShortcutSection(
    title="Navigation",
    accent_slot="accent",
    rows=(
        ShortcutItem("o", "Open Overview tab"),
        ShortcutItem("h", "Open Help tab"),
        ShortcutItem("e", "Open Edit tab"),
        ShortcutItem("s", "Open Settings tab"),
        ShortcutItem("/", "Show Overview search"),
        ShortcutItem("u", "Cycle Overview sort mode"),
        ShortcutItem("enter", "Open selected Overview entry in Edit"),
        ShortcutItem(
            "pgup / pgdn",
            "Scroll contents",
        ),
        ShortcutItem("t", "Cycle color themes"),
        ShortcutItem("r", "Reload entries and tags from disk"),
        ShortcutItem("esc", "Cancel current action or close modals"),
        ShortcutItem("q", "Quit the app"),
    ),
)

EDIT_SHORTCUTS = ShortcutSection(
    title="Edit Mode",
    accent_slot="success",
    rows=(
        ShortcutItem("j / k", "Move the selected entry down or up."),
        ShortcutItem("i", "Toggle between expense and income lists."),
        ShortcutItem("m", "Move the selected entry to a new position."),
        ShortcutItem("a / A", "Create a new entry in the current list."),
        ShortcutItem("e / E", "Edit the currently selected entry."),
        ShortcutItem("d / D", "Delete the selected entry."),
        ShortcutItem("enter / esc", "Confirm or cancel move mode."),
        ShortcutItem("y / n", "Confirm or cancel delete."),
        ShortcutItem(
            "tab / shift+tab",
            "Move between fields or accept the highlighted tag suggestion.",
        ),
        ShortcutItem("up / down", "Step through tag suggestions."),
        ShortcutItem(
            "enter",
            "Advance fields, add tags, or submit from an empty tag field.",
        ),
        ShortcutItem(
            "backspace",
            "Remove the last attached tag when the tag input is empty.",
        ),
    ),
)

SETTINGS_SHORTCUTS = ShortcutSection(
    title="Settings Themes",
    accent_slot="warning",
    rows=(
        ShortcutItem("j / k", "Move the selected theme down or up."),
        ShortcutItem("enter", "Activate the selected theme or advance form fields."),
        ShortcutItem("a", "Create a new theme."),
        ShortcutItem("e", "Edit the selected theme."),
        ShortcutItem("d", "Delete the selected theme."),
        ShortcutItem("y / n", "Confirm or cancel theme deletion."),
        ShortcutItem("tab / shift+tab", "Move between theme form fields."),
        ShortcutItem("esc", "Cancel theme create, edit, or delete confirmation."),
    ),
)


class HelpPane(VerticalScroll):
    CSS = """
    HelpPane {
        height: 1fr;
        padding: 1 2;
    }

    .help-section {
        height: auto;
        width: 1fr;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="help-navigation-card", classes="help-section")
        yield Static(id="help-edit-card", classes="help-section")
        yield Static(id="help-settings-card", classes="help-section")
        yield Static(id="help-callout-theme", classes="help-section")
        yield Static(id="help-callout-reload", classes="help-section")
        yield Static(id="help-callout-settings", classes="help-section")

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        self._refresh_content(theme)

    def _refresh_content(self, theme: AppTheme) -> None:
        self.query_one("#help-navigation-card", Static).update(
            self._build_shortcut_panel(theme, GLOBAL_SHORTCUTS)
        )
        self.query_one("#help-edit-card", Static).update(
            self._build_shortcut_panel(theme, EDIT_SHORTCUTS)
        )
        self.query_one("#help-settings-card", Static).update(
            self._build_shortcut_panel(theme, SETTINGS_SHORTCUTS)
        )
        self.query_one("#help-callout-theme", Static).update(
            self._build_callout(
                theme,
                title="Theme",
                accent_slot="accent",
                message="Use t to rotate themes unless a focused edit or theme form is actively typing.",
            )
        )
        self.query_one("#help-callout-reload", Static).update(
            self._build_callout(
                theme,
                title="Reload",
                accent_slot="warning",
                message="Use r after editing files on disk to reload entries and refresh the tag registry.",
            )
        )
        self.query_one("#help-callout-settings", Static).update(
            self._build_callout(
                theme,
                title="Settings",
                accent_slot="muted",
                message="Use Settings to create, edit, delete, and activate persisted themes.",
            )
        )

    def _build_shortcut_panel(self, theme: AppTheme, section: ShortcutSection) -> Panel:
        table = Table(
            expand=True,
            box=None,
            pad_edge=False,
            show_header=True,
            header_style=theme.rich_style(section.accent_slot, bold=True),
        )
        table.add_column("Keys", no_wrap=True, width=18)
        table.add_column("Action", ratio=1)

        key_style = theme.rich_style(
            "background",
            background_slot=section.accent_slot,
            bold=True,
        )
        for row in section.rows:
            table.add_row(
                Text(f" {row.keys} ", style=key_style),
                Text(row.description, style=theme.rich_style("foreground")),
            )

        panel_background = theme.blend(section.accent_slot, "surface", 0.12)
        return Panel(
            table,
            title=section.title,
            border_style=theme.color(section.accent_slot),
            style=f"{theme.foreground} on {panel_background}",
            padding=(1, 1),
            expand=True,
        )

    def _build_callout(
        self,
        theme: AppTheme,
        *,
        title: str,
        accent_slot: str,
        message: str,
    ) -> Panel:
        panel_background = theme.blend(accent_slot, "surface", 0.18)
        return Panel(
            Text(message, style=theme.rich_style("foreground")),
            title=title,
            border_style=theme.color(accent_slot),
            style=f"{theme.foreground} on {panel_background}",
            padding=(1, 1),
            expand=True,
        )
