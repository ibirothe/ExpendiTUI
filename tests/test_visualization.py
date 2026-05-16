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
    DEFAULT_OTHERS_SYMBOL,
    DEFAULT_VISUALIZATION_TYPE,
    NO_DATA_MESSAGE,
    NO_SPACE_MESSAGE,
    IncomeExpenseVisualizationStrategy,
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


def test_visualization_config_manager_disables_overview_when_file_is_empty(
    tmp_path,
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text("", encoding="utf-8")

    manager = VisualizationConfigManager(path=config_path)

    assert manager.config.overview_enabled is False
    assert manager.config.overview_visualizations == ()


def test_visualization_config_manager_disables_overview_when_file_is_whitespace(
    tmp_path,
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text("  \n\t", encoding="utf-8")

    manager = VisualizationConfigManager(path=config_path)

    assert manager.config.overview_enabled is False
    assert manager.config.overview_visualizations == ()


def test_visualization_config_manager_disables_overview_when_file_is_empty_object(
    tmp_path,
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text("{}", encoding="utf-8")

    manager = VisualizationConfigManager(path=config_path)

    assert manager.config.overview_enabled is False
    assert manager.config.overview_visualizations == ()


def test_visualization_config_manager_uses_defaults_when_file_is_malformed(
    tmp_path,
) -> None:
    config_path = tmp_path / "visualizations.json"
    config_path.write_text("{ invalid json", encoding="utf-8")

    manager = VisualizationConfigManager(path=config_path)

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
                            "entryType": "expense",
                            "tagSymbols": ["🟧", "🟪"],
                            "othersSymbol": "⬜",
                        },
                        {
                            "id": "income-expense",
                            "enabled": True,
                            "type": "income_vs_expense",
                            "maxWidth": 12,
                            "entryType": "both",
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
    assert manager.config.overview_visualizations[0].entry_type == "expense"
    assert manager.config.overview_visualizations[0].tag_symbols == ("🟧", "🟪")
    assert manager.config.overview_visualizations[0].others_symbol == "⬜"
    assert manager.config.overview_visualizations[1].max_width == 12
    assert manager.config.overview_visualizations[1].entry_type == "both"
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
                    "othersSymbol": "",
                    "tagSymbols": ["🟧", "", 1],
                    "entryType": "cashflow",
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
    assert panel.others_symbol == DEFAULT_OTHERS_SYMBOL
    assert panel.tag_symbols == ("🟧",)
    assert panel.entry_type is None
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


def test_visualization_renderer_can_show_only_income_or_expense() -> None:
    renderer = VisualizationRenderer()

    income_result = renderer.render(
        config=VisualizationConfig(
            overview_enabled=True,
            overview_visualizations=(
                OverviewVisualizationConfig(entry_type="income", max_width=10),
            ),
        ),
        income_entries={"salary": make_entry("100.00")},
        expense_entries={"rent": make_entry("50.00")},
        available_width=32,
    )
    expense_result = renderer.render(
        config=VisualizationConfig(
            overview_enabled=True,
            overview_visualizations=(
                OverviewVisualizationConfig(entry_type="expense", max_width=10),
            ),
        ),
        income_entries={"salary": make_entry("100.00")},
        expense_entries={"rent": make_entry("50.00")},
        available_width=32,
    )

    assert [line.plain for line in income_result.lines] == ["Income  ██████████"]
    assert [line.plain for line in expense_result.lines] == ["Expenditure  ██████████"]


def test_visualization_renderer_renders_tag_distribution_panel() -> None:
    renderer = VisualizationRenderer()
    config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(
            OverviewVisualizationConfig(
                type="tag_distribution",
                max_width=8,
                tag_symbols=("🟧", "🟪"),
            ),
        ),
    )

    result = renderer.render(
        config=config,
        income_entries={"salary": make_entry("100.00")},
        expense_entries={
            "rent": make_entry("75.00", tags=["Housing"]),
            "coffee": make_entry("25.00", tags=["Food"]),
        },
        available_width=16,
        style_for_slot=lambda slot: f"style:{slot}",
    )

    assert [line.plain for line in result.lines] == ["🟧" * 6 + "🟪" * 2]
    assert [line.plain for line in result.legend] == ["🟧 Housing", "🟪 Food"]
    assert result.lines[0].spans == []
    assert result.legend[0].spans == []


def test_visualization_renderer_groups_tag_distribution_overflow_into_others() -> None:
    renderer = VisualizationRenderer()
    config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(
            OverviewVisualizationConfig(
                type="tag_distribution",
                max_width=4,
                others_threshold=0,
                max_legend_entries=8,
            ),
        ),
    )

    result = renderer.render(
        config=config,
        income_entries={},
        expense_entries={
            "one": make_entry("40.00", tags=["One"]),
            "two": make_entry("30.00", tags=["Two"]),
            "three": make_entry("20.00", tags=["Three"]),
            "four": make_entry("10.00", tags=["Four"]),
            "five": make_entry("5.00", tags=["Five"]),
        },
        available_width=8,
    )

    assert [line.plain for line in result.lines] == ["🟧🟪🟨⬜"]
    assert [line.plain for line in result.legend] == [
        "🟧 One",
        "🟪 Two",
        "🟨 Three",
        "⬜ Other",
    ]


def test_visualization_renderer_returns_no_data_for_empty_tag_distribution() -> None:
    renderer = VisualizationRenderer()
    config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(OverviewVisualizationConfig(type="tag_distribution"),),
    )

    result = renderer.render(
        config=config,
        income_entries={"salary": make_entry("100.00")},
        expense_entries={},
        available_width=32,
    )

    assert [line.plain for line in result.lines] == [NO_DATA_MESSAGE]


