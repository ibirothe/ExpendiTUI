from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from expenditui.constants import MAX_TAGS
from expenditui.models import EntryType, ExpenseEntry, Frequency
from expenditui.screens.edit import DraftEntry, EditMode, EditPane, EntryForm
from expenditui.tags import TagRegistry
from expenditui.theme import AppTheme


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


class FakeStyles(SimpleNamespace):
    color: str | None
    background: str | None


class FakeStatic:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.renderable = ""
        self.hidden = False
        self.styles = FakeStyles(color=None, background=None)

    def update(self, value) -> None:
        self.renderable = value

    def set_styles(self, **styles: str) -> None:
        for name, value in styles.items():
            setattr(self.styles, name, value)

    def set_class(self, hidden: bool, class_name: str) -> None:
        if class_name == "hidden":
            self.hidden = hidden

    def has_class(self, class_name: str) -> bool:
        return class_name == "hidden" and self.hidden


class FakeDialog(FakeStatic):
    def focus(self) -> None:
        self.app.focused = self


class FakeForm:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.hidden = True
        self._attached_tags: list[str] = []
        self.inputs = {
            "#name-input": FakeInput(app, "name-input"),
            "#amount-input": FakeInput(app, "amount-input"),
            "#frequency-input": FakeInput(app, "frequency-input"),
            "#tags-input": FakeInput(app, "tags-input"),
        }
        self.widgets = {
            "#selected-tags": FakeStatic(app),
            "#tag-suggestions": FakeStatic(app),
        }
        self.widgets["#tag-suggestions"].hidden = True

    def query_one(self, selector: str, _cls: object | None = None):
        if selector in self.inputs:
            return self.inputs[selector]
        return self.widgets[selector]

    def set_draft(self, draft: DraftEntry) -> None:
        self.inputs["#name-input"].value = draft.name
        self.inputs["#amount-input"].value = draft.amount
        self.inputs["#frequency-input"].value = draft.frequency
        self.set_tags(draft.tags)
        self.clear_tag_input()
        self.hide_suggestions()

    def get_draft(self) -> DraftEntry:
        return DraftEntry(
            name=self.inputs["#name-input"].value,
            amount=self.inputs["#amount-input"].value,
            frequency=self.inputs["#frequency-input"].value,
            tags=self.get_tags(),
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
        return field.id == "tags-input"

    def get_tags(self) -> list[str]:
        return list(self._attached_tags)

    def set_tags(self, tags: list[str]) -> None:
        self._attached_tags = list(tags)

    def pop_last_tag(self) -> str | None:
        if not self._attached_tags:
            return None
        return self._attached_tags.pop()

    def get_tag_input(self) -> str:
        return self.inputs["#tags-input"].value

    def clear_tag_input(self) -> None:
        self.inputs["#tags-input"].value = ""

    def render_suggestions(
        self,
        suggestions: list[str],
        highlighted_index: int | None,
        *,
        empty_message: str | None = None,
    ) -> None:
        widget = self.widgets["#tag-suggestions"]
        widget.hidden = False
        widget.renderable = {
            "suggestions": list(suggestions),
            "highlighted_index": highlighted_index,
            "empty_message": empty_message,
        }

    def hide_suggestions(self) -> None:
        widget = self.widgets["#tag-suggestions"]
        widget.hidden = True
        widget.renderable = ""

    def refresh_tag_views(self) -> None:
        return None

    def set_class(self, hidden: bool, class_name: str) -> None:
        if class_name == "hidden":
            self.hidden = hidden

    def has_class(self, class_name: str) -> bool:
        return class_name == "hidden" and self.hidden


class FakeTable:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.rows: list[tuple[object, object, object, object]] = []
        self.cursor_row = 0
        self.styles = SimpleNamespace(background=None, color=None)

    def clear(self, *, columns: bool = False) -> None:
        self.rows.clear()

    def add_row(
        self, name: str, amount: str, frequency: str, tags: str, *, key: str
    ) -> None:
        self.rows.append((name, amount, frequency, tags))

    def move_cursor(self, *, row: int, column: int, animate: bool = False) -> None:
        self.cursor_row = row

    def focus(self) -> None:
        self.app.focused = self


class FakeApp:
    def __init__(
        self,
        expenses: dict[str, ExpenseEntry],
        income: dict[str, ExpenseEntry] | None = None,
    ) -> None:
        self.expenses = dict(expenses)
        self.income = dict(income or {})
        self.focused: object | None = None
        self.saved_payload: dict[str, ExpenseEntry] | None = None
        self.saved_dataset: EntryType | None = None
        self.refresh_views_calls = 0
        self.tag_registry = TagRegistry(["cash", "paypal", "bank"])
        self.tag_registry.extend(self._collect_tags(self.expenses.values()))
        self.tag_registry.extend(self._collect_tags(self.income.values()))
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

    def get_entries(self, entry_type: EntryType) -> dict[str, ExpenseEntry]:
        return self.expenses if entry_type is EntryType.EXPENSE else self.income

    def save_state(
        self, entry_type: EntryType, data: dict[str, ExpenseEntry]
    ) -> str | None:
        self.saved_dataset = entry_type
        self.saved_payload = dict(data)
        self.tag_registry.extend(self._collect_tags(data.values()))
        if entry_type is EntryType.EXPENSE:
            self.expenses = dict(data)
        else:
            self.income = dict(data)
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

    def get_tag_registry(self) -> TagRegistry:
        return self.tag_registry

    def ensure_global_tag(self, raw_tag: str) -> tuple[str | None, str | None]:
        try:
            canonical_tag, _changed = self.tag_registry.add(raw_tag)
        except ValueError as exc:
            return None, str(exc)
        return canonical_tag, None

    @staticmethod
    def _collect_tags(entries) -> list[str]:
        tags: list[str] = []
        for entry in entries:
            tags.extend(entry.tags)
        return tags


class StubEditPane(EditPane):
    def __init__(self, app: FakeApp) -> None:
        self._test_app = app
        self._test_nodes = {
            "#edit-title": FakeStatic(app),
            "#edit-table": FakeTable(app),
            "#delete-confirm": FakeDialog(app),
            "#edit-message": FakeStatic(app),
            EntryForm: FakeForm(app),
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


def build_income() -> dict[str, ExpenseEntry]:
    return {
        "salary": ExpenseEntry(
            amount=Decimal("3200.00"),
            frequency=Frequency.MONTHLY,
            tags=["Work", "Salary"],
        )
    }


def build_pane() -> tuple[StubEditPane, FakeApp]:
    app = FakeApp(build_expenses(), build_income())
    pane = StubEditPane(app)
    pane.load_from_app()
    return pane, app


def submit_tags_input(pane: StubEditPane, form: FakeForm, value: str) -> None:
    tags_input = form.query_one("#tags-input")
    tags_input.value = value
    pane.on_input_changed(SimpleNamespace(input=tags_input))  # type: ignore[arg-type]
    pane.on_input_submitted(SimpleNamespace(input=tags_input, stop=lambda: None))  # type: ignore[arg-type]


def test_navigation_mode_hides_form_and_supports_jk_navigation() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.focus_table()

    assert pane.mode is EditMode.NAVIGATION
    assert pane.active_dataset is EntryType.EXPENSE
    assert pane.current_index == 0
    assert pane.query_one(EntryForm).has_class("hidden")
    assert app.focused is table

    pane.on_key(FakeKeyEvent("j"))
    assert pane.current_index == 1

    pane.on_key(FakeKeyEvent("k"))
    assert pane.current_index == 0
    assert pane.blocks_theme_switch is False


def test_dataset_toggle_switches_rows_and_preserves_selection() -> None:
    pane, _app = build_pane()

    pane.current_index = 1
    pane.selection_by_dataset[EntryType.EXPENSE] = pane.selected_name
    pane.on_key(FakeKeyEvent("i"))

    assert pane.active_dataset is EntryType.INCOME
    assert [entry.name for entry in pane.entries] == ["salary"]
    assert pane.query_one("#edit-message").renderable == "Showing income."

    pane.on_key(FakeKeyEvent("i"))

    assert pane.active_dataset is EntryType.EXPENSE
    assert pane.selected_name == "insurance"


def test_create_flow_inserts_below_selection_and_selects_new_entry() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.start_create()
    form = pane.query_one(EntryForm)
    form.query_one("#name-input").value = "utilities"
    form.query_one("#amount-input").value = "49.99"
    submit_tags_input(pane, form, "Home")
    submit_tags_input(pane, form, "Bills")
    pane.submit_form()

    assert pane.mode is EditMode.NAVIGATION
    assert pane.selected_name == "utilities"
    assert list(app.expenses) == ["rent", "utilities", "insurance"]
    assert app.expenses["utilities"].tags == ["Home", "Bills"]
    assert app.saved_dataset is EntryType.EXPENSE
    assert app.refresh_views_calls == 1
    assert app.focused is table


def test_create_validation_failure_keeps_form_open() -> None:
    pane, app = build_pane()

    pane.start_create()
    form = pane.query_one(EntryForm)
    form.query_one("#amount-input").value = "10.00"
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert "name is required" in pane.query_one("#edit-message").renderable
    assert list(app.expenses) == ["rent", "insurance"]


def test_create_duplicate_name_and_save_failure_keep_modal_open() -> None:
    pane, app = build_pane()
    form = pane.query_one(EntryForm)

    pane.start_create()
    form.query_one("#name-input").value = "rent"
    form.query_one("#amount-input").value = "10.00"
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert "duplicate name 'rent'" in pane.query_one("#edit-message").renderable
    assert app.refresh_views_calls == 0

    form.query_one("#name-input").value = "utilities"
    app.save_state = lambda entry_type, data: "disk full"  # type: ignore[method-assign]
    pane.submit_form()

    assert pane.mode is EditMode.CREATE
    assert pane.query_one("#edit-message").renderable == "disk full"
    assert list(app.expenses) == ["rent", "insurance"]
    assert app.refresh_views_calls == 0


def test_edit_flow_supports_cancel_and_submit() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")

    pane.start_edit()
    form = pane.query_one(EntryForm)

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
    submit_tags_input(pane, form, "Housing")
    pane.submit_form()

    assert pane.mode is EditMode.NAVIGATION
    assert app.expenses["rent"].amount == Decimal("1250.00")
    assert app.expenses["rent"].tags == ["Housing"]
    assert pane.selected_name == "rent"
    assert app.focused is table


def test_create_and_delete_work_in_income_mode() -> None:
    pane, app = build_pane()
    pane.toggle_dataset()

    pane.start_create()
    form = pane.query_one(EntryForm)
    form.query_one("#name-input").value = "bonus"
    form.query_one("#amount-input").value = "500.00"
    form.query_one("#frequency-input").value = "annual"
    submit_tags_input(pane, form, "Work")
    pane.submit_form()

    assert list(app.income) == ["salary", "bonus"]
    assert app.saved_dataset is EntryType.INCOME

    pane.current_index = 1
    pane.start_delete_confirmation()
    pane.on_key(FakeKeyEvent("y"))

    assert list(app.income) == ["salary"]


def test_keyboard_shortcuts_drive_modal_entry_and_field_navigation() -> None:
    pane, app = build_pane()
    table = pane.query_one("#edit-table")
    form = pane.query_one(EntryForm)

    add_event = FakeKeyEvent("a")
    pane.on_key(add_event)

    name_input = form.query_one("#name-input")
    amount_input = form.query_one("#amount-input")
    frequency_input = form.query_one("#frequency-input")
    tags_input = form.query_one("#tags-input")

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

    pane.on_key(FakeKeyEvent("tab", character=""))
    assert app.focused is frequency_input

    pane.on_key(FakeKeyEvent("tab", character=""))
    assert app.focused is tags_input

    final_tab_event = FakeKeyEvent("tab", character="")
    pane.on_key(final_tab_event)
    assert final_tab_event.stopped
    assert final_tab_event.default_prevented
    assert app.focused is tags_input

    shift_tab_event = FakeKeyEvent("shift+tab", character="")
    pane.on_key(shift_tab_event)
    assert shift_tab_event.stopped
    assert shift_tab_event.default_prevented
    assert app.focused is frequency_input

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
    dialog = pane.query_one("#delete-confirm")
    pane.current_index = 1

    pane.start_delete_confirmation()

    assert pane.mode is EditMode.CONFIRM_DELETE
    assert not pane.query_one("#delete-confirm").has_class("hidden")
    assert "DELETE" in str(table.rows[1][0])
    assert dialog.renderable == "Delete this entry? (y/n)"

    pane.on_key(FakeKeyEvent("n"))

    assert pane.mode is EditMode.NAVIGATION
    assert list(app.expenses) == ["rent", "insurance"]
    assert pane.selected_name == "insurance"
    assert dialog.renderable == ""

    pane.start_delete_confirmation()
    pane.on_key(FakeKeyEvent("y"))

    assert pane.mode is EditMode.NAVIGATION
    assert list(app.expenses) == ["rent"]
    assert pane.selected_name == "rent"
    assert app.focused is table
    assert dialog.renderable == ""


def test_delete_confirmation_escape_cancels_without_mutating_entries() -> None:
    pane, app = build_pane()

    pane.current_index = 1
    pane.start_delete_confirmation()
    pane.on_key(FakeKeyEvent("escape", character=""))

    assert pane.mode is EditMode.NAVIGATION
    assert pane.selected_name == "insurance"
    assert list(app.expenses) == ["rent", "insurance"]


def test_submitted_input_advances_fields_and_empty_tag_submit_persists() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)

    name_input = form.query_one("#name-input")
    amount_input = form.query_one("#amount-input")
    frequency_input = form.query_one("#frequency-input")
    tags_input = form.query_one("#tags-input")
    name_input.value = "phone"
    amount_input.value = "25.00"

    pane.on_input_submitted(SimpleNamespace(input=name_input, stop=lambda: None))  # type: ignore[arg-type]
    assert app.focused is amount_input

    pane.on_input_submitted(SimpleNamespace(input=amount_input, stop=lambda: None))  # type: ignore[arg-type]
    assert app.focused is frequency_input

    pane.on_input_submitted(SimpleNamespace(input=frequency_input, stop=lambda: None))  # type: ignore[arg-type]
    assert app.focused is tags_input

    submit_tags_input(pane, form, "Bills")
    assert form.get_tags() == ["Bills"]

    pane.on_input_submitted(SimpleNamespace(input=tags_input, stop=lambda: None))  # type: ignore[arg-type]
    assert list(app.expenses) == ["rent", "phone", "insurance"]
    assert app.expenses["phone"].tags == ["Bills"]


def test_empty_state_edit_and_delete_show_messages_without_leaving_navigation() -> None:
    app = FakeApp({}, {})
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


def test_tag_autocomplete_tab_selects_highlighted_suggestion() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)
    tags_input = form.query_one("#tags-input")
    tags_input.focus()
    app.tag_registry.extend(["Food", "Fast Food", "Travel"])
    tags_input.value = "fo"

    pane.on_input_changed(SimpleNamespace(input=tags_input))  # type: ignore[arg-type]
    tab_event = FakeKeyEvent("tab", character="")
    pane.on_key(tab_event)

    assert tab_event.stopped
    assert tab_event.default_prevented
    assert form.get_tags() == ["Food"]
    assert tags_input.value == ""
    assert app.focused is tags_input


