"""
评测指标模块

提供代码依赖分析任务常用的评测指标：
- 集合运算指标：精确率、召回率、F1
- 排序指标：Recall@K、MRR（平均倒数排名）
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

# 统一规范化函数
from rag.normalize_utils import normalize_fqn

_logger = logging.getLogger(__name__)

LAYER_KEYS = ("direct_deps", "indirect_deps", "implicit_deps")


def _safe_divide(numerator: float, denominator: float) -> float:
    """安全除法，分母为0时返回0"""
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class ClassificationMetrics:
    """分类指标容器"""

    precision: float  # 精确率
    recall: float  # 召回率
    f1: float  # F1分数


@dataclass(frozen=True)
class LayeredDependencyMetrics:
    """代码依赖任务的分层评分结果。"""

    union: ClassificationMetrics
    direct: ClassificationMetrics
    indirect: ClassificationMetrics
    implicit: ClassificationMetrics
    macro_precision: float
    macro_recall: float
    macro_f1: float
    active_layer_count: int
    active_layers: tuple[str, ...]
    exact_layer_match: bool
    exact_union_match: bool
    matched_fqns: int
    mislayered_matches: int
    mislayer_rate: float
    gold_total: int
    predicted_total: int

    def as_dict(self) -> dict[str, Any]:
        def dump(metrics: ClassificationMetrics) -> dict[str, float]:
            return {
                "precision": round(metrics.precision, 4),
                "recall": round(metrics.recall, 4),
                "f1": round(metrics.f1, 4),
            }

        return {
            "union": dump(self.union),
            "direct": dump(self.direct),
            "indirect": dump(self.indirect),
            "implicit": dump(self.implicit),
            "macro_precision": round(self.macro_precision, 4),
            "macro_recall": round(self.macro_recall, 4),
            "macro_f1": round(self.macro_f1, 4),
            "active_layer_count": self.active_layer_count,
            "active_layers": list(self.active_layers),
            "exact_layer_match": self.exact_layer_match,
            "exact_union_match": self.exact_union_match,
            "matched_fqns": self.matched_fqns,
            "mislayered_matches": self.mislayered_matches,
            "mislayer_rate": round(self.mislayer_rate, 4),
            "gold_total": self.gold_total,
            "predicted_total": self.predicted_total,
        }


def compute_set_metrics(
    gold_items: Iterable[str],
    predicted_items: Iterable[str],
) -> ClassificationMetrics:
    """
    计算集合级别的精确率、召回率和F1

    Args:
        gold_items: 标准答案集合
        predicted_items: 模型预测集合

    Returns:
        包含 precision、recall、f1 的指标对象
    """
    gold = {item for item in gold_items if item}
    predicted = {item for item in predicted_items if item}

    true_positives = len(gold & predicted)
    precision = _safe_divide(true_positives, len(predicted))
    recall = _safe_divide(true_positives, len(gold))
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return ClassificationMetrics(precision=precision, recall=recall, f1=f1)


def canonicalize_dependency_symbol(value: str) -> str:
    """将模型输出中常见的路径写法归一化为 dotted FQN 符号。

    委托 ``rag.normalize_utils.normalize_fqn`` 执行规范化，
    处理如 ``path/to/module:ClassName`` 或 ``module.ClassName`` 等
    多种写法，最终返回标准 dotted 格式。

    Args:
        value: 模型输出的原始依赖符号字符串。

    Returns:
        归一化后的 dotted FQN。若规范化结果为空字符串，
        会同时记录 debug 日志和 stderr 输出。
    """
    item = normalize_fqn(value)
    if not item:
        _logger.debug(
            f"canonicalize_dependency_symbol returned empty for input: {value!r}"
        )
        print(
            f"[DEBUG] canonicalize_dependency_symbol returned empty "
            f"for input: {value!r}",
            file=sys.stderr,
        )
    return item


def normalize_dependency_layers(
    payload: Mapping[str, Iterable[str]] | None,
) -> dict[str, list[str]]:
    """归一化 direct / indirect / implicit 三层依赖。

    对每层的每一项执行 FQN 规范化（``canonicalize_dependency_symbol``），
    过滤空值和重复项，保留首次出现的顺序。payload 为 None 或某层
    缺失时，该层返回空列表。

    Args:
        payload: 可为 None，键必须为 "direct_deps" / "indirect_deps" /
            "implicit_deps"，值为对应的依赖字符串可迭代对象。

    Returns:
        形如 ``{"direct_deps": [...], "indirect_deps": [...],
        "implicit_deps": [...]}`` 的字典，三层均已去重且顺序保留。
    """

    normalized: dict[str, list[str]] = {key: [] for key in LAYER_KEYS}
    if payload is None:
        return normalized

    for key in LAYER_KEYS:
        values = payload.get(key, [])
        if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
            continue

        seen: set[str] = set()
        items: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            item = canonicalize_dependency_symbol(value)
            if not item or item in seen:
                continue
            seen.add(item)
            items.append(item)
        normalized[key] = items

    return normalized


def compute_layered_dependency_metrics(
    gold_layers: Mapping[str, Iterable[str]] | None,
    predicted_layers: Mapping[str, Iterable[str]] | None,
) -> LayeredDependencyMetrics:
    """
    同时计算 union 指标与真正分层的 direct / indirect / implicit 指标。

    `macro_f1` 采用 active-layer macro：
    只对 gold 或 prediction 非空的层求平均，避免把“空层对空层”记成满分。
    """

    gold = normalize_dependency_layers(gold_layers)
    predicted = normalize_dependency_layers(predicted_layers)
    direct = compute_set_metrics(gold["direct_deps"], predicted["direct_deps"])
    indirect = compute_set_metrics(gold["indirect_deps"], predicted["indirect_deps"])
    implicit = compute_set_metrics(gold["implicit_deps"], predicted["implicit_deps"])

    union_gold = [item for key in LAYER_KEYS for item in gold[key]]
    union_predicted = [item for key in LAYER_KEYS for item in predicted[key]]
    if not union_gold and not union_predicted:
        union = ClassificationMetrics(precision=1.0, recall=1.0, f1=1.0)
    else:
        union = compute_set_metrics(union_gold, union_predicted)

    per_layer_metrics = {
        "direct_deps": direct,
        "indirect_deps": indirect,
        "implicit_deps": implicit,
    }
    active_layers = tuple(
        layer_key for layer_key in LAYER_KEYS if gold[layer_key] or predicted[layer_key]
    )
    if active_layers:
        macro_precision = sum(
            per_layer_metrics[layer_key].precision for layer_key in active_layers
        ) / len(active_layers)
        macro_recall = sum(
            per_layer_metrics[layer_key].recall for layer_key in active_layers
        ) / len(active_layers)
        macro_f1 = sum(
            per_layer_metrics[layer_key].f1 for layer_key in active_layers
        ) / len(active_layers)
    else:
        macro_precision = 1.0
        macro_recall = 1.0
        macro_f1 = 1.0

    exact_layer_match = all(
        set(gold[key]) == set(predicted[key]) for key in LAYER_KEYS
    )
    exact_union_match = set(union_gold) == set(union_predicted)

    gold_layer_map: dict[str, set[str]] = {}
    predicted_layer_map: dict[str, set[str]] = {}
    for layer_key in LAYER_KEYS:
        for item in gold[layer_key]:
            gold_layer_map.setdefault(item, set()).add(layer_key)
        for item in predicted[layer_key]:
            predicted_layer_map.setdefault(item, set()).add(layer_key)
    matched_fqns = set(gold_layer_map) & set(predicted_layer_map)
    mislayered_matches = sum(
        1 for item in matched_fqns if gold_layer_map[item] != predicted_layer_map[item]
    )
    mislayer_rate = _safe_divide(mislayered_matches, len(matched_fqns))

    return LayeredDependencyMetrics(
        union=union,
        direct=direct,
        indirect=indirect,
        implicit=implicit,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        active_layer_count=len(active_layers),
        active_layers=active_layers,
        exact_layer_match=exact_layer_match,
        exact_union_match=exact_union_match,
        matched_fqns=len(matched_fqns),
        mislayered_matches=mislayered_matches,
        mislayer_rate=mislayer_rate,
        gold_total=len(set(union_gold)),
        predicted_total=len(set(union_predicted)),
    )


def recall_at_k(
    gold_items: Iterable[str], ranked_items: Sequence[str], k: int
) -> float:
    """
    计算 Recall@K

    在前K个检索结果中，命中的gold标准占比。

    Args:
        gold_items: 标准答案集合
        ranked_items: 排序后的检索结果列表
        k: 取前K个结果

    Returns:
        召回率（0.0 ~ 1.0）
    """
    gold = {item for item in gold_items if item}
    if not gold or k <= 0:
        return 0.0

    top_k = set(ranked_items[:k])
    return _safe_divide(len(gold & top_k), len(gold))


def reciprocal_rank(gold_items: Iterable[str], ranked_items: Sequence[str]) -> float:
    """
    计算倒数排名（Reciprocal Rank）

    第一个命中的位置的倒数。命中返回1/position，未命中返回0。

    Args:
        gold_items: 标准答案集合
        ranked_items: 排序后的检索结果列表

    Returns:
        倒数排名分数
    """
    gold = {item for item in gold_items if item}
    if not gold:
        return 0.0

    for index, item in enumerate(ranked_items, start=1):
        if item in gold:
            return 1.0 / index
    return 0.0


def mean_reciprocal_rank(
    gold_sets: Sequence[Iterable[str]],
    ranked_lists: Sequence[Sequence[str]],
) -> float:
    """
    计算平均倒数排名（Mean Reciprocal Rank, MRR）

    对多个查询的倒数排名取平均值。

    Args:
        gold_sets: 多个查询的标准答案集合列表
        ranked_lists: 多个查询的排序结果列表

    Returns:
        平均倒数排名分数
    """
    if not gold_sets or not ranked_lists or len(gold_sets) != len(ranked_lists):
        return 0.0

    total = sum(
        reciprocal_rank(gold_items=gold, ranked_items=ranked)
        for gold, ranked in zip(gold_sets, ranked_lists)
    )
    return _safe_divide(total, len(gold_sets))
