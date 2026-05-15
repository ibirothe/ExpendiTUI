from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from platformdirs import user_config_path
from rich.cells import cell_len
from rich.text import Text

from .calculations import monthly_equivalent, savings_monthly, total_monthly
from .constants import APP_NAME, ROUNDING_MODE, VISUALIZATIONS_FILENAME
from .models import FinancialEntry
from .tags import normalize_tag_key
from .theme import THEME_SLOT_NAMES

logger = logging.getLogger(__name__)

DEFAULT_VISUALIZATION_TYPE = "income_vs_expense"
KNOWN_VISUALIZATION_TYPES = frozenset(
    {
        DEFAULT_VISUALIZATION_TYPE,
        "tag_distribution",
        "savings",
    }
)
DEFAULT_PANEL_ID = "income-expense"
DEFAULT_MAX_WIDTH = 20
DEFAULT_MAX_LEGEND_ENTRIES = 6
DEFAULT_OTHERS_THRESHOLD = 0.05
DEFAULT_MULTI_TAG_STRATEGY = "split_equally"
DEFAULT_INCOME_SYMBOL = "█"
DEFAULT_EXPENSE_SYMBOL = "█"
DEFAULT_SAVINGS_SYMBOL = "█"
DEFAULT_OTHERS_SYMBOL = "·"
DEFAULT_SEGMENT_SYMBOL = "▮"
DEFAULT_OVERVIEW_ENABLED = True
DEFAULT_SHOW_LABELS = True
DEFAULT_TAG_COLOR_SLOTS = ("warning", "accent", "success", "error", "foreground")
DEFAULT_OTHERS_COLOR_SLOT = "muted"
OTHERS_LABEL = "Others"
NO_DATA_MESSAGE = "No financial data available."
NO_SPACE_MESSAGE = "No space available for visualization."


def get_visualizations_path() -> Path:
    return user_config_path(APP_NAME) / VISUALIZATIONS_FILENAME


@dataclass(frozen=True, slots=True)
class OverviewVisualizationConfig:
    id: str = DEFAULT_PANEL_ID
    enabled: bool = True
    type: str = DEFAULT_VISUALIZATION_TYPE
    max_width: int = DEFAULT_MAX_WIDTH
    income_symbol: str = DEFAULT_INCOME_SYMBOL
    expense_symbol: str = DEFAULT_EXPENSE_SYMBOL
    savings_symbol: str = DEFAULT_SAVINGS_SYMBOL
    others_symbol: str = DEFAULT_OTHERS_SYMBOL
    segment_symbol: str = DEFAULT_SEGMENT_SYMBOL
    show_labels: bool = DEFAULT_SHOW_LABELS
    max_legend_entries: int = DEFAULT_MAX_LEGEND_ENTRIES
    others_threshold: float = DEFAULT_OTHERS_THRESHOLD
    multi_tag_strategy: str = DEFAULT_MULTI_TAG_STRATEGY
    group_by: str | None = None
    tag_color_slots: tuple[str, ...] = DEFAULT_TAG_COLOR_SLOTS
    others_color_slot: str = DEFAULT_OTHERS_COLOR_SLOT


@dataclass(frozen=True, slots=True)
class VisualizationConfig:
    overview_enabled: bool
    overview_visualizations: tuple[OverviewVisualizationConfig, ...]

    @classmethod
    def default(cls) -> VisualizationConfig:
        return cls(
            overview_enabled=DEFAULT_OVERVIEW_ENABLED,
            overview_visualizations=(OverviewVisualizationConfig(),),
        )

    @property
    def enabled_visualizations(self) -> tuple[OverviewVisualizationConfig, ...]:
        if not self.overview_enabled:
            return ()
        return tuple(panel for panel in self.overview_visualizations if panel.enabled)


