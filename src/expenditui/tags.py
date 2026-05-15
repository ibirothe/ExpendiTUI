from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from unicodedata import category

from .constants import MAX_TAG_LENGTH


def normalize_tag_key(raw_tag: str) -> str:
    return raw_tag.strip().casefold()


def validate_tag(raw_tag: object) -> str:
    if not isinstance(raw_tag, str):
        raise ValueError("Each tag must be a string.")

    tag = raw_tag.strip()
    if not tag:
        raise ValueError("Tags must be non-empty strings.")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Tags must be at most {MAX_TAG_LENGTH} characters long.")
    if any(category(character) == "Cc" for character in tag):
        raise ValueError("Tags must not contain control characters.")
    return tag


@dataclass(slots=True)
class TagRegistry:
    _tags: dict[str, str] = field(default_factory=dict)

    def __init__(self, tags: Iterable[str] = ()) -> None:
        self._tags = {}
        self.extend(tags)

    def __contains__(self, raw_tag: object) -> bool:
        if not isinstance(raw_tag, str):
            return False
        return normalize_tag_key(raw_tag) in self._tags

    def __len__(self) -> int:
        return len(self._tags)

    def copy(self) -> TagRegistry:
        clone = TagRegistry()
        clone._tags = dict(self._tags)
        return clone

    def add(self, raw_tag: object) -> tuple[str, bool]:
        tag = validate_tag(raw_tag)
        tag_key = normalize_tag_key(tag)
        existing = self._tags.get(tag_key)
        if existing is not None:
            return existing, False
        self._tags[tag_key] = tag
        return tag, True

    def extend(self, tags: Iterable[str]) -> bool:
        changed = False
        for tag in tags:
            _, added = self.add(tag)
            changed = changed or added
        return changed

    def get(self, raw_tag: str) -> str | None:
        return self._tags.get(normalize_tag_key(raw_tag))

    def canonicalize(self, raw_tag: object) -> str:
        tag = validate_tag(raw_tag)
        return self._tags.get(normalize_tag_key(tag), tag)

    def canonicalize_many(self, tags: Iterable[str]) -> list[str]:
        canonical_tags: list[str] = []
        seen: set[str] = set()
        for raw_tag in tags:
            tag = self.canonicalize(raw_tag)
            tag_key = normalize_tag_key(tag)
            if tag_key in seen:
                continue
            seen.add(tag_key)
            canonical_tags.append(tag)
        return canonical_tags

    def suggestions(self, query: str, *, exclude: Iterable[str] = ()) -> list[str]:
        trimmed_query = query.strip()
        if not trimmed_query:
            return []

        query_key = normalize_tag_key(trimmed_query)
        excluded_keys = {normalize_tag_key(tag) for tag in exclude}
        prefix_matches: list[str] = []
        contains_matches: list[str] = []
        for tag_key, display_tag in self._tags.items():
            if tag_key in excluded_keys:
                continue
            if tag_key.startswith(query_key):
                prefix_matches.append(display_tag)
            elif query_key in tag_key:
                contains_matches.append(display_tag)

        key_fn = str.casefold
        return sorted(prefix_matches, key=key_fn) + sorted(
            contains_matches, key=key_fn
        )

    def to_list(self) -> list[str]:
        return sorted(self._tags.values(), key=str.casefold)
