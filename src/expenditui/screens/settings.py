from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Input, Label, Static

from ..theme import AppTheme, THEME_SLOT_NAMES


@dataclass(frozen=True, slots=True)
class DraftTheme:
    name: str
    colors: list[str]


class SettingsMode(str, Enum):
    NAVIGATION = "navigation"
    CREATE_THEME = "create_theme"
    EDIT_THEME = "edit_theme"
    CONFIRM_DELETE_THEME = "confirm_delete_theme"


FORM_GLOBAL_SHORTCUT_KEYS = {
    "/",
    "e",
    "h",
    "o",
    "q",
    "r",
    "s",
    "t",
    "u",
}


class ThemeDeleteDialog(Static, can_focus=True):
    pass


class ThemeForm(VerticalScroll):
    def compose(self) -> ComposeResult:
        yield Label("Theme Name", classes="field-label")
        yield Input(placeholder="Ocean Dark", id="theme-name-input")
        for slot_name in THEME_SLOT_NAMES:
            yield Label(slot_name.replace("_", " ").title(), classes="field-label")
            yield Input(placeholder="#RRGGBB", id=f"theme-color-{slot_name}")

    def set_draft(self, draft: DraftTheme) -> None:
        self.query_one("#theme-name-input", Input).value = draft.name
        for slot_name, color in zip(THEME_SLOT_NAMES, draft.colors, strict=True):
            self.query_one(f"#theme-color-{slot_name}", Input).value = color

    def get_draft(self) -> DraftTheme:
        return DraftTheme(
            name=self.query_one("#theme-name-input", Input).value,
            colors=[
                self.query_one(f"#theme-color-{slot_name}", Input).value
                for slot_name in THEME_SLOT_NAMES
            ],
        )

    def focus_first_field(self) -> None:
        self.query_one("#theme-name-input", Input).focus()

    def focus_next_field(self) -> None:
        self._focus_relative_field(1)

    def focus_previous_field(self) -> None:
        self._focus_relative_field(-1)

    def is_final_field(self, field: Input) -> bool:
        return field.id == f"theme-color-{THEME_SLOT_NAMES[-1]}"

    def _focus_relative_field(self, direction: int) -> None:
        fields = [
            self.query_one("#theme-name-input", Input),
            *[
                self.query_one(f"#theme-color-{slot_name}", Input)
                for slot_name in THEME_SLOT_NAMES
            ],
        ]
        focused = self.app.focused
        try:
            current_index = next(
                index for index, field in enumerate(fields) if field is focused
            )
        except StopIteration:
            current_index = 0

        target_index = max(0, min(current_index + direction, len(fields) - 1))
        fields[target_index].focus()