class VisualizationConfigManager:
    def __init__(self, *, path: Path | None = None) -> None:
        self.path = path or get_visualizations_path()
        self.config = self._load()

    def reload(self) -> VisualizationConfig:
        self.config = self._load()
        return self.config

    def _load(self) -> VisualizationConfig:
        if not self.path.exists():
            logger.info(
                "Visualization config %s does not exist; using defaults.",
                self.path,
            )
            return VisualizationConfig.default()

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(
                "Invalid JSON in %s: %s at line %s, column %s.",
                self.path,
                exc.msg,
                exc.lineno,
                exc.colno,
            )
            return VisualizationConfig.default()
        except OSError as exc:
            logger.warning(
                "Could not read %s: %s",
                self.path,
                exc.strerror or exc,
            )
            return VisualizationConfig.default()

        if not isinstance(data, dict):
            logger.warning(
                "Visualization config %s must contain a JSON object.",
                self.path,
            )
            return VisualizationConfig.default()

        return self._parse_config(data)

    def _parse_config(self, data: Mapping[str, object]) -> VisualizationConfig:
        overview_data = data.get("overview")
        if overview_data is None:
            return VisualizationConfig.default()
        if not isinstance(overview_data, Mapping):
            logger.warning("Visualization config field 'overview' must be an object.")
            return VisualizationConfig.default()

        overview_enabled = _parse_bool(
            overview_data.get("enabled"),
            default=DEFAULT_OVERVIEW_ENABLED,
        )

        visualization_rows = overview_data.get("visualizations")
        panels: list[OverviewVisualizationConfig] = []
        if visualization_rows is not None:
            if not isinstance(visualization_rows, list):
                logger.warning(
                    "Visualization config field 'overview.visualizations' must be an array."
                )
            else:
                for index, raw_panel in enumerate(visualization_rows, start=1):
                    if not isinstance(raw_panel, Mapping):
                        logger.warning(
                            "Skipping invalid visualization panel %s: expected an object.",
                            index,
                        )
                        continue
                    panels.append(
                        self._parse_panel(
                            raw_panel,
                            source=f"{self.path} overview.visualizations[{index}]",
                        )
                    )

        if not panels:
            panels = [
                self._parse_panel(
                    overview_data,
                    source=f"{self.path} overview",
                    default_id=DEFAULT_PANEL_ID,
                )
            ]

        return VisualizationConfig(
            overview_enabled=overview_enabled,
            overview_visualizations=tuple(panels),
        )

    def _parse_panel(
        self,
        data: Mapping[str, object],
        *,
        source: str,
        default_id: str = DEFAULT_PANEL_ID,
    ) -> OverviewVisualizationConfig:
        return OverviewVisualizationConfig(
            id=_parse_non_empty_string(data.get("id"), default=default_id),
            enabled=_parse_bool(data.get("enabled"), default=True),
            type=_parse_visualization_type(data.get("type"), source=source),
            max_width=_parse_positive_int(
                data.get("maxWidth"),
                default=DEFAULT_MAX_WIDTH,
                source=f"{source}.maxWidth",
            ),
            income_symbol=_parse_symbol(
                data.get("incomeSymbol"),
                default=DEFAULT_INCOME_SYMBOL,
                source=f"{source}.incomeSymbol",
            ),
            expense_symbol=_parse_symbol(
                data.get("expenseSymbol"),
                default=DEFAULT_EXPENSE_SYMBOL,
                source=f"{source}.expenseSymbol",
            ),
            savings_symbol=_parse_symbol(
                data.get("savingsSymbol"),
                default=DEFAULT_SAVINGS_SYMBOL,
                source=f"{source}.savingsSymbol",
            ),
            others_symbol=_parse_symbol(
                data.get("othersSymbol"),
                default=DEFAULT_OTHERS_SYMBOL,
                source=f"{source}.othersSymbol",
            ),
            segment_symbol=_parse_symbol(
                data.get("segmentSymbol"),
                default=DEFAULT_SEGMENT_SYMBOL,
                source=f"{source}.segmentSymbol",
            ),
            show_labels=_parse_bool(
                data.get("showLabels"),
                default=DEFAULT_SHOW_LABELS,
            ),
            max_legend_entries=_parse_positive_int(
                data.get("maxLegendEntries"),
                default=DEFAULT_MAX_LEGEND_ENTRIES,
                source=f"{source}.maxLegendEntries",
            ),
            others_threshold=_parse_probability(
                data.get("othersThreshold"),
                default=DEFAULT_OTHERS_THRESHOLD,
                source=f"{source}.othersThreshold",
            ),
            multi_tag_strategy=_parse_multi_tag_strategy(
                data.get("multiTagStrategy"),
                source=source,
            ),
            group_by=_parse_optional_string(data.get("groupBy")),
            tag_color_slots=_parse_color_slots(
                data.get("tagColorSlots"),
                default=DEFAULT_TAG_COLOR_SLOTS,
                source=f"{source}.tagColorSlots",
            ),
            others_color_slot=_parse_color_slot(
                data.get("othersColorSlot"),
                default=DEFAULT_OTHERS_COLOR_SLOT,
                source=f"{source}.othersColorSlot",
            ),
        )


