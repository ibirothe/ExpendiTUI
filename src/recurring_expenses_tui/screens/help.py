from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Markdown


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

    @property
    def help_markdown(self) -> str:
        return """
# Keyboard Shortcuts

- o: open Overview
- h: open Help
- e: open Edit
- j / k: move selection down or up in Edit
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
