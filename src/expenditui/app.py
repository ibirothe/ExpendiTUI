from __future__ import annotations

from textual.app import ScreenStackError
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from .constants import APP_TITLE
from .models import EntryType, FinancialEntry
from .screens.edit import EditPane
from .screens.help import HelpPane
from .screens.overview import OverviewPane
from .screens.settings import SettingsPane
from .storage import (
    StorageError,
    get_dataset_path,
    get_expenses_path,
    get_income_path,
    load_entries,
    load_tag_registry,
    save_entries,
    save_tag_registry,
)
from .tags import TagRegistry
from .theme import AppTheme, ThemeManager
from .visualization import (
    VisualizationConfig,
    VisualizationConfigManager,
    VisualizationRenderer,
    VisualizationResult,
)

OVERVIEW_TAB = "overview-tab"
EDIT_TAB = "edit-tab"
HELP_TAB = "help-tab"
SETTINGS_TAB = "settings-tab"
THEME_NOTICE_SECONDS = 2.0
THEME_CSS_SOURCE = ("runtime-theme.css", "ExpendiTUIApp.RUNTIME_THEME_CSS")


class ExpendiTUIApp(App[None]):
    TITLE = APP_TITLE
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "reload", "Reload Data", priority=True),
        Binding("o", "show_overview", "Overview"),
        Binding("e", "show_edit", "Edit"),
        Binding("h", "show_help", "Help"),
        Binding("s", "show_settings", "Settings"),
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
        self.visualization_manager = VisualizationConfigManager()
        self.visualization_renderer = VisualizationRenderer()

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
        self.refresh_bindings()

    def load_state(self) -> str | None:
        diagnostics: list[str] = []
        loaded_any = False
        for entry_type in EntryType:
            try:
                result = load_entries(entry_type)
                self.set_entries(entry_type, result.entries)
                loaded_any = True
                if result.diagnostics:
                    count = len(result.diagnostics)
                    noun = "entry" if count == 1 else "entries"
                    diagnostics.append(
                        f"{entry_type.display_name}: skipped {count} invalid {noun} from {get_dataset_path(entry_type)}."
                    )
            except StorageError as exc:
                self.set_entries(entry_type, {})
                diagnostics.append(str(exc))

        tag_result = load_tag_registry()
        tag_registry = tag_result.registry
        entry_tags = self._collect_all_tags()
        tag_registry_changed = tag_registry.extend(entry_tags)
        if tag_result.diagnostics:
            diagnostics.extend(tag_result.diagnostics)
        if tag_result.needs_save or tag_registry_changed:
            try:
                save_tag_registry(tag_registry)
            except StorageError as exc:
                diagnostics.append(str(exc))
        self.tag_registry = tag_registry

        self.last_error = " | ".join(diagnostics) if diagnostics else None
        if loaded_any:
            self.status_message = "Loaded expense and income entries."
            self.status_message_kind = "success"
        else:
            self.status_message = None
        return self.last_error

    def save_state(
        self, entry_type: EntryType, data: dict[str, FinancialEntry]
    ) -> str | None:
        updated_tag_registry = self.tag_registry.copy()
        updated_tag_registry.extend(self._collect_tags(data.values()))
        try:
            if updated_tag_registry.to_list() != self.tag_registry.to_list():
                save_tag_registry(updated_tag_registry)
                self.tag_registry = updated_tag_registry
            save_entries(entry_type, data)
            self.set_entries(entry_type, load_entries(entry_type).entries)
            self.tag_registry = updated_tag_registry
            self.last_error = None
            self.status_message = (
                f"Saved {entry_type.plural_name} to {get_dataset_path(entry_type)}."
            )
            self.status_message_kind = "success"
        except StorageError as exc:
            self.last_error = str(exc)
            self.status_message = None
        return self.last_error

    def get_entries(self, entry_type: EntryType) -> dict[str, FinancialEntry]:
        return self.expenses if entry_type is EntryType.EXPENSE else self.income

    def get_tag_registry(self) -> TagRegistry:
        return self.tag_registry

    def ensure_global_tag(self, raw_tag: str) -> tuple[str | None, str | None]:
        updated_registry = self.tag_registry.copy()
        try:
            canonical_tag, _changed = updated_registry.add(raw_tag)
            if updated_registry.to_list() != self.tag_registry.to_list():
                save_tag_registry(updated_registry)
            self.tag_registry = updated_registry
        except (StorageError, ValueError) as exc:
            self.last_error = str(exc)
            self.status_message = None
            return None, self.last_error
        return canonical_tag, None

    def set_entries(
        self, entry_type: EntryType, entries: dict[str, FinancialEntry]
    ) -> None:
        if entry_type is EntryType.EXPENSE:
            self.expenses = entries
        else:
            self.income = entries

    def refresh_views(self, *, sync_edit: bool = False) -> None:
        self.query_one(OverviewPane).refresh_view()
        edit_pane = self.query_one(EditPane)
        if sync_edit:
            edit_pane.load_from_app()
        else:
            edit_pane.refresh_theme_state()

        self.refresh_message_area()

    def _collect_all_tags(self) -> list[str]:
        tags: list[str] = []
        tags.extend(self._collect_tags(self.expenses.values()))
        tags.extend(self._collect_tags(self.income.values()))
        return tags

    def _collect_tags(self, entries) -> list[str]:
        tags: list[str] = []
        for entry in entries:
            tags.extend(entry.tags)
        return tags

    def switch_to_tab(self, tab_id: str) -> None:
        self.active_tab_id = tab_id
        self.query_one("#main-tabs", TabbedContent).active = tab_id
        self.refresh_bindings()

    def switch_to_overview(self) -> None:
        self.switch_to_tab(OVERVIEW_TAB)
        self.query_one(OverviewPane).refresh_view()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if (
            action
            in {
                "reload",
                "show_overview",
                "show_help",
                "show_settings",
                "back",
                "scroll_active_page_up",
                "scroll_active_page_down",
            }
            and self.edit_mode_blocks_global_actions()
        ):
            return False
        if action == "cycle_theme":
            return not self.theme_switch_blocks_global_actions()
        if action == "show_overview":
            return self.active_tab_id != OVERVIEW_TAB
        if action == "show_edit":
            return self.active_tab_id != EDIT_TAB
        if action == "back":
            return self.active_tab_id in {EDIT_TAB, HELP_TAB, SETTINGS_TAB}
        if action == "show_help":
            return self.active_tab_id != HELP_TAB
        if action == "show_settings":
            return self.active_tab_id != SETTINGS_TAB
        if action in {"scroll_active_page_up", "scroll_active_page_down"}:
            return self.active_tab_id in {OVERVIEW_TAB, EDIT_TAB, HELP_TAB}
        return super().check_action(action, parameters)

    def edit_mode_blocks_global_actions(self) -> bool:
        if self.active_tab_id != EDIT_TAB:
            return False
        try:
            return self.query_one(EditPane).blocks_app_navigation
        except ScreenStackError:
            return False

    def theme_switch_blocks_global_actions(self) -> bool:
        if self.active_tab_id != EDIT_TAB:
            return False
        try:
            return self.query_one(EditPane).blocks_theme_switch
        except ScreenStackError:
            return False

    def action_reload(self) -> None:
        self.load_state()
        self.reload_visualizations()
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
        if self.active_tab_id == OVERVIEW_TAB:
            self.query_one(OverviewPane).page_up()
        elif self.active_tab_id == EDIT_TAB:
            self.query_one(EditPane).page_up()
        elif self.active_tab_id == HELP_TAB:
            self.query_one(HelpPane).scroll_page_up(animate=False)

    def action_scroll_active_page_down(self) -> None:
        if self.active_tab_id == OVERVIEW_TAB:
            self.query_one(OverviewPane).page_down()
        elif self.active_tab_id == EDIT_TAB:
            self.query_one(EditPane).page_down()
        elif self.active_tab_id == HELP_TAB:
            self.query_one(HelpPane).scroll_page_down(animate=False)

    def action_cycle_theme(self) -> None:
        if self.theme_switch_blocks_global_actions():
            return
        self.theme_manager.cycle_next()
        self.apply_theme(announce=True)
        self.refresh_views(sync_edit=False)
        self.refresh_bindings()

    def action_back(self) -> None:
        self.switch_to_overview()

    def action_quit(self) -> None:
        self.exit()

    def refresh_message_area(self) -> None:
        message = self.query_one("#app-message", Static)
        message.styles.background = self.theme_color("background")
        if self.last_error:
            message.styles.color = self.theme_color("error")
            message.update(self.last_error)
            return
        if self.theme_notice:
            message.styles.color = self.theme_color("accent")
            message.update(self.theme_notice)
            return
        if self.status_message:
            color_slot = (
                "success" if self.status_message_kind == "success" else "foreground"
            )
            message.styles.color = self.theme_color(color_slot)
            message.update(self.status_message)
            return
        message.update("")

    @property
    def visualization_config(self) -> VisualizationConfig:
        return self.visualization_manager.config

    def reload_visualizations(self) -> VisualizationConfig:
        return self.visualization_manager.reload()

    def render_overview_visualization(
        self, available_width: int
    ) -> VisualizationResult:
        return self.visualization_renderer.render(
            config=self.visualization_config,
            income_entries=self.income,
            expense_entries=self.expenses,
            available_width=available_width,
            style_for_slot=lambda slot_name: self.theme_rich_style(
                slot_name, bold=True
            ),
        )

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
        surface_alt = theme.blend("surface", "background", 0.65)
        surface_hover = theme.blend("accent", "surface", 0.18)
        surface_focus = theme.blend("surface", "accent", 0.85)
        accent_soft = theme.blend("accent", "surface", 0.32)
        footer_description = theme.blend("surface", "background", 0.75)
        row_alt = theme.blend("surface", "background", 0.82)

        return f"""
        Screen {{
            background: {theme.background};
            color: {theme.foreground};
        }}

        Header {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        HeaderTitle {{
            color: {theme.accent};
        }}

        HeaderIcon {{
            color: {theme.accent};
        }}

        HeaderIcon:hover {{
            background: {accent_soft};
            color: {theme.background};
        }}

        Footer {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        FooterLabel {{
            background: {footer_description};
            color: {theme.foreground};
        }}

        FooterKey {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        FooterKey > .footer-key--key {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        FooterKey > .footer-key--description {{
            background: {footer_description};
            color: {theme.foreground};
        }}

        FooterKey:hover {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        Tabs {{
            background: {theme.background};
        }}

        Tab {{
            background: {theme.background};
            color: {theme.muted};
        }}

        Tab:hover {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        Tab.-active {{
            background: {theme.surface};
            color: {theme.foreground};
            text-style: bold;
        }}

        Tabs:focus .-active {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        Underline > .underline--bar {{
            color: {theme.accent};
            background: {surface_alt};
        }}

        Input {{
            background: {theme.surface};
            color: {theme.foreground};
            border: tall {theme.muted};
        }}

        Input:focus {{
            background: {surface_focus};
            border: tall {theme.accent};
        }}

        Input.-invalid {{
            border: tall {theme.error};
        }}

        Input.-invalid:focus {{
            border: tall {theme.error};
        }}

        Input > .input--cursor {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        Input > .input--selection {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        Input > .input--placeholder,
        Input > .input--suggestion {{
            color: {theme.muted};
        }}

        DataTable {{
            background: {theme.surface};
            color: {theme.foreground};
        }}

        DataTable > .datatable--header {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        DataTable > .datatable--fixed {{
            background: {surface_alt};
            color: {theme.foreground};
        }}

        DataTable > .datatable--even-row {{
            background: {row_alt};
        }}

        DataTable > .datatable--cursor {{
            background: {accent_soft};
            color: {theme.foreground};
            text-style: bold;
        }}

        DataTable:focus > .datatable--cursor {{
            background: {theme.accent};
            color: {theme.background};
            text-style: bold;
        }}

        DataTable > .datatable--fixed-cursor {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        DataTable:focus > .datatable--fixed-cursor {{
            background: {theme.accent};
            color: {theme.background};
        }}

        DataTable > .datatable--header-cursor {{
            background: {theme.accent};
            color: {theme.background};
        }}

        DataTable > .datatable--header-hover {{
            background: {accent_soft};
            color: {theme.foreground};
        }}

        DataTable > .datatable--hover {{
            background: {surface_hover};
        }}

        Markdown {{
            background: {theme.background};
            color: {theme.foreground};
        }}
        """


def main() -> None:
    ExpendiTUIApp().run()