@dataclass(frozen=True, slots=True)
class VisualizationContext:
    income_entries: Mapping[str, FinancialEntry]
    expense_entries: Mapping[str, FinancialEntry]
    income_total: Decimal
    expense_total: Decimal
    savings_total: Decimal
    config: OverviewVisualizationConfig
    available_width: int
    filters: Mapping[str, object] | None = None
    style_for_slot: Callable[[str], str] | None = None


@dataclass(frozen=True, slots=True)
class VisualizationResult:
    lines: tuple[Text, ...]
    legend: tuple[Text, ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> VisualizationResult:
        return cls(lines=())


@dataclass(frozen=True, slots=True)
class TagDistributionBucket:
    key: str
    label: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class _BarItem:
    label: str
    compact_label: str
    symbol: str
    value: Decimal
    style_slot: str


@dataclass(frozen=True, slots=True)
class _DistributionItem:
    label: str
    symbol: str
    value: Decimal
    style_slot: str


class VisualizationStrategy(Protocol):
    type: str

    def render(self, context: VisualizationContext) -> VisualizationResult: ...


class IncomeExpenseVisualizationStrategy:
    type = DEFAULT_VISUALIZATION_TYPE

    def render(self, context: VisualizationContext) -> VisualizationResult:
        if context.income_total <= 0 and context.expense_total <= 0:
            return VisualizationResult(lines=(Text(NO_DATA_MESSAGE),))

        items = (
            _BarItem(
                label="Income",
                compact_label="I",
                symbol=context.config.income_symbol,
                value=context.income_total,
                style_slot="success",
            ),
            _BarItem(
                label="Expenditure",
                compact_label="E",
                symbol=context.config.expense_symbol,
                value=context.expense_total,
                style_slot="warning",
            ),
        )
        return _render_bar_items(
            items,
            context=context,
            max_segments=context.config.max_width,
            show_labels=context.config.show_labels,
        )


class TagDistributionVisualizationStrategy:
    type = "tag_distribution"

    def render(self, context: VisualizationContext) -> VisualizationResult:
        buckets = aggregate_tag_distribution(context.expense_entries, context.config)
        if not buckets:
            return VisualizationResult(lines=(Text(NO_DATA_MESSAGE),))

        return _render_distribution(
            _distribution_items_from_buckets(buckets, context.config),
            context=context,
            max_segments=context.config.max_width,
        )


class VisualizationRenderer:
    def __init__(
        self,
        *,
        strategies: Sequence[VisualizationStrategy] | None = None,
    ) -> None:
        strategy_rows = strategies or (
            IncomeExpenseVisualizationStrategy(),
            TagDistributionVisualizationStrategy(),
        )
        self._strategies = {strategy.type: strategy for strategy in strategy_rows}

    def render(
        self,
        *,
        config: VisualizationConfig,
        income_entries: Mapping[str, FinancialEntry],
        expense_entries: Mapping[str, FinancialEntry],
        available_width: int,
        filters: Mapping[str, object] | None = None,
        style_for_slot: Callable[[str], str] | None = None,
    ) -> VisualizationResult:
        if not config.overview_enabled:
            return VisualizationResult.empty()

        panel = self._select_panel(config)
        if panel is None:
            return VisualizationResult.empty()

        context = VisualizationContext(
            income_entries=income_entries,
            expense_entries=expense_entries,
            income_total=total_monthly(income_entries),
            expense_total=total_monthly(expense_entries),
            savings_total=savings_monthly(income_entries, expense_entries),
            config=panel,
            available_width=max(0, available_width),
            filters=filters,
            style_for_slot=style_for_slot,
        )

        strategy = self._strategies.get(panel.type)
        if strategy is None:
            logger.warning(
                "Unsupported visualization type %r; falling back to %s.",
                panel.type,
                DEFAULT_VISUALIZATION_TYPE,
            )
            strategy = self._strategies[DEFAULT_VISUALIZATION_TYPE]

        try:
            return strategy.render(context)
        except Exception:
            logger.exception("Visualization rendering failed for type %s.", panel.type)
            if panel.type == DEFAULT_VISUALIZATION_TYPE:
                return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))
            fallback_panel = OverviewVisualizationConfig()
            fallback_context = VisualizationContext(
                income_entries=context.income_entries,
                expense_entries=context.expense_entries,
                income_total=context.income_total,
                expense_total=context.expense_total,
                savings_total=context.savings_total,
                config=fallback_panel,
                available_width=context.available_width,
                filters=context.filters,
                style_for_slot=context.style_for_slot,
            )
            return self._strategies[DEFAULT_VISUALIZATION_TYPE].render(fallback_context)

    def _select_panel(
        self, config: VisualizationConfig
    ) -> OverviewVisualizationConfig | None:
        enabled_panels = config.enabled_visualizations
        if not enabled_panels:
            return None

        for panel in enabled_panels:
            if panel.type in self._strategies:
                return panel

        logger.warning(
            "No enabled visualization panels use a supported renderer; using default overview visualization."
        )
        return OverviewVisualizationConfig()


