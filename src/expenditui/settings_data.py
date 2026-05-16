from __future__ import annotations

from enum import Enum
from typing import Protocol

from .models import EntryType, FinancialEntry
from .storage import StorageError, save_entries, save_tag_registry
from .tags import TagRegistry


class SettingsDeletionCategory(str, Enum):
    DELETE_FINANCIAL_DATA = "delete_financial_data"
    DELETE_THEMES = "delete_themes"
    DELETE_VISUALIZATIONS = "delete_visualizations"
    DELETE_RECOMMENDED_TAGS = "delete_recommended_tags"


class _ThemeManager(Protocol):
    def reset_to_builtins(self) -> None: ...


class _VisualizationConfigManager(Protocol):
    def reset_to_default(self) -> None: ...


class _SettingsDataApp(Protocol):
    expenses: dict[str, FinancialEntry]
    income: dict[str, FinancialEntry]
    tag_registry: TagRegistry
    theme_manager: _ThemeManager
    visualization_manager: _VisualizationConfigManager
    last_error: str | None
    status_message: str | None
    status_message_kind: str

    def set_entries(
        self, entry_type: EntryType, entries: dict[str, FinancialEntry]
    ) -> None: ...

    def refresh_views(self, *, sync_edit: bool = False) -> None: ...

    def apply_theme(self, *, announce: bool = False) -> None: ...


class SettingsDataManager:
    """Coordinates destructive Settings data operations with UI state refreshes."""

    def __init__(self, app: _SettingsDataApp) -> None:
        self.app = app

    def delete_financial_data(self) -> None:
        save_entries(EntryType.EXPENSE, {})
        save_entries(EntryType.INCOME, {})
        self.app.set_entries(EntryType.EXPENSE, {})
        self.app.set_entries(EntryType.INCOME, {})
        self._set_success("Deleted financial data.")
        self.app.refresh_views(sync_edit=True)

    def delete_themes(self) -> None:
        self.app.theme_manager.reset_to_builtins()
        self._set_success("Reset themes to built-in defaults.")
        self.app.apply_theme(announce=True)
        self.app.refresh_views(sync_edit=False)

    def delete_visualizations(self) -> None:
        self.app.visualization_manager.reset_to_default()
        self._set_success("Reset visualizations to default configuration.")
        self.app.refresh_views(sync_edit=False)

    def delete_recommended_tags(self) -> None:
        registry = TagRegistry(self._collect_used_tags())
        save_tag_registry(registry)
        self.app.tag_registry = registry
        self._set_success("Deleted unused recommended tags.")
        self.app.refresh_views(sync_edit=False)

    def _collect_used_tags(self) -> list[str]:
        tags: list[str] = []
        for entry in (*self.app.expenses.values(), *self.app.income.values()):
            tags.extend(entry.tags)
        return tags

    def _set_success(self, message: str) -> None:
        self.app.last_error = None
        self.app.status_message = message
        self.app.status_message_kind = "success"


def format_deletion_error(exc: Exception) -> str:
    if isinstance(exc, StorageError):
        return str(exc)
    return str(exc) or exc.__class__.__name__
