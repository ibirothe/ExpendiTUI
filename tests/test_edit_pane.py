from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from recurring_expenses_tui.models import ExpenseEntry, Frequency
from recurring_expenses_tui.screens.edit import (
    DraftExpense,
    EditMode,
    EditPane,
    ExpenseForm,
)
from recurring_expenses_tui.theme import AppTheme


class FakeKeyEvent:
    def __init__(self, key: str, character: str | None = None) -> None:
        self.key = key
        self.character = character if character is not None else key
        self.stopped = False
        self.default_prevented = False

    def stop(self) -> None:
        self.stopped = True

    def prevent_default(self) -> None:
        self.default_prevented = True


class FakeInput:
    def __init__(self, app: "FakeApp", input_id: str, value: str = "") -> None:
        self.app = app
        self.id = input_id
        self.value = value

    def focus(self) -> None:
        self.app.focused = self


class FakeForm:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.hidden = True
        self.inputs = {
            "#name-input": FakeInput(app, "name-input"),
            "#amount-input": FakeInput(app, "amount-input"),
            "#frequency-input": FakeInput(app, "frequency-input"),
        }

    def query_one(self, selector: str, _cls: object | None = None) -> FakeInput:
        return self.inputs[selector]

    def set_draft(self, draft: DraftExpense) -> None:
        self.inputs["#name-input"].value = draft.name
        self.inputs["#amount-input"].value = draft.amount
        self.inputs["#frequency-input"].value = draft.frequency

    def get_draft(self) -> DraftExpense:
        return DraftExpense(
            name=self.inputs["#name-input"].value,
            amount=self.inputs["#amount-input"].value,
            frequency=self.inputs["#frequency-input"].value,
        )

    def focus_first_field(self) -> None:
        self.inputs["#name-input"].focus()

    def focus_next_field(self) -> None:
        fields = list(self.inputs.values())
        current = self.app.focused
        try:
            index = fields.index(current)
        except ValueError:
            index = 0
        fields[min(index + 1, len(fields) - 1)].focus()

    def focus_previous_field(self) -> None:
        fields = list(self.inputs.values())
        current = self.app.focused
        try:
            index = fields.index(current)
        except ValueError:
            index = 0
        fields[max(index - 1, 0)].focus()

    def is_final_field(self, field: FakeInput) -> bool:
        return field.id == "frequency-input"

    def set_class(self, hidden: bool, class_name: str) -> None:
        if class_name == "hidden":
            self.hidden = hidden

    def has_class(self, class_name: str) -> bool:
        return class_name == "hidden" and self.hidden


class FakeTable:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.rows: list[tuple[object, object, object]] = []
        self.cursor_row = 0
        self.styles = SimpleNamespace(background=None, color=None)

    def clear(self, *, columns: bool = False) -> None:
        self.rows.clear()

    def add_row(self, name: str, amount: str, frequency: str, *, key: str) -> None:
        self.rows.append((name, amount, frequency))

    def move_cursor(self, *, row: int, column: int, animate: bool = False) -> None:
        self.cursor_row = row

    def focus(self) -> None:
        self.app.focused = self


class FakeStyles(SimpleNamespace):
    color: str | None
    background: str | None


class FakeStatic:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.renderable = ""
        self.styles = FakeStyles(color=None, background=None)

    def update(self, value: str) -> None:
        self.renderable = value

    def set_styles(self, **styles: str) -> None:
        for name, value in styles.items():
            setattr(self.styles, name, value)


class FakeDialog(FakeStatic):
    def __init__(self, app: "FakeApp") -> None:
        super().__init__(app)
        self.hidden = True

    def focus(self) -> None:
        self.app.focused = self

    def set_class(self, hidden: bool, class_name: str) -> None:
        if class_name == "hidden":
            self.hidden = hidden

    def has_class(self, class_name: str) -> bool:
        return class_name == "hidden" and self.hidden


class FakeApp:
    def __init__(self, expenses: dict[str, ExpenseEntry]) -> None:
        self.expenses = dict(expenses)
        self.focused: object | None = None
        self.saved_payload: dict[str, ExpenseEntry] | None = None
        self.refresh_views_calls = 0
        self.active_theme = AppTheme(
            name="Test",
            background="#111111",
            foreground="#EEEEEE",
            surface="#222222",
            accent="#3366FF",
            success="#00AA66",
            warning="#FFAA00",
            error="#CC3333",
            muted="#888888",
        )

    def save_state(self, data: dict[str, ExpenseEntry]) -> str | None:
        self.saved_payload = dict(data)
        self.expenses = dict(data)
        return None

    def refresh_views(self, *, sync_edit: bool = False) -> None:
        self.refresh_views_calls += 1

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


