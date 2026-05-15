from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown

from ..theme import AppTheme


class HelpPane(VerticalScroll):
    CSS = """
    HelpPane {
        height: 1fr;
        padding: 0 1;
    }

    #help-content {
        padding-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Markdown(self.help_markdown, id="help-content")

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        self.query_one("#help-content", Markdown).set_styles(
            background=theme.background,
            color=theme.foreground,
        )

    @property
    def help_markdown(self) -> str:
        return """
# Keyboard Shortcuts

- t: cycle themes globally, except while typing in Edit create or edit forms
- o: open Overview
- h: open Help
- e: open Edit
- j / k: move selection down or up in Edit
- i: toggle between expenses and income in Edit navigation
- a / A: create an entry in Edit
- e / E: edit the selected entry in Edit
- d / D: delete the selected entry in Edit
- tab / shift+tab: move between fields while creating or editing
- enter: advance fields and submit from the final field while creating or editing
- y / n: confirm or cancel delete in Edit
- r: reload the JSON file
- esc: cancel the active Edit modal, or return to Overview from Edit or Help
- q: quit
""".strip()
