from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import ValidationError
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Label, Static

from ..constants import DEFAULT_FREQUENCY, MAX_TAGS
from ..models import EntryType, FinancialEntry
from ..tags import normalize_tag_key
from ..theme import AppTheme


@dataclass
class DraftEntry:
    name: str
    amount: str
    frequency: str
    tags: list[str]


class EditMode(str, Enum):
    NAVIGATION = "navigation"
    CREATE = "create"
    EDIT = "edit"
    CONFIRM_DELETE = "confirm_delete"
    MOVE = "move"


class ConfirmDialog(Static, can_focus=True):
    pass


class EntryForm(Vertical):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._attached_tags: list[str] = []
        self._suggestions: list[str] = []
        self._highlighted_suggestion_index: int | None = None
        self._empty_suggestion_message: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("Name", classes="field-label")
        yield Input(placeholder="Entry name", id="name-input")
        yield Label("Amount", classes="field-label")
        yield Input(placeholder="0.00", id="amount-input")
        yield Label("Frequency", classes="field-label")
        yield Input(placeholder=DEFAULT_FREQUENCY, id="frequency-input")
        yield Label("Tags", classes="field-label")
        yield Static(id="selected-tags")
        yield Input(placeholder="Type to search or create", id="tags-input")
        yield Static(id="tag-suggestions", classes="hidden")

    def set_draft(self, draft: DraftEntry) -> None:
        self.query_one("#name-input", Input).value = draft.name
        self.query_one("#amount-input", Input).value = draft.amount
        self.query_one("#frequency-input", Input).value = draft.frequency
        self.set_tags(draft.tags)
        self.clear_tag_input()
        self.hide_suggestions()

    def get_draft(self) -> DraftEntry:
        return DraftEntry(
            name=self.query_one("#name-input", Input).value,
            amount=self.query_one("#amount-input", Input).value,
            frequency=self.query_one("#frequency-input", Input).value,
            tags=self.get_tags(),
        )

    def focus_first_field(self) -> None:
        self.query_one("#name-input", Input).focus()

    def focus_next_field(self) -> None:
        self._focus_relative_field(1)

    def focus_previous_field(self) -> None:
        self._focus_relative_field(-1)

    def is_final_field(self, field: Input) -> bool:
        return field.id == "tags-input"

    def get_tags(self) -> list[str]:
        return list(self._attached_tags)

    def set_tags(self, tags: list[str]) -> None:
        self._attached_tags = list(tags)
        self._render_selected_tags()

    def pop_last_tag(self) -> str | None:
        if not self._attached_tags:
            return None
        removed = self._attached_tags.pop()
        self._render_selected_tags()
        return removed

    def get_tag_input(self) -> str:
        return self.query_one("#tags-input", Input).value

    def clear_tag_input(self) -> None:
        self.query_one("#tags-input", Input).value = ""

    def render_suggestions(
        self,
        suggestions: list[str],
        highlighted_index: int | None,
        *,
        empty_message: str | None = None,
    ) -> None:
        self._suggestions = list(suggestions)
        self._highlighted_suggestion_index = highlighted_index
        self._empty_suggestion_message = empty_message
        self._render_suggestions()

    def hide_suggestions(self) -> None:
        self._suggestions = []
        self._highlighted_suggestion_index = None
        self._empty_suggestion_message = None
        widget = self.query_one("#tag-suggestions", Static)
        widget.set_class(True, "hidden")
        widget.update("")

    def refresh_tag_views(self) -> None:
        self._render_selected_tags()
        self._render_suggestions()

    def _focus_relative_field(self, direction: int) -> None:
        fields = [
            self.query_one("#name-input", Input),
            self.query_one("#amount-input", Input),
            self.query_one("#frequency-input", Input),
            self.query_one("#tags-input", Input),
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

    def _render_selected_tags(self) -> None:
        widget = self.query_one("#selected-tags", Static)
        if not self._attached_tags:
            widget.update(
                Text("No tags selected.", style=self.app.theme_rich_style("muted"))
            )
            return

        text = Text()
        tag_style = self.app.theme_rich_style(
            "background",
            background_slot="accent",
            bold=True,
        )
        for index, tag in enumerate(self._attached_tags):
            if index:
                text.append(" ")
            text.append(f"[{tag}]", style=tag_style)
        widget.update(text)

    def _render_suggestions(self) -> None:
        widget = self.query_one("#tag-suggestions", Static)
        if not self._suggestions and self._empty_suggestion_message is None:
            widget.set_class(True, "hidden")
            widget.update("")
            return

        widget.set_class(False, "hidden")
        if not self._suggestions:
            widget.update(
                Text(
                    self._empty_suggestion_message or "",
                    style=self.app.theme_rich_style("muted"),
                )
            )
            return

        text = Text()
        for index, suggestion in enumerate(self._suggestions):
            if index:
                text.append("\n")
            is_highlighted = index == self._highlighted_suggestion_index
            line_style = (
                self.app.theme_rich_style(
                    "background",
                    background_slot="accent",
                    bold=True,
                )
                if is_highlighted
                else self.app.theme_rich_style("foreground")
            )
            prefix = "> " if is_highlighted else "  "
            text.append(prefix, style=line_style)
            text.append(suggestion, style=line_style)
        widget.update(text)


class EditPane(Vertical):
    CSS = """
    EditPane {
        height: 1fr;
    }

    #edit-title {
        content-align: center middle;
        height: 3;
        text-style: bold;
    }

    #edit-body {
        height: 1fr;
    }

    #edit-table {
        width: 1fr;
        height: 1fr;
    }

    #edit-form {
        width: 36;
        height: 1fr;
        padding: 0 1;
    }

    .field-label {
        margin-top: 1;
    }

    #selected-tags {
        min-height: 2;
        padding: 0 1;
        border: round $surface;
    }

    #tag-suggestions {
        min-height: 2;
        padding: 0 1;
        border: round $surface;
    }

    #delete-confirm {
        margin: 0 1 1 1;
        padding: 1 2;
        content-align: center middle;
    }

    #edit-message {
        min-height: 2;
        padding: 0 2 1 2;
    }

    .hidden {
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[DraftEntry] = []
        self.current_index = 0
        self.mode = EditMode.NAVIGATION
        self.active_dataset = EntryType.EXPENSE
        self.selection_by_dataset: dict[EntryType, str | None] = {
            EntryType.EXPENSE: None,
            EntryType.INCOME: None,
        }
        self.modal_origin_name: str | None = None
        self.modal_target_index: int | None = None
        self.move_original_entries: list[DraftEntry] | None = None
        self.move_original_index: int | None = None
        self.message_kind = "foreground"
        self.tag_suggestions: list[str] = []
        self.highlighted_tag_index: int | None = None

    def compose(self) -> ComposeResult:
        yield Static(id="edit-title")
        with Horizontal(id="edit-body"):
            yield DataTable(id="edit-table")
            yield EntryForm(id="edit-form", classes="hidden")
        yield ConfirmDialog(id="delete-confirm", classes="hidden")
        yield Static(id="edit-message")

    @property
    def blocks_app_navigation(self) -> bool:
        return self.mode is not EditMode.NAVIGATION

    @property
    def blocks_theme_switch(self) -> bool:
        return self.mode in {EditMode.CREATE, EditMode.EDIT, EditMode.MOVE}

    def on_mount(self) -> None:
        table = self.query_one("#edit-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("Name", key="name", width=24)
        table.add_column("Amount", key="amount", width=12)
        table.add_column("Frequency", key="frequency", width=12)
        table.add_column("Tags", key="tags", width=24)
        self.load_from_app()
        self.apply_theme(self.app.active_theme)

    def load_from_app(self, *, select_name: str | None = None) -> None:
        current_name = (
            select_name
            if select_name is not None
            else self.selection_by_dataset[self.active_dataset]
        )
        self.entries = [
            DraftEntry(
                name=name,
                amount=f"{entry.amount:.2f}",
                frequency=entry.frequency.value,
                tags=list(entry.tags),
            )
            for name, entry in self.app.get_entries(self.active_dataset).items()
        ]
        self.current_index = self._index_for_name(current_name)
        self.selection_by_dataset[self.active_dataset] = self.selected_name
        self.mode = EditMode.NAVIGATION
        self.modal_origin_name = self.selected_name
        self.modal_target_index = None
        self.move_original_entries = None
        self.move_original_index = None
        self.tag_suggestions = []
        self.highlighted_tag_index = None
        if self.is_mounted:
            self.refresh_table()
            self._update_mode_ui()
            self.set_message("")

    def focus_table(self) -> None:
        if not self.is_mounted:
            return
        table = self.query_one("#edit-table", DataTable)
        if self.entries:
            table.move_cursor(row=self.current_index, column=0, animate=False)
        table.focus()

    def refresh_table(self) -> None:
        table = self.query_one("#edit-table", DataTable)
        table.clear(columns=False)
        for index, entry in enumerate(self.entries):
            name_cell, amount_cell, frequency_cell, tags_cell = self._render_row(
                index, entry
            )
            table.add_row(
                name_cell,
                amount_cell,
                frequency_cell,
                tags_cell,
                key=f"row-{index}",
            )

        if self.entries:
            self.current_index = max(0, min(self.current_index, len(self.entries) - 1))
            table.move_cursor(row=self.current_index, column=0, animate=False)
        else:
            self.current_index = 0
        self.selection_by_dataset[self.active_dataset] = self.selected_name

    def page_up(self) -> None:
        self.query_one("#edit-table", DataTable).action_page_up()

    def page_down(self) -> None:
        self.query_one("#edit-table", DataTable).action_page_down()

    def move_selection(self, delta: int) -> None:
        if not self.entries:
            return
        self.current_index = max(
            0, min(self.current_index + delta, len(self.entries) - 1)
        )
        self.selection_by_dataset[self.active_dataset] = self.selected_name
        self.query_one("#edit-table", DataTable).move_cursor(
            row=self.current_index,
            column=0,
            animate=False,
        )

    def toggle_dataset(self) -> None:
        self.selection_by_dataset[self.active_dataset] = self.selected_name
        self.active_dataset = (
            EntryType.INCOME
            if self.active_dataset is EntryType.EXPENSE
            else EntryType.EXPENSE
        )
        self.load_from_app()
        self.focus_table()
        self.set_message(
            f"Showing {self.active_dataset.plural_name}.",
            kind="accent",
        )

    def start_create(self) -> None:
        self.modal_origin_name = self.selected_name
        self.modal_target_index = self.current_index + 1 if self.entries else 0
        self.mode = EditMode.CREATE
        self._show_form(
            DraftEntry(name="", amount="", frequency=DEFAULT_FREQUENCY, tags=[])
        )
        self.set_message("")

    def start_edit(self) -> None:
        if not self.entries:
            self.set_message("There is no entry to edit.", kind="error")
            return
        current = self.entries[self.current_index]
        self.modal_origin_name = current.name
        self.modal_target_index = self.current_index
        self.mode = EditMode.EDIT
        self.refresh_table()
        self._show_form(
            DraftEntry(
                name=current.name,
                amount=current.amount,
                frequency=current.frequency,
                tags=current.tags,
            )
        )
        self.set_message("")

    def start_delete_confirmation(self) -> None:
        if not self.entries:
            self.set_message("There is no entry to delete.", kind="error")
            return
        self.modal_origin_name = self.selected_name
        self.modal_target_index = self.current_index
        self.mode = EditMode.CONFIRM_DELETE
        dialog = self.query_one("#delete-confirm", ConfirmDialog)
        dialog.update("Delete this entry? (y/n)")
        self.refresh_table()
        self._update_mode_ui()
        dialog.focus()
        self.set_message("")

    def start_move(self) -> None:
        if not self.entries:
            self.set_message("There is no entry to move.", kind="error")
            return
        self.modal_origin_name = self.selected_name
        self.modal_target_index = self.current_index
        self.move_original_index = self.current_index
        self.move_original_entries = [self._copy_draft(entry) for entry in self.entries]
        self.mode = EditMode.MOVE
        self.refresh_table()
        self._update_mode_ui()
        self.focus_table()
        self.set_message(
            "MOVE MODE: use j/k or arrows, Enter to save, Esc to cancel.",
            kind="accent",
        )

    def move_active_entry(self, delta: int) -> None:
        if self.mode is not EditMode.MOVE or not self.entries:
            return
        next_index = max(0, min(self.current_index + delta, len(self.entries) - 1))
        if next_index == self.current_index:
            return
        moving_entry = self.entries.pop(self.current_index)
        self.entries.insert(next_index, moving_entry)
        self.current_index = next_index
        self.modal_target_index = next_index
        self.refresh_table()
        self.focus_table()

    def confirm_move(self) -> None:
        if self.mode is not EditMode.MOVE or not self.entries:
            return

        moved_name = self.selected_name
        validated, errors = self.validate_entries(self.entries)
        if errors:
            self.set_message(" | ".join(errors), kind="error")
            return

        error = self.app.save_state(self.active_dataset, validated)
        if error:
            self.set_message(error, kind="error")
            return

        self.move_original_entries = None
        self.move_original_index = None
        self.app.refresh_views(sync_edit=False)
        self.load_from_app(select_name=moved_name)
        self.focus_table()
        self.set_message(
            f"Moved {self.active_dataset.value}: {moved_name}.",
            kind="success",
        )

    def cancel_modal(self) -> None:
        canceling_move = self.mode is EditMode.MOVE
        if canceling_move and self.move_original_entries is not None:
            self.entries = [
                self._copy_draft(entry) for entry in self.move_original_entries
            ]
            self.current_index = self.move_original_index or 0
        self.mode = EditMode.NAVIGATION
        if canceling_move:
            self.current_index = max(0, min(self.current_index, len(self.entries) - 1))
        elif self.entries:
            self.current_index = self._index_for_name(self.modal_origin_name)
        else:
            self.current_index = 0
        self.modal_target_index = None
        self.move_original_entries = None
        self.move_original_index = None
        self.tag_suggestions = []
        self.highlighted_tag_index = None
        self._update_mode_ui()
        self.refresh_table()
        self.focus_table()
        self.set_message("")

    def submit_form(self) -> None:
        if self.mode not in {EditMode.CREATE, EditMode.EDIT}:
            return

        updated_entries = list(self.entries)
        draft = self.query_one(EntryForm).get_draft()
        target_index = self.modal_target_index or 0
        operation = self.mode

        if operation is EditMode.CREATE:
            updated_entries.insert(target_index, draft)
        else:
            updated_entries[target_index] = draft

        validated, errors = self.validate_entries(updated_entries)
        if errors:
            self.set_message(" | ".join(errors), kind="error")
            return

        error = self.app.save_state(self.active_dataset, validated)
        if error:
            self.set_message(error, kind="error")
            return

        selection_name = draft.name.strip()
        self.app.refresh_views(sync_edit=False)
        self.load_from_app(select_name=selection_name)
        self.focus_table()
        self.set_message(
            f"{'Created' if operation is EditMode.CREATE else 'Updated'} {self.active_dataset.value}: {selection_name}.",
            kind="success",
        )

    def confirm_delete(self) -> None:
        if self.mode is not EditMode.CONFIRM_DELETE or not self.entries:
            return

        target_index = self.modal_target_index or 0
        updated_entries = list(self.entries)
        removed = updated_entries.pop(target_index)

        validated, errors = self.validate_entries(updated_entries)
        if errors:
            self.set_message(" | ".join(errors), kind="error")
            return

        error = self.app.save_state(self.active_dataset, validated)
        if error:
            self.set_message(error, kind="error")
            return

        next_selection = None
        if updated_entries:
            next_index = min(target_index, len(updated_entries) - 1)
            next_selection = updated_entries[next_index].name

        self.app.refresh_views(sync_edit=False)
        self.load_from_app(select_name=next_selection)
        self.focus_table()
        self.set_message(
            f"Deleted {self.active_dataset.value}: {removed.name}.",
            kind="success",
        )

    def validate_entries(
        self, entries: list[DraftEntry]
    ) -> tuple[dict[str, FinancialEntry], list[str]]:
        validated: dict[str, FinancialEntry] = {}
        seen_names: set[str] = set()
        errors: list[str] = []

        for index, draft in enumerate(entries, start=1):
            name = draft.name.strip()
            frequency = draft.frequency.strip().lower()
            amount = draft.amount.strip()
            if not name:
                errors.append(f"Row {index}: name is required.")
                continue
            if name in seen_names:
                errors.append(f"Row {index}: duplicate name '{name}'.")
                continue
            seen_names.add(name)

            try:
                validated[name] = FinancialEntry(
                    amount=amount,
                    frequency=frequency,
                    tags=draft.tags,
                )
            except ValidationError as exc:
                for issue in exc.errors():
                    field = ".".join(str(part) for part in issue["loc"])
                    errors.append(f"Row {index} {field}: {issue['msg']}")

        return validated, errors

    def set_message(self, message: str, *, kind: str = "foreground") -> None:
        self.message_kind = kind
        widget = self.query_one("#edit-message", Static)
        widget.styles.color = self._message_color(kind)
        widget.update(message)

    @property
    def selected_name(self) -> str | None:
        if not self.entries:
            return None
        return self.entries[self.current_index].name

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if self.mode is EditMode.NAVIGATION:
            self._set_current_index_from_event(event.row_key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self.mode is EditMode.NAVIGATION:
            self._set_current_index_from_event(event.row_key)

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.mode not in {EditMode.CREATE, EditMode.EDIT}:
            return
        if event.input.id == "tags-input":
            self._refresh_tag_suggestions()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.mode not in {EditMode.CREATE, EditMode.EDIT}:
            return
        event.stop()
        if event.input.id == "tags-input":
            self._handle_tag_input_submit()
            return
        if self.query_one(EntryForm).is_final_field(event.input):
            self.submit_form()
        else:
            self.query_one(EntryForm).focus_next_field()

    def on_key(self, event: events.Key) -> None:
        if self.mode is EditMode.NAVIGATION:
            self._handle_navigation_key(event)
            return

        if self.mode is EditMode.CONFIRM_DELETE:
            self._handle_confirmation_key(event)
            return

        if self.mode is EditMode.MOVE:
            self._handle_move_key(event)
            return

        if (
            event.key == "escape"
            and self._tag_suggestions_open()
            and self._tags_input_has_focus()
        ):
            event.stop()
            event.prevent_default()
            self._hide_tag_suggestions()
            return

        if event.key == "up" and self._tags_input_has_focus() and self.tag_suggestions:
            event.stop()
            event.prevent_default()
            self._move_tag_highlight(-1)
            return

        if (
            event.key == "down"
            and self._tags_input_has_focus()
            and self.tag_suggestions
        ):
            event.stop()
            event.prevent_default()
            self._move_tag_highlight(1)
            return

        if (
            event.key == "backspace"
            and self._tags_input_has_focus()
            and not self.query_one(EntryForm).get_tag_input()
        ):
            removed = self.query_one(EntryForm).pop_last_tag()
            if removed is not None:
                event.stop()
                event.prevent_default()
                self._refresh_tag_suggestions()
                self.set_message(f"Removed tag: {removed}.", kind="muted")
            return

        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.cancel_modal()
            return

        if event.key == "tab":
            event.stop()
            event.prevent_default()
            if self._tags_input_has_focus() and self._apply_highlighted_tag():
                return
            self.query_one(EntryForm).focus_next_field()
            return

        if event.key == "shift+tab":
            event.stop()
            event.prevent_default()
            self.query_one(EntryForm).focus_previous_field()

    def _handle_navigation_key(self, event: events.Key) -> None:
        character = (event.character or "").lower()
        if character == "j":
            event.stop()
            event.prevent_default()
            self.move_selection(1)
            return
        if character == "k":
            event.stop()
            event.prevent_default()
            self.move_selection(-1)
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
        if character == "m":
            event.stop()
            event.prevent_default()
            self.start_move()
            return
        if character == "i":
            event.stop()
            event.prevent_default()
            self.toggle_dataset()

    def _handle_confirmation_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        character = (event.character or "").lower()
        if character == "y":
            self.confirm_delete()
        elif character == "n" or event.key == "escape":
            self.cancel_modal()

    def _handle_move_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        character = (event.character or "").lower()
        if event.key == "enter":
            self.confirm_move()
        elif event.key == "escape":
            self.cancel_modal()
        elif event.key == "up" or character == "k":
            self.move_active_entry(-1)
        elif event.key == "down" or character == "j":
            self.move_active_entry(1)

    def _show_form(self, draft: DraftEntry) -> None:
        form = self.query_one(EntryForm)
        self.tag_suggestions = []
        self.highlighted_tag_index = None
        form.set_draft(draft)
        self._update_mode_ui()
        form.focus_first_field()

    def _update_mode_ui(self) -> None:
        title = self.query_one("#edit-title", Static)
        form = self.query_one(EntryForm)
        dialog = self.query_one("#delete-confirm", ConfirmDialog)

        form.set_class(self.mode not in {EditMode.CREATE, EditMode.EDIT}, "hidden")
        dialog_hidden = self.mode is not EditMode.CONFIRM_DELETE
        dialog.set_class(dialog_hidden, "hidden")
        if dialog_hidden:
            dialog.update("")

        dataset_name = (
            self.active_dataset.plural_name.title()
            if self.mode is EditMode.NAVIGATION
            else self.active_dataset.display_name
        )
        title_text = {
            EditMode.NAVIGATION: (
                f"Edit {dataset_name} · Navigation · m Move · i Toggle "
                f"{'Income' if self.active_dataset is EntryType.EXPENSE else 'Expenses'}"
            ),
            EditMode.CREATE: f"Edit {dataset_name} · Create",
            EditMode.EDIT: f"Edit {dataset_name} · Edit",
            EditMode.CONFIRM_DELETE: f"Edit {dataset_name} · Confirm Delete",
            EditMode.MOVE: f"Edit {dataset_name} · MOVE MODE",
        }[self.mode]
        title.update(title_text)
        self._refresh_app_bindings()

    def _index_for_name(self, name: str | None) -> int:
        if name is None:
            return 0
        for index, entry in enumerate(self.entries):
            if entry.name == name:
                return index
        return 0

    def _set_current_index_from_event(self, row_key: object) -> None:
        value = getattr(row_key, "value", row_key)
        if value is None:
            return
        try:
            index = int(str(value).removeprefix("row-"))
        except ValueError:
            return
        if 0 <= index < len(self.entries):
            self.current_index = index
            self.selection_by_dataset[self.active_dataset] = self.selected_name

    def _render_row(
        self, index: int, entry: DraftEntry
    ) -> tuple[Text | str, Text | str, Text | str, Text | str]:
        tag: str | None = None
        accent_slot = "accent"
        if self.modal_target_index == index:
            if self.mode is EditMode.EDIT:
                tag = "EDITING"
                accent_slot = "accent"
            elif self.mode is EditMode.CONFIRM_DELETE:
                tag = "DELETE"
                accent_slot = "error"
            elif self.mode is EditMode.MOVE:
                tag = "MOVING"
                accent_slot = "success"

        tags_display = ", ".join(entry.tags)
        if tag is None:
            return (
                entry.name or "<blank>",
                entry.amount,
                entry.frequency,
                tags_display,
            )

        row_style = self.app.theme_rich_style(
            "background",
            background_slot=accent_slot,
            bold=True,
        )
        tag_style = self.app.theme_rich_style(accent_slot, bold=True)
        name = Text.assemble(
            (f"{entry.name or '<blank>'} ", row_style), (f"[{tag}]", tag_style)
        )
        amount = Text(entry.amount, style=row_style)
        frequency = Text(entry.frequency, style=row_style)
        tags = Text(tags_display, style=row_style)
        return name, amount, frequency, tags

    def _copy_draft(self, draft: DraftEntry) -> DraftEntry:
        return DraftEntry(
            name=draft.name,
            amount=draft.amount,
            frequency=draft.frequency,
            tags=list(draft.tags),
        )

    def apply_theme(self, theme: AppTheme) -> None:
        self.styles.background = theme.background
        self.styles.color = theme.foreground
        self.query_one("#edit-title", Static).set_styles(
            background=theme.surface,
            color=theme.accent,
        )
        self.query_one("#edit-table", DataTable).set_styles(
            background=theme.surface,
            color=theme.foreground,
        )
        form = self.query_one(EntryForm)
        form.styles.background = theme.surface
        form.styles.color = theme.foreground
        form.styles.border_left = ("solid", theme.muted)
        form.query_one("#selected-tags", Static).set_styles(
            background=theme.background,
            color=theme.foreground,
        )
        form.query_one("#tag-suggestions", Static).set_styles(
            background=theme.background,
            color=theme.foreground,
        )

        dialog = self.query_one("#delete-confirm", ConfirmDialog)
        dialog.styles.background = theme.surface
        dialog.styles.color = theme.foreground
        dialog.styles.border = ("round", theme.warning)
        for label in self.query(".field-label"):
            label.styles.color = theme.muted
        self.query_one("#edit-message", Static).set_styles(
            background=theme.background,
            color=self._message_color(self.message_kind),
        )
        self.refresh_theme_state()

    def refresh_theme_state(self) -> None:
        if self.entries:
            self.refresh_table()
        self.query_one(EntryForm).refresh_tag_views()
        self.query_one("#edit-message", Static).styles.color = self._message_color(
            self.message_kind
        )

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

    def _refresh_tag_suggestions(self) -> None:
        form = self.query_one(EntryForm)
        previous_tag = None
        if (
            self.highlighted_tag_index is not None
            and 0 <= self.highlighted_tag_index < len(self.tag_suggestions)
        ):
            previous_tag = self.tag_suggestions[self.highlighted_tag_index]

        query = form.get_tag_input().strip()
        if not query:
            self.tag_suggestions = []
            self.highlighted_tag_index = None
            form.hide_suggestions()
            return

        suggestions = self.app.get_tag_registry().suggestions(
            query,
            exclude=form.get_tags(),
        )
        self.tag_suggestions = suggestions
        if suggestions:
            if previous_tag in suggestions:
                self.highlighted_tag_index = suggestions.index(previous_tag)
            elif self.highlighted_tag_index is None:
                self.highlighted_tag_index = 0
            else:
                self.highlighted_tag_index = min(
                    self.highlighted_tag_index,
                    len(suggestions) - 1,
                )
            form.render_suggestions(
                suggestions,
                self.highlighted_tag_index,
            )
            return

        self.highlighted_tag_index = None
        form.render_suggestions(
            [],
            None,
            empty_message="No matching tags. Press Enter to create.",
        )

    def _move_tag_highlight(self, delta: int) -> None:
        if not self.tag_suggestions:
            return
        current_index = self.highlighted_tag_index or 0
        self.highlighted_tag_index = max(
            0,
            min(current_index + delta, len(self.tag_suggestions) - 1),
        )
        self.query_one(EntryForm).render_suggestions(
            self.tag_suggestions,
            self.highlighted_tag_index,
        )

    def _apply_highlighted_tag(self) -> bool:
        if (
            self.highlighted_tag_index is None
            or not 0 <= self.highlighted_tag_index < len(self.tag_suggestions)
        ):
            return False
        return self._add_tag_to_form(self.tag_suggestions[self.highlighted_tag_index])

    def _handle_tag_input_submit(self) -> None:
        if self._apply_highlighted_tag():
            return

        form = self.query_one(EntryForm)
        raw_tag = form.get_tag_input().strip()
        if not raw_tag:
            self.submit_form()
            return

        registry = self.app.get_tag_registry()
        if raw_tag in registry:
            self._add_tag_to_form(registry.canonicalize(raw_tag))
            return
        if len(form.get_tags()) >= MAX_TAGS:
            self.set_message(
                f"Tags must contain at most {MAX_TAGS} values.",
                kind="error",
            )
            return

        canonical_tag, error = self.app.ensure_global_tag(raw_tag)
        if error:
            self.set_message(error, kind="error")
            return
        if canonical_tag is not None:
            self._add_tag_to_form(canonical_tag)

    def _add_tag_to_form(self, raw_tag: str) -> bool:
        form = self.query_one(EntryForm)
        existing_tags = form.get_tags()
        canonical_tag = self.app.get_tag_registry().canonicalize(raw_tag)
        canonical_key = normalize_tag_key(canonical_tag)

        if any(normalize_tag_key(tag) == canonical_key for tag in existing_tags):
            form.clear_tag_input()
            self._refresh_tag_suggestions()
            self.set_message(f"Tag already added: {canonical_tag}.", kind="muted")
            return True

        if len(existing_tags) >= MAX_TAGS:
            self.set_message(
                f"Tags must contain at most {MAX_TAGS} values.",
                kind="error",
            )
            return False

        form.set_tags([*existing_tags, canonical_tag])
        form.clear_tag_input()
        self._refresh_tag_suggestions()
        self.set_message("")
        return True

    def _hide_tag_suggestions(self) -> None:
        self.tag_suggestions = []
        self.highlighted_tag_index = None
        self.query_one(EntryForm).hide_suggestions()

    def _tag_suggestions_open(self) -> bool:
        return (
            not self.query_one(EntryForm)
            .query_one(
                "#tag-suggestions",
                Static,
            )
            .has_class("hidden")
        )

    def _tags_input_has_focus(self) -> bool:
        return self.app.focused is self.query_one(EntryForm).query_one(
            "#tags-input",
            Input,
        )
