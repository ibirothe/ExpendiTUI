from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .models import EntryType, FinancialEntry


@dataclass(frozen=True, slots=True)
class FilteredEntry:
    entry_type: EntryType
    name: str
    entry: FinancialEntry


class EntryFilterService:
    @staticmethod
    def normalize_query(query: str) -> str:
        return query.strip().casefold()

    def filter_entries(
        self,
        *,
        expenses: Mapping[str, FinancialEntry],
        income: Mapping[str, FinancialEntry],
        query: str,
    ) -> list[FilteredEntry]:
        normalized_query = self.normalize_query(query)
        rows = [
            *self._rows_for_type(EntryType.EXPENSE, expenses),
            *self._rows_for_type(EntryType.INCOME, income),
        ]
        if not normalized_query:
            return rows
        return [
            row for row in rows if self._matches(row.name, row.entry, normalized_query)
        ]

    def _rows_for_type(
        self, entry_type: EntryType, entries: Mapping[str, FinancialEntry]
    ) -> list[FilteredEntry]:
        return [
            FilteredEntry(entry_type=entry_type, name=name, entry=entry)
            for name, entry in entries.items()
        ]

    def _matches(self, name: str, entry: FinancialEntry, normalized_query: str) -> bool:
        if normalized_query in name.casefold():
            return True
        return any(normalized_query in tag.casefold() for tag in entry.tags)
