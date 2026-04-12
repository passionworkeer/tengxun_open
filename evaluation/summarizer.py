"""
评测数据集统计摘要模块。

Exports:
    summarize_cases()
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .loader import EvalCase


def summarize_cases(cases: list[EvalCase]) -> dict[str, Any]:
    """
    生成数据集统计摘要

    统计内容：
    - 案例总数
    - 难度分布
    - 类别分布
    - Schema分布
    - 失效类型分布
    - 平均gold目标数量

    Args:
        cases: 案例列表

    Returns:
        包含各项统计指标的字典
    """
    difficulty_counter = Counter(case.difficulty for case in cases)
    category_counter = Counter(case.category for case in cases)
    schema_counter = Counter(case.source_schema for case in cases)
    failure_counter = Counter(case.failure_type for case in cases if case.failure_type)
    avg_gold_targets = (
        sum(len(case.gold_fqns) for case in cases) / len(cases) if cases else 0.0
    )
    return {
        "num_cases": len(cases),
        "difficulty_distribution": dict(sorted(difficulty_counter.items())),
        "category_distribution_top10": dict(category_counter.most_common(10)),
        "source_schema_distribution": dict(sorted(schema_counter.items())),
        "failure_type_distribution": dict(sorted(failure_counter.items())),
        "avg_gold_targets": round(avg_gold_targets, 2),
        "has_minimum_required_cases": len(cases) >= 50,
        "has_first_batch_seed": len(cases) >= 12,
        "entry_metadata_coverage": {
            "with_entry_symbol": sum(1 for case in cases if case.entry_symbol),
            "with_entry_file": sum(1 for case in cases if case.entry_file),
        },
        "official_task_setting": "question_plus_entry (question + provided entry metadata)",
    }
