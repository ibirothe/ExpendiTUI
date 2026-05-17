from __future__ import annotations

from types import SimpleNamespace

from expenditui.app import (
    EDIT_TAB,
    HELP_TAB,
    OVERVIEW_TAB,
    SETTINGS_TAB,
    ExpendiTUIApp,
)
from expenditui.models import EntryType


def test_bindings_expose_direct_tab_navigation_without_legacy_edit_actions() -> None:
    bindings = {binding.key: binding.action for binding in ExpendiTUIApp.BINDINGS}

    assert bindings["o"] == "show_overview"
    assert bindings["h"] == "show_help"
    assert bindings["e"] == "show_edit"
    assert bindings["s"] == "show_settings"
    assert bindings["/"] == "focus_overview_search"
    assert bindings["u"] == "toggle_overview_sort"
    assert bindings["enter"] == "open_overview_selection_in_edit"
    assert bindings["pageup"] == "scroll_active_page_up"
    assert bindings["pagedown"] == "scroll_active_page_down"
    assert bindings["r"] == "reload"
    assert bindings["t"] == "cycle_theme"
    assert bindings["escape"] == "back"
    assert "next_tab" not in bindings.values()
    assert "previous_tab" not in bindings.values()
    assert "add_entry" not in bindings.values()
    assert "delete_entry" not in bindings.values()
    assert "save_entries" not in bindings.values()


def test_direct_navigation_actions_switch_to_expected_tabs(monkeypatch) -> None:
    app = ExpendiTUIApp()
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
    app.action_show_settings()
    app.action_show_overview()

    assert switched_tabs == [EDIT_TAB, HELP_TAB, SETTINGS_TAB]
    assert overview_calls == 1


def test_reload_action_refreshes_loaded_state_and_views(monkeypatch) -> None:
    app = ExpendiTUIApp()
    calls: list[str] = []

    monkeypatch.setattr(app, "load_state", lambda: calls.append("load"))
    monkeypatch.setattr(
        app,
        "refresh_views",
        lambda *, sync_edit=False: calls.append(f"refresh:{sync_edit}"),
    )

    app.action_reload()

    assert calls == ["load", "refresh:True"]


def test_direct_tab_actions_are_hidden_only_for_active_tab() -> None:
    app = ExpendiTUIApp()

    app.active_tab_id = OVERVIEW_TAB
    assert app.check_action("show_overview", ()) is False
    assert app.check_action("show_edit", ()) is True
    assert app.check_action("show_help", ()) is True
    assert app.check_action("focus_overview_search", ()) is True
    assert app.check_action("toggle_overview_sort", ()) is True
    assert app.check_action("scroll_active_page_up", ()) is True
    assert app.check_action("scroll_active_page_down", ()) is True

    app.active_tab_id = EDIT_TAB
    assert app.check_action("show_overview", ()) is True
    assert app.check_action("show_edit", ()) is False
    assert app.check_action("show_help", ()) is True
    assert app.check_action("focus_overview_search", ()) is False
    assert app.check_action("toggle_overview_sort", ()) is False
    assert app.check_action("scroll_active_page_up", ()) is True
    assert app.check_action("scroll_active_page_down", ()) is True

    app.active_tab_id = HELP_TAB
    assert app.check_action("show_overview", ()) is True
    assert app.check_action("show_edit", ()) is True
    assert app.check_action("show_help", ()) is False
    assert app.check_action("focus_overview_search", ()) is False
    assert app.check_action("toggle_overview_sort", ()) is False
    assert app.check_action("scroll_active_page_up", ()) is True
    assert app.check_action("scroll_active_page_down", ()) is True

    app.active_tab_id = SETTINGS_TAB
    assert app.check_action("show_overview", ()) is True
    assert app.check_action("show_edit", ()) is True
    assert app.check_action("show_help", ()) is True
    assert app.check_action("show_settings", ()) is False
    assert app.check_action("focus_overview_search", ()) is False
    assert app.check_action("toggle_overview_sort", ()) is False
    assert app.check_action("scroll_active_page_up", ()) is True
    assert app.check_action("scroll_active_page_down", ()) is True
    assert app.check_action("back", ()) is True


