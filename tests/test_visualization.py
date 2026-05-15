from __future__ import annotations

import json
import logging
from decimal import Decimal

from expenditui.models import ExpenseEntry
from expenditui.visualization import (
    DEFAULT_EXPENSE_SYMBOL,
    DEFAULT_MAX_LEGEND_ENTRIES,
    DEFAULT_MAX_WIDTH,
    DEFAULT_OTHERS_THRESHOLD,
    DEFAULT_VISUALIZATION_TYPE,
    NO_DATA_MESSAGE,
    OverviewVisualizationConfig,
    VisualizationConfig,
    VisualizationConfigManager,
    VisualizationRenderer,
    aggregate_tag_distribution,
)


def make_entry(
    amount: str,
    *,
    frequency: str = "monthly",
    tags: list[str] | None = None,
) -> ExpenseEntry:
    return ExpenseEntry(amount=amount, frequency=frequency, tags=tags or [])


def test_visualization_config_manager_uses_defaults_when_file_is_missing(
    tmp_path,
) -> None:
    manager = VisualizationConfigManager(path=tmp_path / "visualizations.json")

    assert manager.config == VisualizationConfig.default()


def test_visualization_config_manager_normalizes_future_visualization_array(
    tmp_path,
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text(
        json.dumps(
            {
                "overview": {
                    "enabled": True,
                    "visualizations": [
                        {
                            "id": "tag-breakdown",
                            "enabled": False,
                            "type": "tag_distribution",
                            "maxWidth": 24,
                        },
                        {
                            "id": "income-expense",
                            "enabled": True,
                            "type": "income_vs_expense",
                            "maxWidth": 12,
                            "incomeSymbol": "🟩",
                            "expenseSymbol": "🟥",
                            "showLabels": False,
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    manager = VisualizationConfigManager(path=config_path)

    assert manager.config.overview_enabled is True
    assert [panel.id for panel in manager.config.overview_visualizations] == [
        "tag-breakdown",
        "income-expense",
    ]
    assert manager.config.overview_visualizations[1].max_width == 12
    assert manager.config.overview_visualizations[1].show_labels is False


def test_visualization_config_manager_recovers_from_invalid_fields(
    tmp_path, caplog
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text(
        json.dumps(
            {
                "overview": {
                    "type": "unknown",
                    "maxWidth": 0,
                    "expenseSymbol": "",
                    "maxLegendEntries": 0,
                    "othersThreshold": 9,
                }
            }
        ),
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        manager = VisualizationConfigManager(path=config_path)

    panel = manager.config.overview_visualizations[0]
    assert panel.type == DEFAULT_VISUALIZATION_TYPE
    assert panel.max_width == DEFAULT_MAX_WIDTH
    assert panel.expense_symbol == DEFAULT_EXPENSE_SYMBOL
    assert panel.max_legend_entries == DEFAULT_MAX_LEGEND_ENTRIES
    assert panel.others_threshold == DEFAULT_OTHERS_THRESHOLD
    assert "Unsupported visualization type" in caplog.text


def test_visualization_renderer_scales_income_and_expense_proportionally() -> None:
    renderer = VisualizationRenderer()

    result = renderer.render(
        config=VisualizationConfig.default(),
        income_entries={"salary": make_entry("4000.00")},
        expense_entries={"rent": make_entry("2000.00")},
        available_width=32,
    )

    lines = [line.plain for line in result.lines]
    assert lines[0].endswith("██████████")
    assert lines[1].endswith("█████")


def test_visualization_renderer_keeps_minimum_visibility_for_non_zero_values() -> None:
    renderer = VisualizationRenderer()

    result = renderer.render(
        config=VisualizationConfig.default(),
        income_entries={"salary": make_entry("5000.00")},
        expense_entries={"coffee": make_entry("1.00")},
        available_width=32,
    )

    lines = [line.plain for line in result.lines]
    assert lines[0].endswith("██████████")
    assert lines[1].endswith("█")


def test_visualization_renderer_uses_compact_labels_in_narrow_layouts() -> None:
    renderer = VisualizationRenderer()

    result = renderer.render(
        config=VisualizationConfig.default(),
        income_entries={"salary": make_entry("100.00")},
        expense_entries={"rent": make_entry("50.00")},
        available_width=4,
    )

    assert [line.plain for line in result.lines] == ["I  █", "E  █"]


def test_visualization_renderer_returns_no_data_message_when_totals_are_empty() -> None:
    renderer = VisualizationRenderer()

    result = renderer.render(
        config=VisualizationConfig.default(),
        income_entries={},
        expense_entries={},
        available_width=32,
    )

    assert [line.plain for line in result.lines] == [NO_DATA_MESSAGE]


def test_visualization_renderer_falls_back_when_only_unsupported_panels_are_enabled() -> (
    None
):
    renderer = VisualizationRenderer()
    config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(
            OverviewVisualizationConfig(type="tag_distribution", max_width=8),
        ),
    )

    result = renderer.render(
        config=config,
        income_entries={"salary": make_entry("100.00")},
        expense_entries={"rent": make_entry("50.00")},
        available_width=32,
    )

    assert [line.plain for line in result.lines][0].startswith("Income")


def test_aggregate_tag_distribution_splits_multi_tags_and_groups_small_buckets() -> (
    None
):
    config = OverviewVisualizationConfig(
        others_threshold=0.10,
        max_legend_entries=3,
    )

    buckets = aggregate_tag_distribution(
        {
            "shared": make_entry("60.00", tags=["Food", "Friends"]),
            "groceries": make_entry("30.00", tags=[" food "]),
            "bus": make_entry("5.00", tags=["Travel"]),
            "misc": make_entry("5.00"),
        },
        config,
    )

    assert [(bucket.label, bucket.amount) for bucket in buckets] == [
        ("Food", Decimal("60.00")),
        ("Friends", Decimal("30.00")),
        ("Others", Decimal("10.00")),
    ]
