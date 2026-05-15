from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from platformdirs import user_config_path
from pydantic import ValidationError

from .constants import APP_NAME, DEFAULT_FILENAME, EMPTY_JSON_OBJECT
from .models import ExpenseEntry, dump_expense_mapping, validate_expense_mapping


class StorageError(Exception):
    """Raised when expense data cannot be loaded or saved."""


def get_expenses_path() -> Path:
    return user_config_path(APP_NAME) / DEFAULT_FILENAME


def ensure_storage_file(path: Path | None = None) -> Path:
    target = path or get_expenses_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_text(EMPTY_JSON_OBJECT, encoding="utf-8")
    except OSError as exc:
        raise StorageError(
            f"Could not prepare {target}: {exc.strerror or exc}."
        ) from exc
    return target


def load_expenses() -> dict[str, ExpenseEntry]:
    path = ensure_storage_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"Invalid JSON in {path}: {exc.msg} at line {exc.lineno}, column {exc.colno}."
        ) from exc
    except OSError as exc:
        raise StorageError(f"Could not read {path}: {exc.strerror or exc}.") from exc

    try:
        return validate_expense_mapping(data)
    except (ValidationError, ValueError) as exc:
        raise StorageError(f"Invalid expense data in {path}: {exc}.") from exc


def save_expenses(data: Mapping[str, ExpenseEntry]) -> None:
    path = ensure_storage_file()
    try:
        payload = dump_expense_mapping(data)
        path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    except (ValidationError, ValueError) as exc:
        raise StorageError(f"Could not save invalid expense data: {exc}.") from exc
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc.strerror or exc}.") from exc
