from __future__ import annotations

from rich.text import Text
from textual.app import ScreenStackError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from .constants import APP_TITLE
from .models import ExpenseEntry
from .screens.edit import EditPane
from .screens.help import HelpPane
from .screens.overview import OverviewPane
from .storage import StorageError, get_expenses_path, load_expenses, save_expenses

OVERVIEW_TAB = "overview-tab"
EDIT_TAB = "edit-tab"
HELP_TAB = "help-tab"


class RecurringExpensesApp(App[None]):
    TITLE = APP_TITLE
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "reload", "Reload JSON", priority=True),
        Binding("o", "show_overview", "Overview"),
        Binding("e", "show_edit", "Edit"),
        Binding("h", "show_help", "Help"),
        Binding("escape", "back", "Back", priority=True),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-tabs {
        height: 1fr;
    }

    #main-tabs ContentSwitcher {
        height: 1fr;
    }

    TabPane {
        height: 1fr;
    }

    #app-message {
        min-height: 1;
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.expenses: dict[str, ExpenseEntry] = {}
        self.last_error: str | None = None
        self.status_message: str | None = None
        self.active_tab_id = OVERVIEW_TAB

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial=OVERVIEW_TAB, id="main-tabs"):
            with TabPane("Overview", id=OVERVIEW_TAB):
                yield OverviewPane()
            with TabPane("Edit", id=EDIT_TAB):
                yield EditPane()
            with TabPane("Help", id=HELP_TAB):
                yield HelpPane()
        yield Static(id="app-message")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.load_state()
        self.refresh_views(sync_edit=True)
        self.refresh_bindings()

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        next_tab_id = event.pane.id or OVERVIEW_TAB
        if (
            self.active_tab_id == EDIT_TAB
            and next_tab_id != EDIT_TAB
            and self.edit_mode_blocks_global_actions()
        ):
            self.query_one("#main-tabs", TabbedContent).active = EDIT_TAB
            return

        self.active_tab_id = next_tab_id
        if self.active_tab_id == OVERVIEW_TAB:
            self.query_one(OverviewPane).refresh_view()
        elif self.active_tab_id == EDIT_TAB:
            self.query_one(EditPane).focus_table()
        self.refresh_bindings()

    def load_state(self) -> str | None:
        try:
            self.expenses = load_expenses()
            self.last_error = None
            self.status_message = f"Loaded expenses from {get_expenses_path()}."
        except StorageError as exc:
            self.expenses = {}
            self.last_error = str(exc)
            self.status_message = None
        return self.last_error

    def save_state(self, data: dict[str, ExpenseEntry]) -> str | None:
        try:
            save_expenses(data)
            self.expenses = load_expenses()
            self.last_error = None
            self.status_message = f"Saved expenses to {get_expenses_path()}."
        except StorageError as exc:
            self.last_error = str(exc)
            self.status_message = None
        return self.last_error

    def refresh_views(self, *, sync_edit: bool = False) -> None:
        self.query_one(OverviewPane).refresh_view()
        if sync_edit:
            self.query_one(EditPane).load_from_app()

        message = self.query_one("#app-message", Static)
        if self.last_error:
            message.update(Text(self.last_error, style="bold red"))
        elif self.status_message:
            message.update(Text(self.status_message, style="green"))
        else:
            message.update("")

    def switch_to_tab(self, tab_id: str) -> None:
        self.active_tab_id = tab_id
        self.query_one("#main-tabs", TabbedContent).active = tab_id
        self.refresh_bindings()

    def switch_to_overview(self) -> None:
        self.switch_to_tab(OVERVIEW_TAB)
        self.query_one(OverviewPane).refresh_view()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"reload", "show_overview", "show_help", "back"} and self.edit_mode_blocks_global_actions():
            return False
        if action == "show_overview":
            return self.active_tab_id != OVERVIEW_TAB
        if action == "show_edit":
            return self.active_tab_id != EDIT_TAB
        if action == "back":
            return self.active_tab_id in {EDIT_TAB, HELP_TAB}
        if action == "show_help":
            return self.active_tab_id != HELP_TAB
        return super().check_action(action, parameters)

    def edit_mode_blocks_global_actions(self) -> bool:
        if self.active_tab_id != EDIT_TAB:
            return False
        try:
            return self.query_one(EditPane).blocks_app_navigation
        except ScreenStackError:
            return False

    def action_reload(self) -> None:
        self.load_state()
        self.refresh_views(sync_edit=True)

    def action_show_edit(self) -> None:
        self.switch_to_tab(EDIT_TAB)

    def action_show_overview(self) -> None:
        self.switch_to_overview()

    def action_show_help(self) -> None:
        self.switch_to_tab(HELP_TAB)

    def action_back(self) -> None:
        self.switch_to_overview()

    def action_quit(self) -> None:
        self.exit()


def main() -> None:
    RecurringExpensesApp().run()
