from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .models import EntryType, FinancialEntry
from .storage import (
    StorageError,
    get_dataset_path,
    load_entries,
    load_tag_registry,
    save_entries,
    save_tag_registry,
)
from .tags import TagRegistry


class _StateOwner(Protocol):
    expenses: dict[str, FinancialEntry]
    income: dict[str, FinancialEntry]
    tag_registry: TagRegistry
    last_error: str | None
    status_message: str | None
    status_message_kind: str


class AppStateService:
    """Coordinates app-owned financial state with persistent storage."""

    def __init__(self, owner: _StateOwner) -> None:
        self.owner = owner

    def load_state(self) -> str | None:
        diagnostics: list[str] = []
        loaded_any = False
        for entry_type in EntryType:
            try:
                result = load_entries(entry_type)
                self.set_entries(entry_type, result.entries)
                loaded_any = True
                if result.diagnostics:
                    count = len(result.diagnostics)
                    noun = "entry" if count == 1 else "entries"
                    diagnostics.append(
                        f"{entry_type.display_name}: skipped {count} invalid {noun} from {get_dataset_path(entry_type)}."
                    )
            except StorageError as exc:
                self.set_entries(entry_type, {})
                diagnostics.append(str(exc))

        tag_result = load_tag_registry()
        tag_registry = tag_result.registry
        tag_registry_changed = tag_registry.extend(self.collect_all_tags())
        if tag_result.diagnostics:
            diagnostics.extend(tag_result.diagnostics)
        if tag_result.needs_save or tag_registry_changed:
            try:
                save_tag_registry(tag_registry)
            except StorageError as exc:
                diagnostics.append(str(exc))
        self.owner.tag_registry = tag_registry

        self.owner.last_error = " | ".join(diagnostics) if diagnostics else None
        if loaded_any:
            self.owner.status_message = "Loaded expense and income entries."
            self.owner.status_message_kind = "success"
        else:
            self.owner.status_message = None
        return self.owner.last_error

    def save_state(
        self, entry_type: EntryType, data: dict[str, FinancialEntry]
    ) -> str | None:
        updated_tag_registry = self.owner.tag_registry.copy()
        updated_tag_registry.extend(self.collect_tags(data.values()))
        try:
            if updated_tag_registry.to_list() != self.owner.tag_registry.to_list():
                save_tag_registry(updated_tag_registry)
                self.owner.tag_registry = updated_tag_registry
            save_entries(entry_type, data)
            self.set_entries(entry_type, load_entries(entry_type).entries)
            self.owner.tag_registry = updated_tag_registry
            self.owner.last_error = None
            self.owner.status_message = (
                f"Saved {entry_type.plural_name} to {get_dataset_path(entry_type)}."
            )
            self.owner.status_message_kind = "success"
        except StorageError as exc:
            self.owner.last_error = str(exc)
            self.owner.status_message = None
        return self.owner.last_error

    def get_entries(self, entry_type: EntryType) -> dict[str, FinancialEntry]:
        return (
            self.owner.expenses
            if entry_type is EntryType.EXPENSE
            else self.owner.income
        )

    def set_entries(
        self, entry_type: EntryType, entries: dict[str, FinancialEntry]
    ) -> None:
        if entry_type is EntryType.EXPENSE:
            self.owner.expenses = entries
        else:
            self.owner.income = entries

    def ensure_global_tag(self, raw_tag: str) -> tuple[str | None, str | None]:
        updated_registry = self.owner.tag_registry.copy()
        try:
            canonical_tag, _changed = updated_registry.add(raw_tag)
            if updated_registry.to_list() != self.owner.tag_registry.to_list():
                save_tag_registry(updated_registry)
            self.owner.tag_registry = updated_registry
        except (StorageError, ValueError) as exc:
            self.owner.last_error = str(exc)
            self.owner.status_message = None
            return None, self.owner.last_error
        return canonical_tag, None

    def collect_all_tags(self) -> list[str]:
        tags: list[str] = []
        tags.extend(self.collect_tags(self.owner.expenses.values()))
        tags.extend(self.collect_tags(self.owner.income.values()))
        return tags

    @staticmethod
    def collect_tags(entries: Iterable[FinancialEntry]) -> list[str]:
        tags: list[str] = []
        for entry in entries:
            tags.extend(entry.tags)
        return tags
