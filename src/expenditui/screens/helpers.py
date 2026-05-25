from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Focusable(Protocol):
    def focus(self) -> None: ...


def focus_relative_field(
    fields: Sequence[Focusable],
    *,
    focused: object,
    direction: int,
) -> None:
    try:
        current_index = next(
            index for index, field in enumerate(fields) if field is focused
        )
    except StopIteration:
        current_index = 0

    target_index = max(0, min(current_index + direction, len(fields) - 1))
    fields[target_index].focus()


def message_color(app: object, kind: str) -> str:
    slot_name = {
        "success": "success",
        "error": "error",
        "accent": "accent",
        "muted": "muted",
    }.get(kind, "foreground")
    return app.theme_color(slot_name)


def refresh_app_bindings(app: object) -> None:
    refresh_bindings = getattr(app, "refresh_bindings", None)
    if callable(refresh_bindings):
        refresh_bindings()
