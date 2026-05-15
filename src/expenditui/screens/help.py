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
- j / k: move the selected entry down or up in Edit
- i: toggle between expense and income entries in Edit navigation
- a / A: create an entry in Edit
- e / E: edit the selected entry in Edit
- d / D: delete the selected entry in Edit
- tab / shift+tab: move between fields, or accept the highlighted tag suggestion
- up / down: move through tag suggestions while editing tags
- enter: advance fields, add or create tags, and submit from an empty tag field
- backspace: remove the last attached tag when the tag input is empty
- y / n: confirm or cancel delete in Edit
- r: reload data and resync global tags from disk
- esc: cancel the active Edit modal, or return to Overview from Edit or Help
- q: quit
""".strip()