def aggregate_tag_distribution(
    entries: Mapping[str, FinancialEntry],
    config: OverviewVisualizationConfig,
) -> tuple[TagDistributionBucket, ...]:
    totals: dict[str, tuple[str, Decimal]] = {}
    others_key = normalize_tag_key(OTHERS_LABEL)

    for entry in entries.values():
        amount = monthly_equivalent(entry.amount, entry.frequency)
        if amount <= 0:
            continue

        normalized_tags = _normalize_distribution_tags(entry.tags)
        target_tags = normalized_tags or [OTHERS_LABEL]
        share = amount / Decimal(len(target_tags))

        for tag in target_tags:
            key = normalize_tag_key(tag)
            label = OTHERS_LABEL if not normalized_tags else tag
            existing_label, existing_amount = totals.get(key, (label, Decimal("0")))
            totals[key] = (existing_label, existing_amount + share)

    if not totals:
        return ()

    total_amount = sum((amount for _, amount in totals.values()), Decimal("0"))
    if total_amount <= 0:
        return ()

    visible: list[TagDistributionBucket] = []
    others_total = Decimal("0")
    for key, (label, amount) in sorted(
        totals.items(),
        key=lambda item: (-item[1][1], item[1][0].casefold()),
    ):
        if amount / total_amount < Decimal(str(config.others_threshold)):
            others_total += amount
            continue
        visible.append(TagDistributionBucket(key=key, label=label, amount=amount))

    limit = max(1, config.max_legend_entries)
    if len(visible) > limit:
        keep_count = max(0, limit - 1)
        retained = visible[:keep_count]
        others_total += sum(
            (bucket.amount for bucket in visible[keep_count:]), Decimal("0")
        )
        visible = retained

    if others_total > 0:
        if visible and visible[-1].key == others_key:
            visible[-1] = TagDistributionBucket(
                key=others_key,
                label=OTHERS_LABEL,
                amount=visible[-1].amount + others_total,
            )
        else:
            visible.append(
                TagDistributionBucket(
                    key=others_key,
                    label=OTHERS_LABEL,
                    amount=others_total,
                )
            )

    return tuple(visible)