def test_modal_edit_blocks_global_navigation_actions(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = EDIT_TAB

    monkeypatch.setattr(app, "edit_mode_blocks_global_actions", lambda: True)

    assert app.check_action("show_overview", ()) is False
    assert app.check_action("show_help", ()) is False
    assert app.check_action("show_settings", ()) is False
    assert app.check_action("scroll_active_page_up", ()) is False
    assert app.check_action("scroll_active_page_down", ()) is False
    assert app.check_action("reload", ()) is False
    assert app.check_action("focus_overview_search", ()) is False
    assert app.check_action("toggle_overview_sort", ()) is False
    assert app.check_action("back", ()) is False


def test_cycle_theme_action_respects_edit_form_blocking(monkeypatch) -> None:
    app = ExpendiTUIApp()

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: True)
    assert app.check_action("cycle_theme", ()) is False

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: False)
    assert app.check_action("cycle_theme", ()) is True


def test_settings_modal_blocks_global_navigation_actions(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = SETTINGS_TAB

    monkeypatch.setattr(app, "settings_mode_blocks_global_actions", lambda: True)

    assert app.check_action("show_overview", ()) is False
    assert app.check_action("show_help", ()) is False
    assert app.check_action("show_edit", ()) is False
    assert app.check_action("scroll_active_page_up", ()) is False
    assert app.check_action("scroll_active_page_down", ()) is False
    assert app.check_action("reload", ()) is False
    assert app.check_action("focus_overview_search", ()) is False
    assert app.check_action("toggle_overview_sort", ()) is False
    assert app.check_action("back", ()) is False


def test_cycle_theme_action_respects_settings_form_blocking(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = SETTINGS_TAB

    monkeypatch.setattr(app, "theme_switch_blocks_global_actions", lambda: True)
    assert app.check_action("cycle_theme", ()) is False


def test_tab_activation_stays_on_edit_when_modal_state_blocks_navigation(
    monkeypatch,
) -> None:
    app = ExpendiTUIApp()
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
    app = ExpendiTUIApp()
    overview = SimpleNamespace(
        refresh_view=lambda: overview_calls.append("overview"),
        hide_search=lambda **_kwargs: overview_calls.append("hide-search"),
    )
    tabs = SimpleNamespace(active=None)
    overview_calls: list[str] = []
    bindings_calls: list[str] = []

    def fake_query_one(selector, *_args):
        if selector == "#main-tabs":
            return tabs
        if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane":
            return overview
        raise AssertionError(f"Unexpected selector: {selector!r}")

    monkeypatch.setattr(app, "query_one", fake_query_one)
    monkeypatch.setattr(
        app, "refresh_bindings", lambda: bindings_calls.append(app.active_tab_id)
    )

    app.on_tabbed_content_tab_activated(SimpleNamespace(pane=SimpleNamespace(id=OVERVIEW_TAB)))  # type: ignore[arg-type]
    app.on_tabbed_content_tab_activated(SimpleNamespace(pane=SimpleNamespace(id=EDIT_TAB)))  # type: ignore[arg-type]

    assert overview_calls == ["overview", "hide-search"]
    assert bindings_calls == [OVERVIEW_TAB, EDIT_TAB]


def test_cycle_theme_action_updates_theme_and_refreshes_views(monkeypatch) -> None:
    app = ExpendiTUIApp()
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


def test_active_page_scroll_actions_target_active_tab(monkeypatch) -> None:
    app = ExpendiTUIApp()
    calls: list[str] = []
    overview = SimpleNamespace(
        page_up=lambda: calls.append("overview:up"),
        page_down=lambda: calls.append("overview:down"),
    )
    edit = SimpleNamespace(
        page_up=lambda: calls.append("edit:up"),
        page_down=lambda: calls.append("edit:down"),
    )
    help_pane = SimpleNamespace(
        scroll_page_up=lambda **kwargs: calls.append(f"up:{kwargs}"),
        scroll_page_down=lambda **kwargs: calls.append(f"down:{kwargs}"),
    )
    settings = SimpleNamespace(
        page_up=lambda: calls.append("settings:up"),
        page_down=lambda: calls.append("settings:down"),
    )

    def fake_query_one(selector, *_args):
        if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane":
            return overview
        if hasattr(selector, "__name__") and selector.__name__ == "EditPane":
            return edit
        if hasattr(selector, "__name__") and selector.__name__ == "HelpPane":
            return help_pane
        if hasattr(selector, "__name__") and selector.__name__ == "SettingsPane":
            return settings
        raise AssertionError(f"Unexpected selector: {selector!r}")

    monkeypatch.setattr(app, "query_one", fake_query_one)

    app.active_tab_id = OVERVIEW_TAB
    app.action_scroll_active_page_up()
    app.action_scroll_active_page_down()

    app.active_tab_id = EDIT_TAB
    app.action_scroll_active_page_up()
    app.action_scroll_active_page_down()

    app.active_tab_id = HELP_TAB
    app.action_scroll_active_page_up()
    app.action_scroll_active_page_down()

    app.active_tab_id = SETTINGS_TAB
    app.action_scroll_active_page_up()
    app.action_scroll_active_page_down()

    assert calls == [
        "overview:up",
        "overview:down",
        "edit:up",
        "edit:down",
        "up:{'animate': False}",
        "down:{'animate': False}",
        "settings:up",
        "settings:down",
    ]


def test_overview_search_action_focuses_overview_search(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = OVERVIEW_TAB
    calls: list[str] = []
    overview = SimpleNamespace(
        search_has_focus=False, focus_search=lambda: calls.append("focus")
    )

    monkeypatch.setattr(
        app,
        "query_one",
        lambda selector, *_args: (
            overview
            if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane"
            else None
        ),
    )

    app.action_focus_overview_search()

    assert calls == ["focus"]


def test_overview_sort_action_toggles_only_when_search_is_not_focused(
    monkeypatch,
) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = OVERVIEW_TAB
    calls: list[str] = []
    overview = SimpleNamespace(
        search_has_focus=False, toggle_sort_mode=lambda: calls.append("toggle")
    )

    monkeypatch.setattr(
        app,
        "query_one",
        lambda selector, *_args: (
            overview
            if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane"
            else None
        ),
    )

    assert app.check_action("toggle_overview_sort", ()) is True
    app.action_toggle_overview_sort()

    overview.search_has_focus = True
    assert app.check_action("toggle_overview_sort", ()) is False
    app.action_toggle_overview_sort()

    app.active_tab_id = EDIT_TAB
    app.action_toggle_overview_sort()

    assert calls == ["toggle"]


def test_back_exits_overview_search_before_tab_navigation(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = OVERVIEW_TAB
    calls: list[str] = []
    overview = SimpleNamespace(
        search_has_focus=True, hide_search=lambda: calls.append("hide")
    )

    monkeypatch.setattr(
        app,
        "query_one",
        lambda selector, *_args: (
            overview
            if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane"
            else None
        ),
    )
    monkeypatch.setattr(app, "switch_to_overview", lambda: calls.append("overview"))

    app.action_back()

    assert calls == ["hide"]


def test_open_overview_selection_switches_to_matching_edit_row(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = OVERVIEW_TAB
    calls: list[object] = []
    overview = SimpleNamespace(
        selected_entry_identity=(EntryType.INCOME, "salary"),
        hide_search=lambda **kwargs: calls.append(("hide", kwargs)),
    )
    edit = SimpleNamespace(
        select_entry=lambda entry_type, name: calls.append(("select", entry_type, name))
    )
    tabs = SimpleNamespace(active=None)

    def fake_query_one(selector, *_args):
        if selector == "#main-tabs":
            return tabs
        if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane":
            return overview
        if hasattr(selector, "__name__") and selector.__name__ == "EditPane":
            return edit
        raise AssertionError(f"Unexpected selector: {selector!r}")

    monkeypatch.setattr(app, "query_one", fake_query_one)
    monkeypatch.setattr(app, "refresh_bindings", lambda: calls.append("bindings"))

    app.open_overview_selection_in_edit()

    assert tabs.active == EDIT_TAB
    assert app.active_tab_id == EDIT_TAB
    assert calls == [
        ("hide", {"clear": True, "focus_table": False}),
        "bindings",
        ("select", EntryType.INCOME, "salary"),
    ]


def test_open_overview_selection_does_nothing_without_real_row(monkeypatch) -> None:
    app = ExpendiTUIApp()
    app.active_tab_id = OVERVIEW_TAB
    calls: list[str] = []
    overview = SimpleNamespace(selected_entry_identity=None)

    monkeypatch.setattr(
        app,
        "query_one",
        lambda selector, *_args: (
            overview
            if hasattr(selector, "__name__") and selector.__name__ == "OverviewPane"
            else calls.append("unexpected")
        ),
    )

    app.open_overview_selection_in_edit()

    assert app.active_tab_id == OVERVIEW_TAB
    assert calls == []