def test_visualization_renderer_tag_distribution_can_use_income_or_both() -> None:
    renderer = VisualizationRenderer()
    income_config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(
            OverviewVisualizationConfig(
                type="tag_distribution",
                entry_type="income",
                max_width=4,
                tag_symbols=("🟧", "🟪"),
            ),
        ),
    )
    both_config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(
            OverviewVisualizationConfig(
                type="tag_distribution",
                entry_type="both",
                max_width=4,
                tag_symbols=("🟧", "🟪"),
            ),
        ),
    )

    income_result = renderer.render(
        config=income_config,
        income_entries={"salary": make_entry("100.00", tags=["Work"])},
        expense_entries={"rent": make_entry("50.00", tags=["Housing"])},
        available_width=8,
    )
    both_result = renderer.render(
        config=both_config,
        income_entries={"salary": make_entry("100.00", tags=["Work"])},
        expense_entries={"rent": make_entry("50.00", tags=["Housing"])},
        available_width=10,
    )

    assert [line.plain for line in income_result.legend] == ["🟧 Work"]
    assert [line.plain for line in both_result.legend] == ["🟧 Work", "🟪 Housing"]


def test_visualization_renderer_returns_no_space_for_too_narrow_tag_distribution() -> (
    None
):
    renderer = VisualizationRenderer()
    config = VisualizationConfig(
        overview_enabled=True,
        overview_visualizations=(OverviewVisualizationConfig(type="tag_distribution"),),
    )

    result = renderer.render(
        config=config,
        income_entries={},
        expense_entries={"rent": make_entry("100.00", tags=["Housing"])},
        available_width=0,
    )

    assert [line.plain for line in result.lines] == [NO_SPACE_MESSAGE]


def test_visualization_renderer_falls_back_when_only_unsupported_panels_are_enabled() -> (
    None
):
    renderer = VisualizationRenderer(strategies=(IncomeExpenseVisualizationStrategy(),))
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


def test_aggregate_tag_distribution_merges_existing_others_with_small_buckets() -> None:
    config = OverviewVisualizationConfig(
        others_threshold=0.02,
        max_legend_entries=6,
    )

    buckets = aggregate_tag_distribution(
        {
            "food": make_entry("100.00", tags=["Food"]),
            "untagged": make_entry("50.00"),
            "rent": make_entry("40.00", tags=["Rent"]),
            "tiny": make_entry("1.00", tags=["Tiny"]),
        },
        config,
    )

    assert [(bucket.label, bucket.amount) for bucket in buckets] == [
        ("Food", Decimal("100.00")),
        ("Others", Decimal("51.00")),
        ("Rent", Decimal("40.00")),
    ]
    assert sum(1 for bucket in buckets if bucket.label == "Others") == 1