def _render_bar_items(
    items: Sequence[_BarItem],
    *,
    context: VisualizationContext,
    max_segments: int,
    show_labels: bool,
) -> VisualizationResult:
    if context.available_width <= 0:
        return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))

    render_modes: list[list[str] | None] = []
    if show_labels:
        render_modes.append([item.label for item in items])
    render_modes.append([item.compact_label for item in items])
    render_modes.append(None)

    for labels in render_modes:
        rendered = _try_render_bar_mode(
            items,
            context=context,
            labels=labels,
            max_segments=max_segments,
        )
        if rendered is not None:
            return VisualizationResult(lines=rendered)

    return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))


def _distribution_items_from_buckets(
    buckets: Sequence[TagDistributionBucket],
    config: OverviewVisualizationConfig,
) -> tuple[_DistributionItem, ...]:
    color_slots = config.tag_color_slots or DEFAULT_TAG_COLOR_SLOTS
    items: list[_DistributionItem] = []
    for index, bucket in enumerate(buckets):
        if bucket.key == normalize_tag_key(OTHERS_LABEL):
            style_slot = config.others_color_slot
        else:
            style_slot = color_slots[index % len(color_slots)]
        items.append(
            _DistributionItem(
                label=bucket.label,
                symbol=config.segment_symbol,
                value=bucket.amount,
                style_slot=style_slot,
            )
        )
    return tuple(items)


def _render_distribution(
    items: Sequence[_DistributionItem],
    *,
    context: VisualizationContext,
    max_segments: int,
) -> VisualizationResult:
    if context.available_width <= 0:
        return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))

    symbol_width = max(0, cell_len(context.config.segment_symbol))
    if symbol_width <= 0:
        return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))

    max_segments_by_width = context.available_width // symbol_width
    target_segments = min(max_segments, max_segments_by_width)
    if target_segments <= 0:
        return VisualizationResult(lines=(Text(NO_SPACE_MESSAGE),))

    fitted_items = _fit_distribution_items(
        items,
        max_items=target_segments,
        others_color_slot=context.config.others_color_slot,
    )
    counts = _scale_distribution_to_segments(
        [item.value for item in fitted_items],
        target_segments=target_segments,
    )
    if not any(counts):
        return VisualizationResult(lines=(Text(NO_DATA_MESSAGE),))

    bar = Text()
    for item, count in zip(fitted_items, counts, strict=True):
        if count <= 0:
            continue
        bar.append(
            item.symbol * count,
            style=_resolve_style(context, item.style_slot),
        )

    legend = _render_distribution_legend(fitted_items, context=context)
    return VisualizationResult(lines=(bar,), legend=legend)


def _fit_distribution_items(
    items: Sequence[_DistributionItem], *, max_items: int, others_color_slot: str
) -> tuple[_DistributionItem, ...]:
    positive_items = tuple(item for item in items if item.value > 0)
    if max_items <= 0 or len(positive_items) <= max_items:
        return positive_items

    if max_items == 1:
        return (
            _DistributionItem(
                label=OTHERS_LABEL,
                symbol=positive_items[0].symbol,
                value=sum((item.value for item in positive_items), Decimal("0")),
                style_slot=others_color_slot,
            ),
        )

    retained = list(positive_items[: max_items - 1])
    overflow = positive_items[max_items - 1 :]
    retained.append(
        _DistributionItem(
            label=OTHERS_LABEL,
            symbol=positive_items[0].symbol,
            value=sum((item.value for item in overflow), Decimal("0")),
            style_slot=others_color_slot,
        )
    )
    return tuple(retained)


