from __future__ import annotations

from textual.app import ScreenStackError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from .app_state import AppStateService
from .constants import APP_TITLE
from .models import EntryType, FinancialEntry
from .screens.edit import EditPane
from .screens.help import HelpPane
from .screens.overview import OverviewPane
from .screens.settings import SettingsPane
from .settings_data import (
    SettingsDataManager,
    SettingsDeletionCategory,
    format_deletion_error,
)
from .storage import (
    StorageError,
    get_expenses_path,
    get_income_path,
)
from .tags import TagRegistry
from .theme import AppTheme, ThemeManager
from .theme_css import build_theme_css

OVERVIEW_TAB = "overview-tab"
EDIT_TAB = "edit-tab"
HELP_TAB = "help-tab"
SETTINGS_TAB = "settings-tab"
THEME_NOTICE_SECONDS = 2.0
THEME_CSS_SOURCE = ("runtime-theme.css", "ExpendiTUIApp.RUNTIME_THEME_CSS")
NAVIGATION_TAB_IDS = frozenset({OVERVIEW_TAB, EDIT_TAB, HELP_TAB, SETTINGS_TAB})
GLOBAL_BLOCKED_ACTIONS = frozenset(
    {
        "reload",
        "show_overview",
        "show_edit",
        "show_help",
        "show_settings",
        "back",
        "focus_overview_search",
        "toggle_overview_sort",
        "open_overview_selection_in_edit",
        "scroll_active_page_up",
        "scroll_active_page_down",
    }
)
TAB_ACTIONS = {
    "show_overview": OVERVIEW_TAB,
    "show_edit": EDIT_TAB,
    "show_help": HELP_TAB,
    "show_settings": SETTINGS_TAB,
}


