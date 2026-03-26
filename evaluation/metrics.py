from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


def _safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class ClassificationMetrics:
    precision: float
    recall: float
    f1: float


def compute_set_metrics(
    gold_items: Iterable[str],
    predicted_items: Iterable[str],
) -> ClassificationMetrics:
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
    gold = {item for item in gold_items if item}
    if not gold or k <= 0:
        return 0.0

    top_k = set(ranked_items[:k])
    return _safe_divide(len(gold & top_k), len(gold))


def reciprocal_rank(gold_items: Iterable[str], ranked_items: Sequence[str]) -> float:
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
    if not gold_sets or not ranked_lists or len(gold_sets) != len(ranked_lists):
        return 0.0

    total = sum(
        reciprocal_rank(gold_items=gold, ranked_items=ranked)
        for gold, ranked in zip(gold_sets, ranked_lists)
    )
    return _safe_divide(total, len(gold_sets))