def _scale_distribution_to_segments(
    values: Sequence[Decimal], *, target_segments: int
) -> list[int]:
    if target_segments <= 0:
        return [0 for _ in values]

    clamped = [max(Decimal("0"), value) for value in values]
    positive_indices = [index for index, value in enumerate(clamped) if value > 0]
    if not positive_indices:
        return [0 for _ in values]

    counts = [0 for _ in values]
    if len(positive_indices) >= target_segments:
        for index in positive_indices[:target_segments]:
            counts[index] = 1
        return counts

    for index in positive_indices:
        counts[index] = 1

    total_value = sum((clamped[index] for index in positive_indices), Decimal("0"))
    remaining = target_segments - len(positive_indices)
    allocations: list[tuple[Decimal, int]] = []
    for index in positive_indices:
        exact_extra = (clamped[index] / total_value) * Decimal(remaining)
        whole_extra = int(exact_extra)
        counts[index] += whole_extra
        allocations.append((exact_extra - Decimal(whole_extra), index))

    assigned = sum(counts)
    for _fraction, index in sorted(allocations, key=lambda item: (-item[0], item[1])):
        if assigned >= target_segments:
            break
        counts[index] += 1
        assigned += 1

    return counts


def _render_distribution_legend(
    items: Sequence[_DistributionItem],
    *,
    context: VisualizationContext,
) -> tuple[Text, ...]:
    legend: list[Text] = []
    symbol_width = cell_len(context.config.segment_symbol)
    label_available_width = context.available_width - symbol_width - 1
    if label_available_width <= 0:
        return ()

    for item in items:
        label = _truncate_to_width(item.label, label_available_width)
        if not label:
            continue
        line = Text()
        line.append(item.symbol, style=_resolve_style(context, item.style_slot))
        line.append(" ")
        line.append(label)
        legend.append(line)
    return tuple(legend)


def _try_render_bar_mode(
    items: Sequence[_BarItem],
    *,
    context: VisualizationContext,
    labels: list[str] | None,
    max_segments: int,
) -> tuple[Text, ...] | None:
    available_width = max(0, context.available_width)
    if available_width <= 0:
        return None

    label_width = 0
    if labels is not None:
        label_width = max(cell_len(label) for label in labels)
        available_width -= label_width + 2

    symbol_widths = [max(0, cell_len(item.symbol)) for item in items]
    if not symbol_widths or min(symbol_widths) <= 0:
        return None

    max_segments_by_width = min(
        available_width // symbol_width for symbol_width in symbol_widths
    )
    if max_segments_by_width <= 0:
        return None

    target_segments = min(max_segments, max_segments_by_width)
    counts = _scale_values_to_segments(
        [item.value for item in items],
        target_segments=target_segments,
    )

    lines: list[Text] = []
    for index, item in enumerate(items):
        line = Text()
        if labels is not None:
            line.append(_pad_to_width(labels[index], label_width))
            line.append("  ")

        if counts[index] > 0:
            line.append(
                item.symbol * counts[index],
                style=_resolve_style(context, item.style_slot),
            )
        lines.append(line)

    if not any(lines):
        return None
    return tuple(lines)


def _scale_values_to_segments(
    values: Sequence[Decimal], *, target_segments: int
) -> list[int]:
    if target_segments <= 0:
        return [0 for _ in values]

    clamped = [max(Decimal("0"), value) for value in values]
    max_value = max(clamped, default=Decimal("0"))
    if max_value <= 0:
        return [0 for _ in values]

    segments: list[int] = []
    target_decimal = Decimal(target_segments)
    for value in clamped:
        if value <= 0:
            segments.append(0)
            continue
        scaled = (value / max_value) * target_decimal
        count = int(scaled.to_integral_value(rounding=ROUNDING_MODE))
        segments.append(max(1, min(target_segments, count)))
    return segments


def _normalize_distribution_tags(tags: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = raw_tag.strip()
        if not tag:
            continue
        key = normalize_tag_key(tag)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)
    return normalized


def _pad_to_width(label: str, width: int) -> str:
    padding = max(0, width - cell_len(label))
    return label + (" " * padding)