class ExpendiTUIApp(App[None]):
    TITLE = APP_TITLE
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "reload", "Reload Data", priority=True),
        Binding("o", "show_overview", "Overview"),
        Binding("e", "show_edit", "Edit"),
        Binding("h", "show_help", "Help"),
        Binding("s", "show_settings", "Settings"),
        Binding("/", "focus_overview_search", "Search"),
        Binding("u", "toggle_overview_sort", "Sort"),
        Binding(
            "enter",
            "open_overview_selection_in_edit",
            "Edit Entry",
            show=False,
        ),
        Binding("pageup", "scroll_active_page_up", "Page Up", show=False),
        Binding("pagedown", "scroll_active_page_down", "Page Down", show=False),
        Binding("t", "cycle_theme", "Theme"),
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
        self.expenses: dict[str, FinancialEntry] = {}
        self.income: dict[str, FinancialEntry] = {}
        self.tag_registry = TagRegistry()
        self.last_error: str | None = None
        self.status_message: str | None = None
        self.status_message_kind = "success"
        self.active_tab_id = OVERVIEW_TAB
        self.theme_notice: str | None = None
        self._theme_notice_token = 0
        self.theme_manager = ThemeManager()
        self.state_service = AppStateService(self)
        self.settings_data_manager = SettingsDataManager(self)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial=OVERVIEW_TAB, id="main-tabs"):
            with TabPane("Overview", id=OVERVIEW_TAB):
                yield OverviewPane()
            with TabPane("Edit", id=EDIT_TAB):
                yield EditPane()
            with TabPane("Help", id=HELP_TAB):
                yield HelpPane()
            with TabPane("Settings", id=SETTINGS_TAB):
                yield SettingsPane()
        yield Static(id="app-message")
        yield Footer(show_command_palette=False)

    def on_mount(self) -> None:
        self.apply_theme()
        self.load_state()
        self.refresh_views(sync_edit=True)
        self.refresh_bindings()

    @property
    def active_theme(self) -> AppTheme:
        return self.theme_manager.active_theme

    def theme_color(self, slot_name: str) -> str:
        return self.active_theme.color(slot_name)

    def theme_rich_style(
        self,
        foreground_slot: str,
        *,
        background_slot: str | None = None,
        bold: bool = False,
    ) -> str:
        return self.active_theme.rich_style(
            foreground_slot,
            background_slot=background_slot,
            bold=bold,
        )

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        next_tab_id = event.pane.id or OVERVIEW_TAB
        if not self._can_leave_active_tab(next_tab_id):
            self.query_one("#main-tabs", TabbedContent).active = self.active_tab_id
            return

        leaving_overview = (
            self.active_tab_id == OVERVIEW_TAB and next_tab_id != OVERVIEW_TAB
        )
        self.active_tab_id = next_tab_id
        if leaving_overview:
            self.query_one(OverviewPane).hide_search(clear=True, focus_table=False)
        if self.active_tab_id == OVERVIEW_TAB:
            self.query_one(OverviewPane).refresh_view()
        self.refresh_bindings()

    def load_state(self) -> str | None:
        return self.state_service.load_state()

    def save_state(
        self, entry_type: EntryType, data: dict[str, FinancialEntry]
    ) -> str | None:
        return self.state_service.save_state(entry_type, data)

    def get_entries(self, entry_type: EntryType) -> dict[str, FinancialEntry]:
        return self.state_service.get_entries(entry_type)

    def get_tag_registry(self) -> TagRegistry:
        return self.tag_registry

    def ensure_global_tag(self, raw_tag: str) -> tuple[str | None, str | None]:
        return self.state_service.ensure_global_tag(raw_tag)

    def set_entries(
        self, entry_type: EntryType, entries: dict[str, FinancialEntry]
    ) -> None:
        self.state_service.set_entries(entry_type, entries)

    def refresh_views(self, *, sync_edit: bool = False) -> None:
        self.query_one(OverviewPane).refresh_view()
        edit_pane = self.query_one(EditPane)
        if sync_edit:
            edit_pane.load_from_app()
        else:
            edit_pane.refresh_theme_state()

        self.refresh_message_area()

    def _collect_all_tags(self) -> list[str]:
        return self.state_service.collect_all_tags()

    def _collect_tags(self, entries) -> list[str]:
        return self.state_service.collect_tags(entries)

    def switch_to_tab(self, tab_id: str) -> None:
        if self.active_tab_id == OVERVIEW_TAB and tab_id != OVERVIEW_TAB:
            self.query_one(OverviewPane).hide_search(clear=True, focus_table=False)
        self.active_tab_id = tab_id
        self.query_one("#main-tabs", TabbedContent).active = tab_id
        self.refresh_bindings()

    def switch_to_overview(self) -> None:
        self.switch_to_tab(OVERVIEW_TAB)
        self.query_one(OverviewPane).refresh_view()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in GLOBAL_BLOCKED_ACTIONS and (
            self.edit_mode_blocks_global_actions()
            or self.settings_mode_blocks_global_actions()
        ):
            return False
        if action == "cycle_theme":
            return not self.theme_switch_blocks_global_actions()
        if action in TAB_ACTIONS:
            return self.active_tab_id != TAB_ACTIONS[action]
        if action == "back":
            return self.active_tab_id in {EDIT_TAB, HELP_TAB, SETTINGS_TAB}
        if action == "focus_overview_search":
            return self._overview_search_action_available()
        if action == "toggle_overview_sort":
            return self._overview_search_action_available()
        if action == "open_overview_selection_in_edit":
            return self._overview_selection_action_available()
        if action in {"scroll_active_page_up", "scroll_active_page_down"}:
            return self.active_tab_id in NAVIGATION_TAB_IDS
        return super().check_action(action, parameters)

    def _can_leave_active_tab(self, next_tab_id: str) -> bool:
        if self.active_tab_id == next_tab_id:
            return True
        return not (
            self.edit_mode_blocks_global_actions()
            or self.settings_mode_blocks_global_actions()
        )

    def _overview_search_action_available(self) -> bool:
        if self.active_tab_id != OVERVIEW_TAB:
            return False
        try:
            return not self.query_one(OverviewPane).search_has_focus
        except (NoMatches, ScreenStackError):
            return True

    def _overview_selection_action_available(self) -> bool:
        if self.active_tab_id != OVERVIEW_TAB:
            return False
        try:
            overview = self.query_one(OverviewPane)
            return (
                not overview.search_has_focus
                and overview.selected_entry_identity is not None
            )
        except (NoMatches, ScreenStackError):
            return False

    def edit_mode_blocks_global_actions(self) -> bool:
        if self.active_tab_id != EDIT_TAB:
            return False
        try:
            return self.query_one(EditPane).blocks_app_navigation
        except ScreenStackError:
            return False

    def theme_switch_blocks_global_actions(self) -> bool:
        if self.active_tab_id == EDIT_TAB:
            try:
                return self.query_one(EditPane).blocks_theme_switch
            except ScreenStackError:
                return False
        if self.active_tab_id == SETTINGS_TAB:
            try:
                return self.query_one(SettingsPane).blocks_theme_switch
            except ScreenStackError:
                return False
        return False

    def settings_mode_blocks_global_actions(self) -> bool:
        if self.active_tab_id != SETTINGS_TAB:
            return False
        try:
            return self.query_one(SettingsPane).blocks_app_navigation
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

    def action_show_settings(self) -> None:
        self.switch_to_tab(SETTINGS_TAB)

    def action_scroll_active_page_up(self) -> None:
        self._scroll_active_page("up")

    def action_scroll_active_page_down(self) -> None:
        self._scroll_active_page("down")

    def _scroll_active_page(self, direction: str) -> None:
        if self.active_tab_id == OVERVIEW_TAB:
            pane = self.query_one(OverviewPane)
            pane.page_up() if direction == "up" else pane.page_down()
        elif self.active_tab_id == EDIT_TAB:
            pane = self.query_one(EditPane)
            pane.page_up() if direction == "up" else pane.page_down()
        elif self.active_tab_id == HELP_TAB:
            pane = self.query_one(HelpPane)
            if direction == "up":
                pane.scroll_page_up(animate=False)
            else:
                pane.scroll_page_down(animate=False)
        elif self.active_tab_id == SETTINGS_TAB:
            pane = self.query_one(SettingsPane)
            pane.page_up() if direction == "up" else pane.page_down()

    def action_focus_overview_search(self) -> None:
        if self.active_tab_id != OVERVIEW_TAB:
            return
        self.query_one(OverviewPane).focus_search()

    def action_toggle_overview_sort(self) -> None:
        if self.active_tab_id != OVERVIEW_TAB:
            return
        overview = self.query_one(OverviewPane)
        if overview.search_has_focus:
            return
        overview.toggle_sort_mode()

    def action_open_overview_selection_in_edit(self) -> None:
        if self.active_tab_id != OVERVIEW_TAB:
            return
        self.open_overview_selection_in_edit()

    def open_overview_selection_in_edit(self) -> None:
        overview = self.query_one(OverviewPane)
        selection = overview.selected_entry_identity
        if selection is None:
            return
        entry_type, name = selection
        self.switch_to_tab(EDIT_TAB)
        edit_pane = self.query_one(EditPane)
        edit_pane.select_entry(entry_type, name)

    def action_cycle_theme(self) -> None:
        if self.theme_switch_blocks_global_actions():
            return
        self.theme_manager.cycle_next()
        self.apply_theme(announce=True)
        self.refresh_views(sync_edit=False)
        self.refresh_bindings()

    def action_back(self) -> None:
        if self.active_tab_id == OVERVIEW_TAB:
            overview = self.query_one(OverviewPane)
            if overview.search_has_focus:
                overview.hide_search()
                return
        self.switch_to_overview()

    def action_quit(self) -> None:
        self.exit()

    def refresh_message_area(self) -> None:
        message = self.query_one("#app-message", Static)
        message.styles.background = self.theme_color("background")
        sort_suffix = self._overview_sort_status_suffix()
        if self.last_error:
            message.styles.color = self.theme_color("error")
            message.update(self._message_with_suffix(self.last_error, sort_suffix))
            return
        if self.theme_notice:
            message.styles.color = self.theme_color("accent")
            message.update(self._message_with_suffix(self.theme_notice, sort_suffix))
            return
        if self.status_message:
            color_slot = (
                "success" if self.status_message_kind == "success" else "foreground"
            )
            message.styles.color = self.theme_color(color_slot)
            message.update(self._message_with_suffix(self.status_message, sort_suffix))
            return
        message.styles.color = self.theme_color("foreground")
        message.update(sort_suffix)

    def _overview_sort_status_suffix(self) -> str:
        if self.active_tab_id != OVERVIEW_TAB:
            return ""
        try:
            return self.query_one(OverviewPane).sort_status_label
        except (NoMatches, ScreenStackError):
            return ""

    @staticmethod
    def _message_with_suffix(message: str, suffix: str) -> str:
        if not suffix:
            return message
        return f"{message} | {suffix}"

    def delete_settings_data(self, category: SettingsDeletionCategory) -> str | None:
        try:
            handler = {
                SettingsDeletionCategory.DELETE_FINANCIAL_DATA: (
                    self.settings_data_manager.delete_financial_data
                ),
                SettingsDeletionCategory.DELETE_THEMES: (
                    self.settings_data_manager.delete_themes
                ),
                SettingsDeletionCategory.DELETE_RECOMMENDED_TAGS: (
                    self.settings_data_manager.delete_recommended_tags
                ),
            }.get(category)
            if handler is None:
                raise ValueError(f"Unsupported deletion category: {category}.")
            handler()
        except (OSError, StorageError, ValueError) as exc:
            self.last_error = format_deletion_error(exc)
            self.status_message = None
            self.refresh_message_area()
            return self.last_error
        return None

    def show_theme_notice(self) -> None:
        self.theme_notice = f"Theme: {self.active_theme.name}"
        self._theme_notice_token += 1
        token = self._theme_notice_token
        self.refresh_message_area()
        self.set_timer(
            THEME_NOTICE_SECONDS, callback=lambda: self._clear_theme_notice(token)
        )

    def _clear_theme_notice(self, token: int) -> None:
        if token != self._theme_notice_token:
            return
        self.theme_notice = None
        self.refresh_message_area()

    def apply_theme(self, *, announce: bool = False) -> None:
        theme = self.active_theme
        self._install_theme_css(theme)
        self.screen.styles.background = theme.background
        self.screen.styles.color = theme.foreground
        self.styles.background = theme.background
        self.styles.color = theme.foreground

        header = self.query_one_optional(Header)
        if header is not None:
            header.styles.background = theme.surface
            header.styles.color = theme.accent

        footer = self.query_one_optional(Footer)
        if footer is not None:
            footer.styles.background = theme.surface
            footer.styles.color = theme.foreground

        tabs = self.query_one_optional("#main-tabs", TabbedContent)
        if tabs is not None:
            tabs.styles.background = theme.background
            tabs.styles.color = theme.foreground

        for pane in self.query(TabPane):
            pane.styles.background = theme.background
            pane.styles.color = theme.foreground

        overview = self.query_one_optional(OverviewPane)
        if overview is not None:
            overview.apply_theme(theme)

        edit = self.query_one_optional(EditPane)
        if edit is not None:
            edit.apply_theme(theme)

        help_pane = self.query_one_optional(HelpPane)
        if help_pane is not None:
            help_pane.apply_theme(theme)

        settings_pane = self.query_one_optional(SettingsPane)
        if settings_pane is not None:
            settings_pane.apply_theme(theme)

        if announce:
            self.show_theme_notice()
        else:
            self.refresh_message_area()

    def _install_theme_css(self, theme: AppTheme) -> None:
        self.stylesheet.add_source(
            self._build_theme_css(theme), read_from=THEME_CSS_SOURCE
        )
        self.refresh_css(animate=False)

    def _build_theme_css(self, theme: AppTheme) -> str:
        return build_theme_css(theme)


def main() -> None:
    ExpendiTUIApp().run()
