from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from platformdirs import user_config_path
from pydantic import ValidationError

from .constants import (
    APP_NAME,
    DEFAULT_TAGS,
    EMPTY_JSON_OBJECT,
    EXPENSES_FILENAME,
    INCOME_FILENAME,
    TAGS_FILENAME,
)
from .models import (
    EntryType,
    ExpenseEntry,
    FinancialEntry,
    IncomeEntry,
    ValidationError as ModelValidationError,
    dump_financial_mapping,
    normalize_entry_name,
)
from .tags import TagRegistry, normalize_tag_key, validate_tag

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadResult:
    entries: dict[str, FinancialEntry]
    diagnostics: list[str]


@dataclass(frozen=True, slots=True)
class TagLoadResult:
    registry: TagRegistry
    diagnostics: list[str]
    needs_save: bool = False


class StorageError(Exception):
    """Raised when entry data cannot be loaded or saved."""


def get_expenses_path() -> Path:
    return user_config_path(APP_NAME) / EXPENSES_FILENAME


def get_income_path() -> Path:
    return user_config_path(APP_NAME) / INCOME_FILENAME


def get_tags_path() -> Path:
    return user_config_path(APP_NAME) / TAGS_FILENAME


def get_dataset_path(entry_type: EntryType) -> Path:
    return get_expenses_path() if entry_type is EntryType.EXPENSE else get_income_path()


def ensure_storage_file(entry_type: EntryType, path: Path | None = None) -> Path:
    target = path or get_dataset_path(entry_type)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(EMPTY_JSON_OBJECT, encoding="utf-8")
    except OSError as exc:
        raise StorageError(
            f"Could not prepare {target}: {exc.strerror or exc}."
        ) from exc
    return target


def ensure_tag_directory(path: Path | None = None) -> Path:
    target = path or get_tags_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageError(
            f"Could not prepare {target.parent}: {exc.strerror or exc}."
        ) from exc
    return target


def load_entries(entry_type: EntryType) -> LoadResult:
    path = ensure_storage_file(entry_type)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}."
        ) from exc
    except OSError as exc:
        raise StorageError(f"Could not read {path}: {exc.strerror or exc}.") from exc

    if not isinstance(data, dict):
        raise StorageError(f"Invalid data in {path}: expected a JSON object.")

    validated: dict[str, FinancialEntry] = {}
    diagnostics: list[str] = []
    for raw_name, raw_entry in data.items():
        try:
            name = normalize_entry_name(raw_name)
            if name in validated:
                raise ValueError(f"Duplicate entry name: {name}")
            validated[name] = FinancialEntry.model_validate(raw_entry)
        except (ModelValidationError, ValueError) as exc:
            diagnostics.append(f"Skipped '{raw_name}': {exc}")

    if diagnostics:
        logger.warning(
            "Loaded %s with %d skipped entries: %s",
            path,
            len(diagnostics),
            "; ".join(diagnostics),
        )

    return LoadResult(entries=validated, diagnostics=diagnostics)


def save_entries(entry_type: EntryType, data: Mapping[str, FinancialEntry]) -> None:
    path = ensure_storage_file(entry_type)
    try:
        payload = dump_financial_mapping(data)
    except (ValidationError, ValueError) as exc:
        raise StorageError(f"Could not save invalid entry data: {exc}.") from exc

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(f"{json.dumps(payload, indent=2)}\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise StorageError(f"Could not write {path}: {exc.strerror or exc}.") from exc


def load_tag_registry() -> TagLoadResult:
    path = get_tags_path()
    registry = TagRegistry(DEFAULT_TAGS)
    diagnostics: list[str] = []
    needs_save = False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        message = f"Could not prepare {path.parent}: {exc.strerror or exc}."
        logger.warning(message)
        return TagLoadResult(registry=registry, diagnostics=[message], needs_save=False)

    if not path.exists():
        return TagLoadResult(registry=registry, diagnostics=[], needs_save=True)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = (
            f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, "
            f"column {exc.colno}."
        )
        logger.warning(message)
        return TagLoadResult(registry=registry, diagnostics=[message], needs_save=True)
    except OSError as exc:
        message = f"Could not read {path}: {exc.strerror or exc}."
        logger.warning(message)
        return TagLoadResult(registry=registry, diagnostics=[message], needs_save=False)

    if not isinstance(data, list):
        message = f"Invalid data in {path}: expected a JSON array."
        logger.warning(message)
        return TagLoadResult(registry=registry, diagnostics=[message], needs_save=True)

    seen: set[str] = set()
    file_tag_keys: set[str] = set()
    for index, raw_tag in enumerate(data, start=1):
        try:
            tag = validate_tag(raw_tag)
            canonical, added = registry.add(tag)
            if not added and canonical != tag:
                needs_save = True
            tag_key = normalize_tag_key(tag)
            if tag_key in seen:
                needs_save = True
            seen.add(tag_key)
            file_tag_keys.add(tag_key)
        except ValueError as exc:
            diagnostics.append(f"Skipped tag {index} from {path.name}: {exc}")
            needs_save = True

    if any(normalize_tag_key(tag) not in file_tag_keys for tag in DEFAULT_TAGS):
        needs_save = True

    if diagnostics:
        logger.warning(
            "Loaded %s with %d skipped tags: %s",
            path,
            len(diagnostics),
            "; ".join(diagnostics),
        )

    return TagLoadResult(
        registry=registry,
        diagnostics=diagnostics,
        needs_save=needs_save,
    )


def save_tag_registry(registry: TagRegistry) -> None:
    path = ensure_tag_directory()
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(f"{json.dumps(registry.to_list(), indent=2)}\n")
            temp_path = Path(handle.name)
        temp_path.replace(path)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise StorageError(f"Could not write {path}: {exc.strerror or exc}.") from exc


def load_expenses() -> dict[str, ExpenseEntry]:
    return load_entries(EntryType.EXPENSE).entries


def load_income() -> dict[str, IncomeEntry]:
    return load_entries(EntryType.INCOME).entries


def save_expenses(data: Mapping[str, ExpenseEntry]) -> None:
    save_entries(EntryType.EXPENSE, data)


def save_income(data: Mapping[str, IncomeEntry]) -> None:
    save_entries(EntryType.INCOME, data)