def _truncate_to_width(value: str, width: int) -> str:
    if width <= 0:
        return ""
    output = ""
    used_width = 0
    for character in value:
        character_width = cell_len(character)
        if used_width + character_width > width:
            break
        output += character
        used_width += character_width
    return output


def _resolve_style(context: VisualizationContext, slot_name: str) -> str:
    if context.style_for_slot is None:
        return ""
    return context.style_for_slot(slot_name)


def _parse_visualization_type(value: object, *, source: str) -> str:
    candidate = _parse_non_empty_string(value, default=DEFAULT_VISUALIZATION_TYPE)
    if candidate not in KNOWN_VISUALIZATION_TYPES:
        logger.warning(
            "Unsupported visualization type %r in %s; using %s.",
            candidate,
            source,
            DEFAULT_VISUALIZATION_TYPE,
        )
        return DEFAULT_VISUALIZATION_TYPE
    return candidate


def _parse_multi_tag_strategy(value: object, *, source: str) -> str:
    candidate = _parse_non_empty_string(value, default=DEFAULT_MULTI_TAG_STRATEGY)
    if candidate != DEFAULT_MULTI_TAG_STRATEGY:
        logger.warning(
            "Unsupported multiTagStrategy %r in %s; using %s.",
            candidate,
            source,
            DEFAULT_MULTI_TAG_STRATEGY,
        )
        return DEFAULT_MULTI_TAG_STRATEGY
    return candidate


def _parse_symbol(value: object, *, default: str, source: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        logger.warning("Invalid symbol type in %s; using %r.", source, default)
        return default

    symbol = value.strip()
    if not symbol or cell_len(symbol) <= 0:
        logger.warning("Invalid symbol %r in %s; using %r.", value, source, default)
        return default
    return symbol


def _parse_color_slots(
    value: object,
    *,
    default: tuple[str, ...],
    source: str,
) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list):
        logger.warning("Invalid color slot list in %s; using defaults.", source)
        return default

    slots: list[str] = []
    for index, item in enumerate(value, start=1):
        slot = _parse_color_slot(
            item,
            default="",
            source=f"{source}[{index}]",
            warn_on_missing=True,
        )
        if slot:
            slots.append(slot)

    if not slots:
        logger.warning("No valid color slots in %s; using defaults.", source)
        return default
    return tuple(slots)


def _parse_color_slot(
    value: object,
    *,
    default: str,
    source: str,
    warn_on_missing: bool = False,
) -> str:
    if value is None:
        if warn_on_missing:
            logger.warning("Invalid color slot %r in %s; skipping.", value, source)
        return default
    if not isinstance(value, str):
        logger.warning("Invalid color slot %r in %s; using %s.", value, source, default)
        return default

    slot = value.strip()
    if slot not in THEME_SLOT_NAMES:
        logger.warning("Invalid color slot %r in %s; using %s.", value, source, default)
        return default
    return slot


def _parse_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _parse_non_empty_string(value: object, *, default: str) -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip()
    return normalized or default


def _parse_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _parse_positive_int(value: object, *, default: int, source: str) -> int:
    if isinstance(value, bool):
        logger.warning(
            "Invalid integer value %r in %s; using %s.", value, source, default
        )
        return default
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, float):
        candidate = int(value)
    else:
        logger.warning(
            "Invalid integer value %r in %s; using %s.", value, source, default
        )
        return default

    if candidate <= 0:
        logger.warning(
            "Invalid integer value %r in %s; using %s.", value, source, default
        )
        return default
    return candidate


def _parse_probability(value: object, *, default: float, source: str) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        logger.warning("Invalid threshold %r in %s; using %s.", value, source, default)
        return default
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        logger.warning("Invalid threshold %r in %s; using %s.", value, source, default)
        return default
    if not 0 <= candidate <= 1:
        logger.warning("Invalid threshold %r in %s; using %s.", value, source, default)
        return default
    return candidate