class SettingsPane(Vertical):
    CSS = """
    SettingsPane {
        height: 1fr;
    }

    #settings-title {
        content-align: center middle;
        height: 3;
        text-style: bold;
    }

    #settings-body {
        height: 1fr;
    }

    #theme-table {
        width: 1fr;
        height: 1fr;
    }

    #theme-form {
        width: 34;
        height: 1fr;
        padding: 0 1;
    }

    .field-label {
        margin-top: 1;
    }

    #theme-delete-confirm {
        margin: 0 1 1 1;
        padding: 1 2;
        content-align: center middle;
    }

    #settings-message {
        min-height: 2;
        padding: 0 2 1 2;
    }

    .hidden {
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.current_index = 0
        self.mode = SettingsMode.NAVIGATION
        self.modal_origin_index = 0
        self.modal_target_index: int | None = None
        self.message_kind = "foreground"

    def compose(self) -> ComposeResult:
        yield Static(id="settings-title")
        with Horizontal(id="settings-body"):
            yield DataTable(id="theme-table")
            yield ThemeForm(id="theme-form", classes="hidden")
        yield ThemeDeleteDialog(id="theme-delete-confirm", classes="hidden")
        yield Static(id="settings-message")

    @property
    def blocks_app_navigation(self) -> bool:
        return self.mode is not SettingsMode.NAVIGATION

    @property
    def blocks_theme_switch(self) -> bool:
        return self.mode in {SettingsMode.CREATE_THEME, SettingsMode.EDIT_THEME}

    def on_mount(self) -> None:
        table = self.query_one("#theme-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("Active", key="active", width=8)
        table.add_column("Theme", key="name", width=28)
        table.add_column("Preview", key="preview", width=24)
        self.refresh_theme_state()
        self.apply_theme(self.app.active_theme)

    def refresh_theme_state(self) -> None:
        if not self.is_mounted:
            return
        self.current_index = max(
            0, min(self.current_index, len(self.app.theme_manager.themes) - 1)
        )
        self.refresh_table()
        self._update_mode_ui()
        self.query_one("#settings-message", Static).styles.color = self._message_color(
            self.message_kind
        )

    def refresh_table(self) -> None:
        table = self.query_one("#theme-table", DataTable)
        table.clear(columns=False)
        for index, theme in enumerate(self.app.theme_manager.themes):
            table.add_row(*self._render_row(index, theme), key=f"theme-{index}")
        if self.app.theme_manager.themes:
            table.move_cursor(row=self.current_index, column=0, animate=False)

    def page_up(self) -> None:
        self.query_one("#theme-table", DataTable).action_page_up()

    def page_down(self) -> None:
        self.query_one("#theme-table", DataTable).action_page_down()

    def move_selection(self, delta: int) -> None:
        themes = self.app.theme_manager.themes
        if not themes:
            return
        self.current_index = max(0, min(self.current_index + delta, len(themes) - 1))
        self.query_one("#theme-table", DataTable).move_cursor(
            row=self.current_index,
            column=0,
            animate=False,
        )

    def start_create(self) -> None:
        self.modal_origin_index = self.current_index
        self.modal_target_index = None
        self.mode = SettingsMode.CREATE_THEME
        self._show_form(
            DraftTheme(
                name="",
                colors=["#000000" for _slot_name in THEME_SLOT_NAMES],
            )
        )
        self.set_message("")

    def start_edit(self) -> None:
        if not self.app.theme_manager.themes:
            self.set_message("There is no theme to edit.", kind="error")
            return
        theme = self.app.theme_manager.themes[self.current_index]
        self.modal_origin_index = self.current_index
        self.modal_target_index = self.current_index
        self.mode = SettingsMode.EDIT_THEME
        self.refresh_table()
        self._show_form(
            DraftTheme(
                name=theme.name,
                colors=[theme.color(slot_name) for slot_name in THEME_SLOT_NAMES],
            )
        )
        self.set_message("")

    def start_delete_confirmation(self) -> None:
        themes = self.app.theme_manager.themes
        if not themes:
            self.set_message("There is no theme to delete.", kind="error")
            return
        if len(themes) <= 1:
            self.set_message("At least one theme must remain.", kind="error")
            return
        self.modal_origin_index = self.current_index
        self.modal_target_index = self.current_index
        self.mode = SettingsMode.CONFIRM_DELETE_THEME
        dialog = self.query_one("#theme-delete-confirm", ThemeDeleteDialog)
        dialog.update(f'Delete theme "{themes[self.current_index].name}"? (y/n)')
        self.refresh_table()
        self._update_mode_ui()
        dialog.focus()
        self.set_message("")

    def cancel_modal(self) -> None:
        self.mode = SettingsMode.NAVIGATION
        self.current_index = max(
            0, min(self.modal_origin_index, len(self.app.theme_manager.themes) - 1)
        )
        self.modal_target_index = None
        self._update_mode_ui()
        self.refresh_table()
        self.focus_table()
        self.set_message("")

    def activate_selected_theme(self) -> None:
        try:
            self.app.theme_manager.set_active(self.current_index)
        except ValueError as exc:
            self.set_message(str(exc), kind="error")
            return
        self._after_theme_change()
        self.focus_table()
        self.set_message(
            f"Theme activated: {self.app.theme_manager.active_theme.name}.",
            kind="success",
        )

    def submit_form(self) -> None:
        if self.mode not in {SettingsMode.CREATE_THEME, SettingsMode.EDIT_THEME}:
            return

        draft = self.query_one(ThemeForm).get_draft()
        operation = self.mode
        target_index = self.modal_target_index or 0
        try:
            if operation is SettingsMode.CREATE_THEME:
                self.app.theme_manager.create_theme(
                    draft.name,
                    draft.colors,
                    activate=True,
                )
                self.current_index = len(self.app.theme_manager.themes) - 1
                action = "Created"
            else:
                self.app.theme_manager.update_theme(
                    target_index,
                    draft.name,
                    draft.colors,
                )
                self.current_index = target_index
                action = "Updated"
        except (OSError, ValueError) as exc:
            self.set_message(str(exc), kind="error")
            return

        theme_name = self.app.theme_manager.themes[self.current_index].name
        self.mode = SettingsMode.NAVIGATION
        self.modal_target_index = None
        self._after_theme_change()
        self.focus_table()
        self.set_message(f"{action} theme: {theme_name}.", kind="success")

    def confirm_delete(self) -> None:
        if self.mode is not SettingsMode.CONFIRM_DELETE_THEME:
            return

        target_index = self.modal_target_index or 0
        try:
            removed = self.app.theme_manager.delete_theme(target_index)
        except (OSError, ValueError) as exc:
            self.set_message(str(exc), kind="error")
            return

        self.current_index = min(target_index, len(self.app.theme_manager.themes) - 1)
        self.mode = SettingsMode.NAVIGATION
        self.modal_target_index = None
        self._after_theme_change()
        self.focus_table()
        self.set_message(f"Deleted theme: {removed.name}.", kind="success")

    def focus_table(self) -> None:
        if not self.is_mounted:
            return
        self.query_one("#theme-table", DataTable).focus()

    def set_message(self, message: str, *, kind: str = "foreground") -> None:
        self.message_kind = kind
        widget = self.query_one("#settings-message", Static)
        widget.styles.color = self._message_color(kind)
        widget.update(message)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.mode is SettingsMode.NAVIGATION:
            self._set_current_index_from_event(event.row_key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self.mode is SettingsMode.NAVIGATION:
            self._set_current_index_from_event(event.row_key)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.mode not in {SettingsMode.CREATE_THEME, SettingsMode.EDIT_THEME}:
            return
        event.stop()
        self.submit_form()

    def on_key(self, event: events.Key) -> None:
        if self.mode is SettingsMode.NAVIGATION:
            self._handle_navigation_key(event)
            return
        if self.mode is SettingsMode.CONFIRM_DELETE_THEME:
            self._handle_confirmation_key(event)
            return

        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.cancel_modal()
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.submit_form()
            return
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.query_one(ThemeForm).focus_next_field()
            return
        if event.key == "shift+tab":
            event.stop()
            event.prevent_default()
            self.query_one(ThemeForm).focus_previous_field()
            return

        character = (event.character or "").lower()
        if event.key in {"pageup", "pagedown"} or character in FORM_GLOBAL_SHORTCUT_KEYS:
            event.stop()

    def _handle_navigation_key(self, event: events.Key) -> None:
        character = (event.character or "").lower()
        if event.key == "up" or character == "k":
            event.stop()
            event.prevent_default()
            self.move_selection(-1)
            return
        if event.key == "down" or character == "j":
            event.stop()
            event.prevent_default()
            self.move_selection(1)
            return
        if character == "a":
            event.stop()
            event.prevent_default()
            self.start_create()
            return
        if character == "e":
            event.stop()
            event.prevent_default()
            self.start_edit()
            return
        if character == "d":
            event.stop()
            event.prevent_default()
            self.start_delete_confirmation()
            return
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.activate_selected_theme()

    def _handle_confirmation_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        character = (event.character or "").lower()
        if character == "y":
            self.confirm_delete()
        elif character == "n" or event.key == "escape":
            self.cancel_modal()

    def _show_form(self, draft: DraftTheme) -> None:
        form = self.query_one(ThemeForm)
        form.set_draft(draft)
        self._update_mode_ui()
        form.focus_first_field()

    def _update_mode_ui(self) -> None:
        title = self.query_one("#settings-title", Static)
        form = self.query_one(ThemeForm)
        dialog = self.query_one("#theme-delete-confirm", ThemeDeleteDialog)

        form_visible = self.mode in {SettingsMode.CREATE_THEME, SettingsMode.EDIT_THEME}
        form.set_class(not form_visible, "hidden")
        form.display = form_visible
        dialog_hidden = self.mode is not SettingsMode.CONFIRM_DELETE_THEME
        dialog.set_class(dialog_hidden, "hidden")
        dialog.display = not dialog_hidden
        if dialog_hidden:
            dialog.update("")

        title_text = {
            SettingsMode.NAVIGATION: "Settings - Themes - a Create - e Edit - d Delete - Enter Activate",
            SettingsMode.CREATE_THEME: "Settings - Create Theme",
            SettingsMode.EDIT_THEME: "Settings - Edit Theme",
            SettingsMode.CONFIRM_DELETE_THEME: "Settings - Confirm Delete",
        }[self.mode]
        title.update(title_text)
        self._refresh_app_bindings()

    def _after_theme_change(self) -> None:
        self.refresh_table()
        apply_theme = getattr(self.app, "apply_theme", None)
        if callable(apply_theme):
            apply_theme(announce=True)
        refresh_views = getattr(self.app, "refresh_views", None)
        if callable(refresh_views):
            refresh_views(sync_edit=False)
        self._refresh_app_bindings()

    def _set_current_index_from_event(self, row_key: object) -> None:
        value = getattr(row_key, "value", row_key)
        if value is None:
            return
        try:
            index = int(str(value).removeprefix("theme-"))
        except ValueError:
            return
        if 0 <= index < len(self.app.theme_manager.themes):
            self.current_index = index

    def _render_row(self, index: int, theme: AppTheme) -> tuple[Text | str, Text, Text]:
        is_active = index == self.app.theme_manager.active_index
        is_target = self.modal_target_index == index
        accent_slot = "accent"
        tag: str | None = "ACTIVE" if is_active else None
        if is_target and self.mode is SettingsMode.EDIT_THEME:
            tag = "EDITING"
        elif is_target and self.mode is SettingsMode.CONFIRM_DELETE_THEME:
            tag = "DELETE"
            accent_slot = "error"

        active_cell = Text("*" if is_active else "")
        name_style = self.app.theme_rich_style("foreground")
        if tag is not None:
            name_style = self.app.theme_rich_style(
                "background",
                background_slot=accent_slot,
                bold=True,
            )
        name_cell = Text(theme.name, style=name_style)
        if tag is not None:
            name_cell.append(" ")
            name_cell.append(
                f"[{tag}]",
                style=self.app.theme_rich_style(accent_slot, bold=True),
            )

        preview = Text()
        for slot_name in THEME_SLOT_NAMES:
            preview.append("  ", style=f"on {theme.color(slot_name)}")
            preview.append(" ")
        return active_cell, name_cell, preview

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        self.query_one("#settings-title", Static).set_styles(
            background=theme.surface,
            color=theme.accent,
        )
        self.query_one("#theme-table", DataTable).set_styles(
            background=theme.surface,
            color=theme.foreground,
        )
        form = self.query_one(ThemeForm)
        form.styles.background = theme.surface
        form.styles.color = theme.foreground
        form.styles.border_left = ("solid", theme.muted)
        dialog = self.query_one("#theme-delete-confirm", ThemeDeleteDialog)
        dialog.styles.background = theme.surface
        dialog.styles.color = theme.foreground
        dialog.styles.border = ("round", theme.warning)
        for label in self.query(".field-label"):
            label.styles.color = theme.muted
        self.query_one("#settings-message", Static).set_styles(
            background=theme.background,
            color=self._message_color(self.message_kind),
        )
        self.refresh_theme_state()

    def _message_color(self, kind: str) -> str:
        slot_name = {
            "success": "success",
            "error": "error",
            "accent": "accent",
            "muted": "muted",
        }.get(kind, "foreground")
        return self.app.theme_color(slot_name)

    def _refresh_app_bindings(self) -> None:
        refresh_bindings = getattr(self.app, "refresh_bindings", None)
        if callable(refresh_bindings):
            refresh_bindings()
