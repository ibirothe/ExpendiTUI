from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path

from .constants import APP_NAME

logger = logging.getLogger(__name__)

THEMES_FILENAME = "themes.json"
THEME_STATE_FILENAME = "ui-state.json"
THEME_SLOT_NAMES = (
    "background",
    "foreground",
    "surface",
    "accent",
    "success",
    "warning",
    "error",
    "muted",
)
HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
THEME_FORM_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_THEME_NAME_LENGTH = 64
BUILTIN_THEME_ROWS: tuple[tuple[str, ...], ...] = (
    (
        "Dreamy",
        "#FFF1E6",
        "#6D597A",
        "#F0EFEB",
        "#CDDAFD",
        "#BEE1E6",
        "#CEAE4E",
        "#B56576",
        "#E2ECE9",
    ),
    (
        "Sandstone",
        "#F1DDBF",
        "#525E75",
        "#CABEAD",
        "#85A78E",
        "#92BA92",
        "#B8845F",
        "#7D5A50",
        "#A29E9A",
    ),
    (
        "Nord",
        "#292929",
        "#CACBCD",
        "#2A2A2B",
        "#8AACCE",
        "#9EB889",
        "#E4C588",
        "#937791",
        "#6F7278",
    ),
)


@dataclass(frozen=True, slots=True)
class AppTheme:
    name: str
    background: str
    foreground: str
    surface: str
    accent: str
    success: str
    warning: str
    error: str
    muted: str

    @classmethod
    def from_row(cls, row: object, *, source: str) -> AppTheme:
        expected_length = len(THEME_SLOT_NAMES) + 1
        if not isinstance(row, list):
            raise ValueError(
                f"{source}: expected a list, received {type(row).__name__}."
            )
        if len(row) != expected_length:
            raise ValueError(
                f"{source}: expected {expected_length} entries, received {len(row)}."
            )
        name, *colors = row
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{source}: theme name must be a non-empty string.")
        validated_colors: list[str] = []
        for slot_name, color in zip(THEME_SLOT_NAMES, colors, strict=True):
            if not isinstance(color, str) or not HEX_COLOR_PATTERN.fullmatch(color):
                raise ValueError(f"{source}: invalid {slot_name} color {color!r}.")
            validated_colors.append(color)
        return cls(
            name=name.strip(),
            **dict(zip(THEME_SLOT_NAMES, validated_colors, strict=True)),
        )

    def color(self, slot_name: str) -> str:
        return getattr(self, slot_name)

    def blend(self, first_slot: str, second_slot: str, ratio: float) -> str:
        ratio = max(0.0, min(1.0, ratio))
        first = _hex_to_rgb(self.color(first_slot))
        second = _hex_to_rgb(self.color(second_slot))
        blended = tuple(
            round(first_value * ratio + second_value * (1.0 - ratio))
            for first_value, second_value in zip(first, second, strict=True)
        )
        return _rgb_to_hex(blended)

    def rich_style(
        self,
        foreground_slot: str,
        *,
        background_slot: str | None = None,
        bold: bool = False,
    ) -> str:
        parts: list[str] = []
        if bold:
            parts.append("bold")
        parts.append(self.color(foreground_slot))
        if background_slot is not None:
            parts.append(f"on {self.color(background_slot)}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class PersistedThemeSelection:
    name: str | None
    index: int | None


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    normalized = value.removeprefix("#")
    if len(normalized) == 3:
        normalized = "".join(character * 2 for character in normalized)
    if len(normalized) == 8:
        normalized = normalized[:6]
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _rgb_to_hex(value: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*value)


def get_config_dir() -> Path:
    return user_config_path(APP_NAME)


def get_themes_path() -> Path:
    return get_config_dir() / THEMES_FILENAME


def get_theme_state_path() -> Path:
    return get_config_dir() / THEME_STATE_FILENAME


class ThemeManager:
    def __init__(
        self,
        *,
        themes_path: Path | None = None,
        state_path: Path | None = None,
    ) -> None:
        self.themes_path = themes_path or get_themes_path()
        self.state_path = state_path or get_theme_state_path()
        self.themes = self._load_themes()
        self.active_index = 0
        self._restore_selection()

    @property
    def active_theme(self) -> AppTheme:
        return self.themes[self.active_index]

    def cycle_next(self) -> AppTheme:
        self.active_index = (self.active_index + 1) % len(self.themes)
        self.persist_selection()
        return self.active_theme

    def set_active(self, index: int) -> AppTheme:
        if not 0 <= index < len(self.themes):
            raise ValueError("Theme index is out of range.")
        self.active_index = index
        self.persist_selection()
        return self.active_theme

    def create_theme(
        self, name: str, colors: list[str] | tuple[str, ...], *, activate: bool = True
    ) -> AppTheme:
        theme = self._build_validated_theme(name, colors)
        updated_themes = [*self.themes, theme]
        self._persist_theme_list(updated_themes)
        self.themes = updated_themes
        if activate:
            self.active_index = len(self.themes) - 1
            self.persist_selection()
        return theme

    def update_theme(
        self, index: int, name: str, colors: list[str] | tuple[str, ...]
    ) -> AppTheme:
        if not 0 <= index < len(self.themes):
            raise ValueError("Theme index is out of range.")
        theme = self._build_validated_theme(name, colors, existing_index=index)
        updated_themes = list(self.themes)
        updated_themes[index] = theme
        self._persist_theme_list(updated_themes)
        self.themes = updated_themes
        if self.active_index == index:
            self.persist_selection()
        return theme

    def delete_theme(self, index: int) -> AppTheme:
        if not 0 <= index < len(self.themes):
            raise ValueError("Theme index is out of range.")
        if len(self.themes) <= 1:
            raise ValueError("At least one theme must remain.")

        updated_themes = list(self.themes)
        removed = updated_themes.pop(index)
        if index < self.active_index:
            next_active_index = self.active_index - 1
        elif index == self.active_index:
            next_active_index = min(index, len(updated_themes) - 1)
        else:
            next_active_index = self.active_index

        self._persist_theme_list(updated_themes)
        self.themes = updated_themes
        self.active_index = next_active_index
        self.persist_selection()
        return removed

    def persist_selection(self) -> None:
        payload = {
            "theme_name": self.active_theme.name,
            "theme_index": self.active_index,
        }
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                f"{json.dumps(payload, indent=2)}\n", encoding="utf-8"
            )
        except OSError as exc:
            logger.warning(
                "Could not persist theme selection to %s: %s",
                self.state_path,
                exc.strerror or exc,
            )

    def persist_themes(self) -> None:
        self._persist_theme_list(self.themes)

    def reset_to_builtins(self) -> None:
        builtin_themes = self._builtin_themes()
        self._persist_selection_strict(
            theme_name=builtin_themes[0].name,
            theme_index=0,
        )
        self.themes_path.unlink(missing_ok=True)
        self.themes = builtin_themes
        self.active_index = 0

    def _persist_theme_list(self, themes: list[AppTheme]) -> None:
        rows = [self._theme_to_row(theme) for theme in themes]
        payload = f"{json.dumps(rows, indent=2)}\n"
        self.themes_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.themes_path.with_name(f".{self.themes_path.name}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(self.themes_path)

    def _persist_selection_strict(
        self,
        *,
        theme_name: str | None = None,
        theme_index: int | None = None,
    ) -> None:
        payload = {
            "theme_name": self.active_theme.name if theme_name is None else theme_name,
            "theme_index": self.active_index if theme_index is None else theme_index,
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_name(f".{self.state_path.name}.tmp")
        temp_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
        temp_path.replace(self.state_path)

    def _build_validated_theme(
        self,
        name: str,
        colors: list[str] | tuple[str, ...],
        *,
        existing_index: int | None = None,
    ) -> AppTheme:
        normalized_name = self._validate_theme_name(name, existing_index)
        normalized_colors = self._validate_theme_colors(colors)
        return AppTheme(
            name=normalized_name,
            **dict(zip(THEME_SLOT_NAMES, normalized_colors, strict=True)),
        )

    def _validate_theme_name(self, name: str, existing_index: int | None = None) -> str:
        if not isinstance(name, str):
            raise ValueError("Theme name is required.")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Theme name is required.")
        if len(normalized_name) > MAX_THEME_NAME_LENGTH:
            raise ValueError(
                f"Theme name must be {MAX_THEME_NAME_LENGTH} characters or fewer."
            )
        normalized_key = normalized_name.casefold()
        for index, theme in enumerate(self.themes):
            if existing_index is not None and index == existing_index:
                continue
            if theme.name.casefold() == normalized_key:
                raise ValueError(f"Theme name '{normalized_name}' already exists.")
        return normalized_name

    def _validate_theme_colors(self, colors: list[str] | tuple[str, ...]) -> list[str]:
        if len(colors) != len(THEME_SLOT_NAMES):
            raise ValueError(f"Theme requires {len(THEME_SLOT_NAMES)} colors.")
        normalized_colors: list[str] = []
        for slot_name, color in zip(THEME_SLOT_NAMES, colors, strict=True):
            if not isinstance(color, str):
                raise ValueError(f"{slot_name.title()} color is required.")
            normalized_color = color.strip().upper()
            if not THEME_FORM_HEX_COLOR_PATTERN.fullmatch(normalized_color):
                raise ValueError(f"{slot_name.title()} must be a #RRGGBB hex color.")
            normalized_colors.append(normalized_color)
        return normalized_colors

    def _theme_to_row(self, theme: AppTheme) -> list[str]:
        return [
            theme.name,
            *(
                _rgb_to_hex(_hex_to_rgb(theme.color(slot_name)))
                for slot_name in THEME_SLOT_NAMES
            ),
        ]

    def _load_themes(self) -> list[AppTheme]:
        loaded = self._load_themes_from_file()
        if loaded:
            return loaded
        if self.themes_path.exists():
            logger.warning("Using built-in default themes.")
        else:
            logger.info("Using built-in default themes.")
        return self._builtin_themes()

    def _builtin_themes(self) -> list[AppTheme]:
        return [
            AppTheme.from_row(list(row), source=f"built-in theme {index}")
            for index, row in enumerate(BUILTIN_THEME_ROWS, start=1)
        ]

    def _load_themes_from_file(self) -> list[AppTheme]:
        if not self.themes_path.exists():
            logger.info(
                "Theme file %s does not exist; using built-in defaults.",
                self.themes_path,
            )
            return []

        try:
            data = json.loads(self.themes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(
                "Invalid JSON in %s: %s at line %s, column %s.",
                self.themes_path,
                exc.msg,
                exc.lineno,
                exc.colno,
            )
            return []
        except OSError as exc:
            logger.warning(
                "Could not read %s: %s", self.themes_path, exc.strerror or exc
            )
            return []

        if not isinstance(data, list):
            logger.warning("Theme file %s must contain a JSON array.", self.themes_path)
            return []

        themes: list[AppTheme] = []
        for row_index, row in enumerate(data, start=1):
            source = f"{self.themes_path} row {row_index}"
            try:
                themes.append(AppTheme.from_row(row, source=source))
            except ValueError as exc:
                logger.warning("Skipping invalid theme definition: %s", exc)

        if not themes:
            logger.warning(
                "Theme file %s did not contain any valid themes.", self.themes_path
            )
        return themes

    def _restore_selection(self) -> None:
        selection, should_reset = self._read_persisted_selection()
        resolved_index, matched = self._resolve_selection(selection)
        self.active_index = resolved_index
        if should_reset or (selection is not None and not matched):
            self.persist_selection()

    def _read_persisted_selection(self) -> tuple[PersistedThemeSelection | None, bool]:
        if not self.state_path.exists():
            return None, False

        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(
                "Invalid persisted theme state in %s: %s at line %s, column %s.",
                self.state_path,
                exc.msg,
                exc.lineno,
                exc.colno,
            )
            return None, True
        except OSError as exc:
            logger.warning(
                "Could not read %s: %s", self.state_path, exc.strerror or exc
            )
            return None, True

        if not isinstance(data, dict):
            logger.warning(
                "Persisted theme state in %s must be a JSON object.", self.state_path
            )
            return None, True

        name = data.get("theme_name")
        index = data.get("theme_index")
        if name is not None and not isinstance(name, str):
            logger.warning(
                "Persisted theme name in %s must be a string.", self.state_path
            )
            return None, True
        if index is not None and not isinstance(index, int):
            logger.warning(
                "Persisted theme index in %s must be an integer.", self.state_path
            )
            return None, True
        return PersistedThemeSelection(name=name, index=index), False

    def _resolve_selection(
        self, selection: PersistedThemeSelection | None
    ) -> tuple[int, bool]:
        if selection is None:
            return 0, True
        if selection.name:
            for index, theme in enumerate(self.themes):
                if theme.name == selection.name:
                    return index, True
        if selection.index is not None and 0 <= selection.index < len(self.themes):
            return selection.index, True
        logger.warning(
            "Persisted theme selection %r did not match the current theme set; falling back to index 0.",
            selection,
        )
        return 0, False
