"""
评测数据加载模块。

Exports:
    EvalCase dataclass
    load_eval_cases()
    load_fewshot_cases()
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class EvalCase:
    """
    评测案例数据结构

    Attributes:
        case_id: 案例唯一标识
        difficulty: 难度等级 (easy/medium/hard)
        category: 失败类型分类
        question: 问题描述
        entry_file: 任务显式提供的入口文件 anchor
        entry_symbol: 任务显式提供的入口符号 anchor（函数/类名）
        gold_fqns: 标准答案FQN列表
        reasoning_hint: 推理提示
        source_note: 来源备注
        source_schema: 数据schema版本
        failure_type: 失效类型 (Type A/B/C/D/E)
        implicit_level: 隐式依赖层级
        direct_gold_fqns: 直接依赖标准答案
        indirect_gold_fqns: 间接依赖标准答案
        implicit_gold_fqns: 隐式依赖标准答案
    """

    case_id: str
    difficulty: str
    category: str
    question: str
    entry_file: str
    entry_symbol: str
    gold_fqns: tuple[str, ...]
    reasoning_hint: str = ""
    source_note: str = ""
    source_schema: str = "legacy_v1"
    failure_type: str = ""
    implicit_level: int | None = None
    direct_gold_fqns: tuple[str, ...] = ()
    indirect_gold_fqns: tuple[str, ...] = ()
    implicit_gold_fqns: tuple[str, ...] = ()


def load_eval_cases(path: Path) -> list[EvalCase]:
    """
    加载评测案例数据集

    支持两种schema：
    - legacy_v1: 使用 gold_fqns 字段
    - schema_v2: 使用 ground_truth 字段（含 direct_deps/indirect_deps/implicit_deps）

    Args:
        path: JSON文件路径

    Returns:
        EvalCase 对象列表

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 数据格式错误
    """
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    # 使用 utf-8-sig 兼容带 BOM 的文件
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError(f"Eval dataset must be a JSON array: {path}")

    cases: list[EvalCase] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Eval case #{index} must be a JSON object.")
        if "gold_fqns" in item:
            cases.append(_parse_legacy_case(item=item, index=index))
        elif "ground_truth" in item:
            cases.append(_parse_schema_v2_case(item=item, index=index))
        else:
            raise ValueError(
                f"Eval case #{index} does not match a supported schema. "
                "Expected `gold_fqns` or `ground_truth`."
            )
    return cases


def load_fewshot_cases(path: Path) -> list[EvalCase]:
    """
    加载 few-shot 示例案例。

    与 load_eval_cases 相同入口，但语义上用于 few-shot 场景。
    """
    return load_eval_cases(path)


def _parse_legacy_case(item: dict[str, Any], index: int) -> EvalCase:
    """
    解析旧schema（legacy_v1）的案例格式

    使用 gold_fqns 字段作为标准答案。
    """
    case_id = _require_string(item, "id", index)
    question = _require_string(item, "question", index, case_id=case_id)
    entry_file = _require_string(item, "entry_file", index, case_id=case_id)
    entry_symbol = _require_string(item, "entry_symbol", index, case_id=case_id)
    gold_fqns = _normalize_ranked_items(item.get("gold_fqns", []))
    if not gold_fqns:
        raise ValueError(f"Legacy eval case `{case_id}` has no gold_fqns.")

    return EvalCase(
        case_id=case_id,
        difficulty=_require_string(item, "difficulty", index, case_id=case_id),
        category=str(item.get("category", "unspecified")),
        question=question,
        entry_file=entry_file,
        entry_symbol=entry_symbol,
        gold_fqns=gold_fqns,
        reasoning_hint=str(item.get("reasoning_hint", "")),
        source_note=str(item.get("source_note", "")),
        source_schema="legacy_v1",
        direct_gold_fqns=gold_fqns,
    )


def _parse_schema_v2_case(item: dict[str, Any], index: int) -> EvalCase:
    """
    解析新schema（schema_v2）的案例格式

    使用 ground_truth 字段，包含 direct_deps、indirect_deps、implicit_deps。
    `source_file` 是正式任务显式提供的 entry anchor，因此在运行时映射到 `entry_file`。
    """
    case_id = _require_string(item, "id", index)
    question = _require_string(item, "question", index, case_id=case_id)
    source_file = _require_string(item, "source_file", index, case_id=case_id)
    ground_truth = item.get("ground_truth")
    if not isinstance(ground_truth, dict):
        raise ValueError(f"Schema-v2 eval case `{case_id}` has invalid ground_truth.")

    direct = _normalize_ranked_items(ground_truth.get("direct_deps", []))
    indirect = _normalize_ranked_items(ground_truth.get("indirect_deps", []))
    implicit = _normalize_ranked_items(ground_truth.get("implicit_deps", []))
    gold_fqns = _normalize_ranked_items([*direct, *indirect, *implicit])
    if not gold_fqns:
        raise ValueError(f"Schema-v2 eval case `{case_id}` has no gold dependencies.")

    implicit_level_raw = item.get("implicit_level")
    implicit_level = int(implicit_level_raw) if implicit_level_raw is not None else None

    return EvalCase(
        case_id=case_id,
        difficulty=_require_string(item, "difficulty", index, case_id=case_id),
        category=str(item.get("category", "unspecified")),
        question=question,
        entry_file=source_file,
        entry_symbol=str(item.get("entry_symbol", "")),
        gold_fqns=gold_fqns,
        reasoning_hint=str(item.get("reasoning_hint", "")),
        source_note=str(item.get("source_note", "")),
        source_schema="schema_v2",
        failure_type=str(item.get("failure_type", "")),
        implicit_level=implicit_level,
        direct_gold_fqns=direct,
        indirect_gold_fqns=indirect,
        implicit_gold_fqns=implicit,
    )


def _normalize_ranked_items(values: Iterable[Any]) -> tuple[str, ...]:
    """
    规范化并去重排名项目列表

    过滤空值和重复项。
    """
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return tuple(normalized)


def _require_string(
    item: dict[str, Any],
    key: str,
    index: int,
    case_id: str = "",
) -> str:
    """
    获取必需字符串字段

    验证字段存在且为非空字符串。
    """
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        label = case_id or f"#{index}"
        raise ValueError(f"Eval case {label} is missing required string field `{key}`.")
    return value.strip()
