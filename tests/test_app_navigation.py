from __future__ import annotations

from types import SimpleNamespace

from recurring_expenses_tui.app import (
    EDIT_TAB,
    HELP_TAB,
    OVERVIEW_TAB,
    RecurringExpensesApp,
)


def test_bindings_expose_direct_tab_navigation_without_legacy_edit_actions() -> None:
    bindings = {
        binding.key: binding.action for binding in RecurringExpensesApp.BINDINGS
    }

    assert bindings["o"] == "show_overview"
    assert bindings["h"] == "show_help"
    assert bindings["e"] == "show_edit"
    assert bindings["r"] == "reload"
    assert bindings["t"] == "cycle_theme"
    assert bindings["escape"] == "back"
    assert "next_tab" not in bindings.values()
    assert "previous_tab" not in bindings.values()
    assert "add_entry" not in bindings.values()
    assert "delete_entry" not in bindings.values()
    assert "save_entries" not in bindings.values()


def test_direct_navigation_actions_switch_to_expected_tabs(monkeypatch) -> None:
    app = RecurringExpensesApp()
    switched_tabs: list[str] = []
    overview_calls = 0

    def switch_to_tab(tab_id: str) -> None:
        switched_tabs.append(tab_id)

    def switch_to_overview() -> None:
        nonlocal overview_calls
        overview_calls += 1

    monkeypatch.setattr(app, "switch_to_tab", switch_to_tab)
    monkeypatch.setattr(app, "switch_to_overview", switch_to_overview)

    app.action_show_edit()
    app.action_show_help()
    app.action_show_overview()

    assert switched_tabs == [EDIT_TAB, HELP_TAB]
    assert overview_calls == 1


def test_direct_tab_actions_are_hidden_only_for_active_tab() -> None:
    app = RecurringExpensesApp()

    app.active_tab_id = OVERVIEW_TAB
    assert app.check_action("show_overview", ()) is False
    assert app.check_action("show_edit", ()) is True
    assert app.check_action("show_help", ()) is True

    app.active_tab_id = EDIT_TAB
    assert app.check_action("show_overview", ()) is True
    assert app.check_action("show_edit", ()) is False
    assert app.check_action("show_help", ()) is True

    app.active_tab_id = HELP_TAB
    assert app.check_action("show_overview", ()) is True
    assert app.check_action("show_edit", ()) is True
    assert app.check_action("show_help", ()) is False


def test_modal_edit_blocks_global_navigation_actions(monkeypatch) -> None:
    app = RecurringExpensesApp()
    app.active_tab_id = EDIT_TAB

    monkeypatch.setattr(app, "edit_mode_blocks_global_actions", lambda: True)

    assert app.check_action("show_overview", ()) is False
    assert app.check_action("show_help", ()) is False
    assert app.check_action("reload", ()) is False
    assert app.check_action("back", ()) is False


def test_cycle_theme_action_respects_edit_form_blocking(monkeypatch) -> None:
    app = RecurringExpensesApp()

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: True)
    assert app.check_action("cycle_theme", ()) is False

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: False)
    assert app.check_action("cycle_theme", ()) is True


def test_tab_activation_stays_on_edit_when_modal_state_blocks_navigation(
    monkeypatch,
) -> None:
    app = RecurringExpensesApp()
    tabs = SimpleNamespace(active=EDIT_TAB)
    app.active_tab_id = EDIT_TAB

    monkeypatch.setattr(app, "edit_mode_blocks_global_actions", lambda: True)
    monkeypatch.setattr(
        app,
        "query_one",
        lambda selector, *_args: tabs if selector == "#main-tabs" else None,
    )

    event = SimpleNamespace(pane=SimpleNamespace(id=HELP_TAB))
    app.on_tabbed_content_tab_activated(event)  # type: ignore[arg-type]

    assert tabs.active == EDIT_TAB
    assert app.active_tab_id == EDIT_TAB


def test_tab_activation_refreshes_destination_view_and_bindings(monkeypatch) -> None:
    app = RecurringExpensesApp()
    overview = SimpleNamespace(refresh_view=lambda: overview_calls.append("overview"))
    edit = SimpleNamespace(focus_table=lambda: edit_calls.append("edit"))
    tabs = SimpleNamespace(active=None)
    overview_calls: list[str] = []
    edit_calls: list[str] = []
    bindings_calls: list[str] = []

    def fake_query_one(selector, *_args):
        if selector == "#main-tabs":
            return tabs
        if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane":
            return overview
        if hasattr(selector, "__name__") and selector.__name__ == "EditPane":
            return edit
        raise AssertionError(f"Unexpected selector: {selector!r}")

    monkeypatch.setattr(app, "query_one", fake_query_one)
    monkeypatch.setattr(
        app, "refresh_bindings", lambda: bindings_calls.append(app.active_tab_id)
    )

    app.on_tabbed_content_tab_activated(SimpleNamespace(pane=SimpleNamespace(id=OVERVIEW_TAB)))  # type: ignore[arg-type]
    app.on_tabbed_content_tab_activated(SimpleNamespace(pane=SimpleNamespace(id=EDIT_TAB)))  # type: ignore[arg-type]

    assert overview_calls == ["overview"]
    assert edit_calls == ["edit"]
    assert bindings_calls == [OVERVIEW_TAB, EDIT_TAB]


def test_cycle_theme_action_updates_theme_and_refreshes_views(monkeypatch) -> None:
    app = RecurringExpensesApp()
    calls: list[str] = []

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: False)
    monkeypatch.setattr(app.theme_manager, "cycle_next", lambda: calls.append("cycle"))
    monkeypatch.setattr(
        app, "apply_theme", lambda announce=False: calls.append(f"apply:{announce}")
    )
    monkeypatch.setattr(
        app,
        "refresh_views",
        lambda *, sync_edit=False: calls.append(f"refresh:{sync_edit}"),
    )
    monkeypatch.setattr(app, "refresh_bindings", lambda: calls.append("bindings"))

    app.action_cycle_theme()

    assert calls == ["cycle", "apply:True", "refresh:False", "bindings"]
