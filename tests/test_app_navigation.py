from __future__ import annotations

from recurring_expenses_tui.app import EDIT_TAB, HELP_TAB, OVERVIEW_TAB, RecurringExpensesApp


def test_bindings_expose_direct_tab_navigation_without_legacy_edit_actions() -> None:
    bindings = {binding.key: binding.action for binding in RecurringExpensesApp.BINDINGS}

    assert bindings["o"] == "show_overview"
    assert bindings["h"] == "show_help"
    assert bindings["e"] == "show_edit"
    assert bindings["r"] == "reload"
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
