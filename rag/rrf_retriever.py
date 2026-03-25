from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RankedResult:
    item_id: str
    score: float
    source: str


def rrf_fuse(rankings: dict[str, Iterable[str]], k: int = 60) -> list[RankedResult]:
    fused_scores: dict[str, float] = defaultdict(float)
    provenance: dict[str, set[str]] = defaultdict(set)

    for source_name, items in rankings.items():
        for rank, item_id in enumerate(items, start=1):
            fused_scores[item_id] += 1.0 / (k + rank)
            provenance[item_id].add(source_name)

    ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)
    return [
        RankedResult(
            item_id=item_id,
            score=score,
            source=",".join(sorted(provenance[item_id])),
        )
        for item_id, score in ranked
    ]

