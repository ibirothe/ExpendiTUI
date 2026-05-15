from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import ValidationError
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, Label, Static

from ..constants import DEFAULT_FREQUENCY
from ..models import ExpenseEntry
from ..theme import AppTheme


@dataclass
class DraftExpense:
    name: str
    amount: str
    frequency: str


class EditMode(str, Enum):
    NAVIGATION = "navigation"
    CREATE = "create"
    EDIT = "edit"
    CONFIRM_DELETE = "confirm_delete"


class ConfirmDialog(Static, can_focus=True):
    pass


class ExpenseForm(Vertical):
    def compose(self) -> ComposeResult:
        yield Label("Name", classes="field-label")
        yield Input(placeholder="Expense name", id="name-input")
        yield Label("Amount", classes="field-label")
        yield Input(placeholder="0.00", id="amount-input")
        yield Label("Frequency", classes="field-label")
        yield Input(placeholder=DEFAULT_FREQUENCY, id="frequency-input")

    def set_draft(self, draft: DraftExpense) -> None:
        self.query_one("#name-input", Input).value = draft.name
        self.query_one("#amount-input", Input).value = draft.amount
        self.query_one("#frequency-input", Input).value = draft.frequency

    def get_draft(self) -> DraftExpense:
        return DraftExpense(
            name=self.query_one("#name-input", Input).value,
            amount=self.query_one("#amount-input", Input).value,
            frequency=self.query_one("#frequency-input", Input).value,
        )

    def focus_first_field(self) -> None:
        self.query_one("#name-input", Input).focus()

    def focus_next_field(self) -> None:
        self._focus_relative_field(1)

    def focus_previous_field(self) -> None:
        self._focus_relative_field(-1)

    def is_final_field(self, field: Input) -> bool:
        return field.id == "frequency-input"

    def _focus_relative_field(self, direction: int) -> None:
        fields = [
            self.query_one("#name-input", Input),
            self.query_one("#amount-input", Input),
            self.query_one("#frequency-input", Input),
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
        width: 34;
        height: 1fr;
        padding: 0 1;
    }

    .field-label {
        margin-top: 1;
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
        self.entries: list[DraftExpense] = []
        self.current_index = 0
        self.mode = EditMode.NAVIGATION
        self.modal_origin_index = 0
        self.modal_target_index: int | None = None
        self.message_kind = "foreground"

    def compose(self) -> ComposeResult:
        yield Static(id="edit-title")
        with Horizontal(id="edit-body"):
            yield DataTable(id="edit-table")
            yield ExpenseForm(id="edit-form", classes="hidden")
        yield ConfirmDialog(id="delete-confirm", classes="hidden")
        yield Static(id="edit-message")

    @property
    def blocks_app_navigation(self) -> bool:
        return self.mode is not EditMode.NAVIGATION

    @property
    def blocks_theme_switch(self) -> bool:
        return self.mode in {EditMode.CREATE, EditMode.EDIT}

    def on_mount(self) -> None:
        table = self.query_one("#edit-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_column("Name", key="name", width=28)
        table.add_column("Amount", key="amount", width=12)
        table.add_column("Frequency", key="frequency", width=12)
        self.load_from_app()
        self.apply_theme(self.app.active_theme)

    def load_from_app(self, *, select_name: str | None = None) -> None:
        current_name = select_name or self.selected_name
        self.entries = [
            DraftExpense(
                name=name, amount=f"{entry.amount:.2f}", frequency=entry.frequency.value
            )
            for name, entry in self.app.expenses.items()
        ]
        self.current_index = self._index_for_name(current_name)
        self.mode = EditMode.NAVIGATION
        self.modal_origin_index = self.current_index
        self.modal_target_index = None
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
            name_cell, amount_cell, frequency_cell = self._render_row(index, entry)
            table.add_row(
                name_cell,
                amount_cell,
                frequency_cell,
                key=f"row-{index}",
            )

        if self.entries:
            self.current_index = max(0, min(self.current_index, len(self.entries) - 1))
            table.move_cursor(row=self.current_index, column=0, animate=False)
        else:
            self.current_index = 0

    def move_selection(self, delta: int) -> None:
        if not self.entries:
            return
        self.current_index = max(
            0, min(self.current_index + delta, len(self.entries) - 1)
        )
        self.query_one("#edit-table", DataTable).move_cursor(
            row=self.current_index,
            column=0,
            animate=False,
        )

    def start_create(self) -> None:
        self.modal_origin_index = self.current_index
        self.modal_target_index = self.current_index + 1 if self.entries else 0
        self.mode = EditMode.CREATE
        self._show_form(DraftExpense(name="", amount="", frequency=DEFAULT_FREQUENCY))
        self.set_message("")

    def start_edit(self) -> None:
        if not self.entries:
            self.set_message("There is no entry to edit.", kind="error")
            return
        current = self.entries[self.current_index]
        self.modal_origin_index = self.current_index
        self.modal_target_index = self.current_index
        self.mode = EditMode.EDIT
        self.refresh_table()
        self._show_form(
            DraftExpense(
                name=current.name, amount=current.amount, frequency=current.frequency
            )
        )
        self.set_message("")

    def start_delete_confirmation(self) -> None:
        if not self.entries:
            self.set_message("There is no entry to delete.", kind="error")
            return
        self.modal_origin_index = self.current_index
        self.modal_target_index = self.current_index
        self.mode = EditMode.CONFIRM_DELETE
        dialog = self.query_one("#delete-confirm", ConfirmDialog)
        dialog.update("Delete this entry? (y/n)")
        self.refresh_table()
        self._update_mode_ui()
        dialog.focus()
        self.set_message("")

    def cancel_modal(self) -> None:
        self.mode = EditMode.NAVIGATION
        if self.entries:
            self.current_index = max(
                0, min(self.modal_origin_index, len(self.entries) - 1)
            )
        else:
            self.current_index = 0
        self.modal_target_index = None
        self._update_mode_ui()
        self.refresh_table()
        self.focus_table()
        self.set_message("")

    def submit_form(self) -> None:
        if self.mode not in {EditMode.CREATE, EditMode.EDIT}:
            return

        updated_entries = list(self.entries)
        draft = self.query_one(ExpenseForm).get_draft()
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

        error = self.app.save_state(validated)
        if error:
            self.set_message(error, kind="error")
            return

        selection_name = draft.name.strip()
        self.app.refresh_views(sync_edit=False)
        self.load_from_app(select_name=selection_name)
        self.focus_table()
        self.set_message(
            f"{'Created' if operation is EditMode.CREATE else 'Updated'} entry: {selection_name}.",
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

        error = self.app.save_state(validated)
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
        self.set_message(f"Deleted entry: {removed.name}.", kind="success")

    def validate_entries(
        self, entries: list[DraftExpense]
    ) -> tuple[dict[str, ExpenseEntry], list[str]]:
        validated: dict[str, ExpenseEntry] = {}
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
                validated[name] = ExpenseEntry(amount=amount, frequency=frequency)
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

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.mode not in {EditMode.CREATE, EditMode.EDIT}:
            return
        event.stop()
        if self.query_one(ExpenseForm).is_final_field(event.input):
            self.submit_form()
        else:
            self.query_one(ExpenseForm).focus_next_field()

    def on_key(self, event: events.Key) -> None:
        if self.mode is EditMode.NAVIGATION:
            self._handle_navigation_key(event)
            return

        if self.mode is EditMode.CONFIRM_DELETE:
            self._handle_confirmation_key(event)
            return

        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self.cancel_modal()
            return

        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self.query_one(ExpenseForm).focus_next_field()
            return

        if event.key == "shift+tab":
            event.stop()
            event.prevent_default()
            self.query_one(ExpenseForm).focus_previous_field()

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

    def _handle_confirmation_key(self, event: events.Key) -> None:
        event.stop()
        event.prevent_default()
        character = (event.character or "").lower()
        if character == "y":
            self.confirm_delete()
        elif character == "n" or event.key == "escape":
            self.cancel_modal()

    def _show_form(self, draft: DraftExpense) -> None:
        form = self.query_one(ExpenseForm)
        form.set_draft(draft)
        self._update_mode_ui()
        form.focus_first_field()

    def _update_mode_ui(self) -> None:
        title = self.query_one("#edit-title", Static)
        form = self.query_one(ExpenseForm)
        dialog = self.query_one("#delete-confirm", ConfirmDialog)

        form.set_class(self.mode not in {EditMode.CREATE, EditMode.EDIT}, "hidden")
        dialog.set_class(self.mode is not EditMode.CONFIRM_DELETE, "hidden")

        title.update(
            {
                EditMode.NAVIGATION: "Edit Recurring Expenses · Navigation",
                EditMode.CREATE: "Edit Recurring Expenses · Create",
                EditMode.EDIT: "Edit Recurring Expenses · Edit",
                EditMode.CONFIRM_DELETE: "Edit Recurring Expenses · Confirm Delete",
            }[self.mode]
        )
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

    def _render_row(
        self, index: int, entry: DraftExpense
    ) -> tuple[Text | str, Text | str, Text | str]:
        tag: str | None = None
        accent_slot = "accent"
        if self.modal_target_index == index:
            if self.mode is EditMode.EDIT:
                tag = "EDITING"
                accent_slot = "accent"
            elif self.mode is EditMode.CONFIRM_DELETE:
                tag = "DELETE"
                accent_slot = "error"

        if tag is None:
            return (
                entry.name or "<blank>",
                entry.amount,
                entry.frequency,
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
        return name, amount, frequency

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
        form = self.query_one(ExpenseForm)
        form.styles.background = theme.surface
        form.styles.color = theme.foreground
        form.styles.border_left = ("solid", theme.muted)

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
