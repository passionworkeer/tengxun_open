"""
评测指标模块

提供代码依赖分析任务常用的评测指标：
- 集合运算指标：精确率、召回率、F1
- 排序指标：Recall@K、MRR（平均倒数排名）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def _safe_divide(numerator: float, denominator: float) -> float:
    """安全除法，分母为0时返回0"""
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class ClassificationMetrics:
    """分类指标容器"""

    precision: float  # 精确率
    recall: float  # 召回率
    f1: float  # F1分数


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