class StubEditPane(EditPane):
    def __init__(self, app: FakeApp) -> None:
        self._test_app = app
        self._test_nodes = {
            "#edit-title": FakeStatic(app),
            "#edit-table": FakeTable(app),
            "#delete-confirm": FakeDialog(app),
            "#edit-message": FakeStatic(app),
            ExpenseForm: FakeForm(app),
        }
        super().__init__()

    @property
    def app(self) -> FakeApp:
        return self._test_app

    @property
    def is_mounted(self) -> bool:
        return True

    def query_one(self, selector: object, _cls: object | None = None) -> object:
        return self._test_nodes[selector]


def build_expenses() -> dict[str, ExpenseEntry]:
    return {
        "rent": ExpenseEntry(amount=Decimal("1200.00"), frequency=Frequency.MONTHLY),
        "insurance": ExpenseEntry(amount=Decimal("600.00"), frequency=Frequency.ANNUAL),
    }


def build_pane() -> tuple[StubEditPane, FakeApp]:
    app = FakeApp(build_expenses())
    pane = StubEditPane(app)
    pane.load_from_app()
    return pane, app


def test_navigation_mode_hides_form_and_supports_jk_navigation() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.focus_table()

    assert pane.mode is EditMode.NAVIGATION
    assert pane.current_index == 0
    assert pane.query_one(ExpenseForm).has_class("hidden")
    assert app.focused is table

    pane.on_key(FakeKeyEvent("j"))
    assert pane.current_index == 1

    pane.on_key(FakeKeyEvent("k"))
    assert pane.current_index == 0
    assert pane.blocks_theme_switch is False


def test_create_flow_inserts_below_selection_and_selects_new_entry() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.start_create()
    form = pane.query_one(ExpenseForm)
    form.query_one("#name-input").value = "utilities"
    form.query_one("#amount-input").value = "49.99"
    pane.submit_form()

    assert pane.mode is EditMode.NAVIGATION
    assert pane.selected_name == "utilities"
    assert list(app.expenses) == ["rent", "utilities", "insurance"]
    assert app.refresh_views_calls == 1
    assert app.focused is table


def test_create_validation_failure_keeps_form_open() -> None:
    pane, app = build_pane()

    pane.start_create()
    form = pane.query_one(ExpenseForm)
    form.query_one("#amount-input").value = "10.00"
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert "name is required" in pane.query_one("#edit-message").renderable
    assert list(app.expenses) == ["rent", "insurance"]


def test_create_duplicate_name_and_save_failure_keep_modal_open() -> None:
    pane, app = build_pane()
    form = pane.query_one(ExpenseForm)

    pane.start_create()
    form.query_one("#name-input").value = "rent"
    form.query_one("#amount-input").value = "10.00"
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert "duplicate name 'rent'" in pane.query_one("#edit-message").renderable
    assert app.refresh_views_calls == 0

    form.query_one("#name-input").value = "utilities"
    app.save_state = lambda data: "disk full"  # type: ignore[method-assign]
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert pane.query_one("#edit-message").renderable == "disk full"
    assert list(app.expenses) == ["rent", "insurance"]
    assert app.refresh_views_calls == 0


def test_edit_flow_supports_cancel_and_submit() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.start_edit()
    form = pane.query_one(ExpenseForm)

    assert pane.mode is EditMode.EDIT
    assert form.query_one("#name-input").value == "rent"
    assert "EDITING" in str(table.rows[0][0])

    form.query_one("#name-input").value = "rent-adjusted"
    pane.cancel_modal()

    assert pane.mode is EditMode.NAVIGATION
    assert list(app.expenses) == ["rent", "insurance"]
    assert pane.selected_name == "rent"

    pane.start_edit()
    form.query_one("#amount-input").value = "1250.00"
    pane.submit_form()

    assert pane.mode is EditMode.NAVIGATION
    assert app.expenses["rent"].amount == Decimal("1250.00")
    assert pane.selected_name == "rent"
    assert app.focused is table


