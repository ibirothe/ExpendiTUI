from __future__ import annotations

from types import SimpleNamespace

from expenditui.screens.settings import (
    DraftTheme,
    SettingsMode,
    SettingsPane,
    ThemeDeleteDialog,
    ThemeForm,
)
from expenditui.theme import AppTheme, THEME_SLOT_NAMES


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


class FakeStatic:
    def __init__(self, app: "FakeApp") -> None:
        self.app = app
        self.renderable = ""
        self.hidden = False
        self.display = True
        self.styles = SimpleNamespace(color=None, background=None)

    def update(self, value: object) -> None:
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
        self.display = False
        self.inputs = {
            "#theme-name-input": FakeInput(app, "theme-name-input"),
            **{
                f"#theme-color-{slot_name}": FakeInput(
                    app, f"theme-color-{slot_name}"
                )
                for slot_name in THEME_SLOT_NAMES
            },
        }

    def query_one(self, selector: str, _cls: object | None = None) -> FakeInput:
        return self.inputs[selector]

    def set_draft(self, draft: DraftTheme) -> None:
        self.inputs["#theme-name-input"].value = draft.name
        for slot_name, color in zip(THEME_SLOT_NAMES, draft.colors, strict=True):
            self.inputs[f"#theme-color-{slot_name}"].value = color

    def get_draft(self) -> DraftTheme:
        return DraftTheme(
            name=self.inputs["#theme-name-input"].value,
            colors=[
                self.inputs[f"#theme-color-{slot_name}"].value
                for slot_name in THEME_SLOT_NAMES
            ],
        )

    def focus_first_field(self) -> None:
        self.inputs["#theme-name-input"].focus()

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
        return field.id == f"theme-color-{THEME_SLOT_NAMES[-1]}"

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

    def add_row(self, active: object, name: object, preview: object, *, key: str) -> None:
        self.rows.append((active, name, preview))

    def move_cursor(self, *, row: int, column: int, animate: bool = False) -> None:
        self.cursor_row = row

    def focus(self) -> None:
        self.app.focused = self

    def action_page_up(self) -> None:
        return None

    def action_page_down(self) -> None:
        return None


class FakeThemeManager:
    def __init__(self) -> None:
        self.themes = [
            AppTheme(
                name="Alpha",
                background="#101010",
                foreground="#EFEFEF",
                surface="#202020",
                accent="#3366FF",
                success="#22AA66",
                warning="#DD9900",
                error="#CC3344",
                muted="#888888",
            ),
            AppTheme(
                name="Beta",
                background="#111111",
                foreground="#EEEEEE",
                surface="#222222",
                accent="#2EC4B6",
                success="#22AA66",
                warning="#DD9900",
                error="#CC3344",
                muted="#888888",
            ),
        ]
        self.active_index = 0

    @property
    def active_theme(self) -> AppTheme:
        return self.themes[self.active_index]

    def create_theme(
        self, name: str, colors: list[str], *, activate: bool = True
    ) -> AppTheme:
        theme = AppTheme(
            name=name.strip(),
            **dict(zip(THEME_SLOT_NAMES, colors, strict=True)),
        )
        self.themes.append(theme)
        if activate:
            self.active_index = len(self.themes) - 1
        return theme

    def update_theme(self, index: int, name: str, colors: list[str]) -> AppTheme:
        theme = AppTheme(
            name=name.strip(),
            **dict(zip(THEME_SLOT_NAMES, colors, strict=True)),
        )
        self.themes[index] = theme
        return theme


class FakeApp:
    def __init__(self) -> None:
        self.focused: object | None = None
        self.theme_manager = FakeThemeManager()
        self.active_theme = self.theme_manager.active_theme
        self.refresh_bindings_calls = 0

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

    def refresh_bindings(self) -> None:
        self.refresh_bindings_calls += 1


class StubSettingsPane(SettingsPane):
    def __init__(self, app: FakeApp) -> None:
        self._test_app = app
        self._test_nodes = {
            "#settings-title": FakeStatic(app),
            "#theme-table": FakeTable(app),
            "#theme-delete-confirm": FakeDialog(app),
            "#settings-message": FakeStatic(app),
            ThemeForm: FakeForm(app),
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

    def query(self, selector: str) -> list[object]:
        return []


def build_pane() -> tuple[StubSettingsPane, FakeApp]:
    app = FakeApp()
    pane = StubSettingsPane(app)
    pane.refresh_theme_state()
    return pane, app


def test_navigation_mode_does_not_display_theme_form() -> None:
    pane, _app = build_pane()
    form = pane.query_one(ThemeForm)
    dialog = pane.query_one("#theme-delete-confirm")

    assert pane.mode is SettingsMode.NAVIGATION
    assert form.has_class("hidden")
    assert form.display is False
    assert dialog.has_class("hidden")
    assert dialog.display is False


def test_create_theme_form_stops_navigation_keys_without_blocking_input_default() -> None:
    pane, _app = build_pane()
    form = pane.query_one(ThemeForm)

    pane.start_create()
    event = FakeKeyEvent("o")
    pane.on_key(event)

    assert event.stopped
    assert not event.default_prevented
    assert pane.mode is SettingsMode.CREATE_THEME
    assert not form.has_class("hidden")
    assert form.display is True


def test_create_theme_form_does_not_swallow_backspace() -> None:
    pane, _app = build_pane()

    pane.start_create()
    event = FakeKeyEvent("backspace", character="")
    pane.on_key(event)

    assert not event.stopped
    assert not event.default_prevented
    assert pane.mode is SettingsMode.CREATE_THEME


def test_enter_saves_create_theme_form_from_any_field() -> None:
    pane, app = build_pane()
    form = pane.query_one(ThemeForm)

    pane.start_create()
    form.query_one("#theme-name-input").value = "Custom"
    event = FakeKeyEvent("enter", character="")
    pane.on_key(event)

    assert event.stopped
    assert event.default_prevented
    assert pane.mode is SettingsMode.NAVIGATION
    assert form.has_class("hidden")
    assert form.display is False
    assert app.theme_manager.themes[-1].name == "Custom"


def test_input_submitted_saves_theme_form_without_advancing_fields() -> None:
    pane, app = build_pane()
    form = pane.query_one(ThemeForm)
    submitted_event = SimpleNamespace(
        input=form.query_one("#theme-name-input"),
        stopped=False,
        stop=lambda: setattr(submitted_event, "stopped", True),
    )

    pane.start_create()
    form.query_one("#theme-name-input").value = "Submitted"
    pane.on_input_submitted(submitted_event)  # type: ignore[arg-type]

    assert submitted_event.stopped
    assert pane.mode is SettingsMode.NAVIGATION
    assert form.display is False
    assert app.theme_manager.themes[-1].name == "Submitted"


def test_edit_theme_form_stops_navigation_keys_without_blocking_input_default() -> None:
    pane, _app = build_pane()
    form = pane.query_one(ThemeForm)

    pane.start_edit()
    event = FakeKeyEvent("o")
    pane.on_key(event)

    assert event.stopped
    assert not event.default_prevented
    assert pane.mode is SettingsMode.EDIT_THEME
    assert not form.has_class("hidden")
    assert form.display is True


def test_delete_confirmation_hides_form_and_blocks_navigation_key_default() -> None:
    pane, _app = build_pane()
    form = pane.query_one(ThemeForm)

    pane.start_delete_confirmation()
    event = FakeKeyEvent("o")
    pane.on_key(event)

    assert event.stopped
    assert event.default_prevented
    assert pane.mode is SettingsMode.CONFIRM_DELETE_THEME
    assert form.has_class("hidden")
    assert form.display is False