def test_enter_creates_new_tag_and_duplicate_additions_are_ignored() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)

    submit_tags_input(pane, form, "Weekend")
    assert form.get_tags() == ["Weekend"]
    assert "Weekend" in app.get_tag_registry()

    submit_tags_input(pane, form, "weekend")
    assert form.get_tags() == ["Weekend"]
    assert "Tag already added: Weekend." == pane.query_one("#edit-message").renderable


def test_escape_closes_suggestions_without_canceling_modal() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)
    tags_input = form.query_one("#tags-input")
    tags_input.focus()
    app.tag_registry.extend(["Food", "Fast Food"])
    tags_input.value = "fo"

    pane.on_input_changed(SimpleNamespace(input=tags_input))  # type: ignore[arg-type]
    pane.on_key(FakeKeyEvent("escape", character=""))

    assert pane.mode is EditMode.CREATE
    assert form.query_one("#tag-suggestions").has_class("hidden")
    assert tags_input.value == "fo"


def test_backspace_removes_last_attached_tag_when_input_is_empty() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)
    tags_input = form.query_one("#tags-input")

    form.set_tags(["Home", "Bills"])
    tags_input.focus()
    tags_input.value = ""

    pane.on_key(FakeKeyEvent("backspace", character=""))

    assert form.get_tags() == ["Home"]
    assert pane.query_one("#edit-message").renderable == "Removed tag: Bills."
    assert app.focused is tags_input


def test_adding_sixty_fifth_tag_is_blocked() -> None:
    pane, app = build_pane()
    pane.start_create()
    form = pane.query_one(EntryForm)
    form.set_tags([f"Tag {index}" for index in range(MAX_TAGS)])

    submit_tags_input(pane, form, "Overflow")

    assert len(form.get_tags()) == MAX_TAGS
    assert pane.query_one("#edit-message").renderable == (
        f"Tags must contain at most {MAX_TAGS} values."
    )
    assert "Overflow" not in app.get_tag_registry()