def test_keyboard_shortcuts_drive_modal_entry_and_field_navigation() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")
    form = pane.query_one(ExpenseForm)

    add_event = FakeKeyEvent("a")
    pane.on_key(add_event)

    name_input = form.query_one("#name-input")
    amount_input = form.query_one("#amount-input")
    frequency_input = form.query_one("#frequency-input")

    assert add_event.stopped
    assert add_event.default_prevented
    assert pane.mode is EditMode.CREATE
    assert pane.blocks_theme_switch is True
    assert app.focused is name_input
    assert frequency_input.value == "monthly"

    tab_event = FakeKeyEvent("tab", character="")
    pane.on_key(tab_event)
    assert tab_event.stopped
    assert tab_event.default_prevented
    assert app.focused is amount_input

    shift_tab_event = FakeKeyEvent("shift+tab", character="")
    pane.on_key(shift_tab_event)
    assert shift_tab_event.stopped
    assert shift_tab_event.default_prevented
    assert app.focused is name_input

    escape_event = FakeKeyEvent("escape", character="")
    pane.on_key(escape_event)
    assert escape_event.stopped
    assert escape_event.default_prevented
    assert pane.mode is EditMode.NAVIGATION
    assert app.focused is table
    assert pane.blocks_theme_switch is False


def test_delete_confirmation_requires_explicit_choice_and_updates_selection() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")
    pane.current_index = 1

    pane.start_delete_confirmation()

    assert pane.mode is EditMode.CONFIRM_DELETE
    assert not pane.query_one("#delete-confirm").has_class("hidden")
    assert "DELETE" in str(table.rows[1][0])

    pane.on_key(FakeKeyEvent("n"))

    assert pane.mode is EditMode.NAVIGATION
    assert list(app.expenses) == ["rent", "insurance"]
    assert pane.selected_name == "insurance"

    pane.start_delete_confirmation()
    pane.on_key(FakeKeyEvent("y"))

    assert pane.mode is EditMode.NAVIGATION
    assert list(app.expenses) == ["rent"]
    assert pane.selected_name == "rent"
    assert app.focused is table


def test_delete_confirmation_escape_cancels_without_mutating_entries() -> None:
    pane, app = build_pane()

    pane.current_index = 1
    pane.start_delete_confirmation()
    pane.on_key(FakeKeyEvent("escape", character=""))

    assert pane.mode is EditMode.NAVIGATION
    assert pane.selected_name == "insurance"
    assert list(app.expenses) == ["rent", "insurance"]


def test_submitted_input_advances_fields_and_final_submit_persists() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(ExpenseForm)

    name_input = form.query_one("#name-input")
    amount_input = form.query_one("#amount-input")
    frequency_input = form.query_one("#frequency-input")
    name_input.value = "phone"
    amount_input.value = "25.00"

    pane.on_input_submitted(SimpleNamespace(input=name_input, stop=lambda: None))  # type: ignore[arg-type]
    assert app.focused is amount_input

    pane.on_input_submitted(SimpleNamespace(input=amount_input, stop=lambda: None))  # type: ignore[arg-type]
    assert app.focused is frequency_input

    pane.on_input_submitted(SimpleNamespace(input=frequency_input, stop=lambda: None))  # type: ignore[arg-type]
    assert list(app.expenses) == ["rent", "phone", "insurance"]


def test_empty_state_edit_and_delete_show_messages_without_leaving_navigation() -> None:
    app = FakeApp({})
    pane = StubEditPane(app)
    pane.load_from_app()

    pane.start_edit()
    assert pane.mode is EditMode.NAVIGATION
    assert pane.query_one("#edit-message").renderable == "There is no entry to edit."

    pane.start_delete_confirmation()
    assert pane.mode is EditMode.NAVIGATION
    assert pane.query_one("#edit-message").renderable == "There is no entry to delete."


def test_row_events_update_selection_only_while_navigating() -> None:
    pane, _app = build_pane()

    pane.on_data_table_row_selected(SimpleNamespace(row_key="row-1"))  # type: ignore[arg-type]
    assert pane.current_index == 1

    pane.start_edit()
    pane.on_data_table_row_highlighted(SimpleNamespace(row_key="row-0"))  # type: ignore[arg-type]

    assert pane.current_index == 1
