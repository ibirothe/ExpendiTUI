from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ..theme import AppTheme


class SettingsPane(Vertical):
    CSS = """
    SettingsPane {
        height: 1fr;
        padding: 1 2;
    }

    #settings-placeholder {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(id="settings-placeholder")

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        placeholder = self.query_one("#settings-placeholder", Static)
        placeholder.set_styles(
            background=theme.background,
            color=theme.foreground,
        )
        placeholder.update(self._build_placeholder(theme))

    def _build_placeholder(self, theme: AppTheme) -> Panel:
        body = Text(
            "Reserved for future configuration options.",
            style=theme.rich_style("foreground"),
        )
        panel_background = theme.blend("surface", "background", 0.82)
        return Panel(
            body,
            title="Settings",
            border_style=theme.color("muted"),
            style=f"{theme.foreground} on {panel_background}",
            padding=(1, 2),
            expand=True,
        )
