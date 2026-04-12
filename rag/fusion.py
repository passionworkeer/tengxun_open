"""
RRF fusion utilities and shared data structures.

Exports:
    RankedResult, RetrievalHit, RetrievalTrace
    rrf_fuse, rrf_fuse_weighted
    _tokenize, _kind_bonus, _looks_like_fqn
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from .ast_chunker import normalize_symbol_target

_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class RankedResult:
    item_id: str
    score: float
    source: str


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    symbol: str
    repo_path: str
    kind: str
    score: float
    source: tuple[str, ...]
    start_line: int
    end_line: int
    snippet: str


@dataclass(frozen=True)
class RetrievalTrace:
    bm25: tuple[str, ...]
    semantic: tuple[str, ...]
    graph: tuple[str, ...]
    fused_ids: tuple[str, ...]
    fused: tuple[RetrievalHit, ...]


def rrf_fuse(rankings: dict[str, Iterable[str]], k: int = 60) -> list[RankedResult]:
    """
    倒数排名融合（Reciprocal Rank Fusion）

    将多个排序列表融合为一个统一排序。
    公式：score(item) = Σ 1/(k + rank(item))

    Args:
        rankings: 各来源的排序字典，key为来源名，value为排序后的item列表
        k: RRF参数，通常60

    Returns:
        按融合分数排序的结果列表
    """
    fused_scores: dict[str, float] = defaultdict(float)
    provenance: dict[str, set[str]] = defaultdict(set)

    for source_name, items in rankings.items():
        for rank, item_id in enumerate(items, start=1):
            fused_scores[item_id] += 1.0 / (k + rank)
            provenance[item_id].add(source_name)

    ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)

    results: list[RankedResult] = []
    for item_id, score in ranked:
        results.append(
            RankedResult(
                item_id=item_id,
                score=score,
                source=",".join(sorted(provenance[item_id])),
            )
        )
    return results


def rrf_fuse_weighted(
    rankings: dict[str, Iterable[str]],
    weights: dict[str, float],
    k: int = 30,
) -> list[RankedResult]:
    """
    加权倒数排名融合（Weighted Reciprocal Rank Fusion）

    在标准 RRF 基础上乘以来源权重。
    公式：score(item) = Σ weight[source] / (k + rank(item))

    Args:
        rankings: 各来源的排序字典，key为来源名，value为排序后的item列表
        weights: 各来源的权重，key为来源名
        k: RRF参数，通常30

    Returns:
        按融合分数排序的结果列表
    """
    fused_scores: dict[str, float] = defaultdict(float)
    provenance: dict[str, set[str]] = defaultdict(set)

    for source_name, items in rankings.items():
        w = weights.get(source_name, 1.0)
        for rank, item_id in enumerate(items, start=1):
            fused_scores[item_id] += w * 1.0 / (k + rank)
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


# ── Shared helpers used across modules ──────────────────────────────────


def _kind_bonus(kind: str) -> float:
    """
    根据代码块类型给予额外加分

    - method: 0.18 (类方法权重最高)
    - function/async_function: 0.12
    - class: 0.08
    - 其他: 0.0
    """
    if kind == "method":
        return 0.18
    if kind in {"function", "async_function"}:
        return 0.12
    if kind == "class":
        return 0.08
    return 0.0


def _tokenize(text: str) -> list[str]:
    """
    分词函数

    处理：
    1. 特殊字符替换（: -> .，/ -> . 等）
    2. 标识符提取
    3. 驼峰分词
    """
    normalized = (
        text.replace(":", ".").replace("/", ".").replace("`", " ").replace("-", " ")
    )
    tokens: list[str] = []
    for raw_token in _TOKEN_PATTERN.findall(normalized):
        lower = raw_token.lower()
        tokens.append(lower)
        split_token = re.sub(r"(?<!^)(?=[A-Z])", " ", raw_token).lower()
        tokens.extend(piece for piece in split_token.split() if piece)
    return tokens


def _looks_like_fqn(value: str) -> bool:
    """
    检查字符串是否像FQN（完全限定名）

    必须包含至少一个点，且每个部分都是有效的Python标识符。

    Examples:
        "celery.app.trace" -> True
        "foo" -> False (没有点)
        "123.foo" -> False (部分以数字开头)
    """
    if "." not in value:
        return False
    for part in value.split("."):
        if not part:
            return False
        if not (part[0].isalpha() or part[0] == "_"):
            return False
    return True


def _extract_string_literals(text: str) -> set[str]:
    """Extract quoted string literals from text for Type D disambiguation.

    Matches single-quoted and double-quoted strings like 'processes', "threads".
    These are often alias/argument values that determine which symbol to resolve to.
    """
    quoted = re.findall(r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text)
    return set(quoted)


def _extract_symbol_like_strings(text: str) -> list[str]:
    matches = re.findall(
        r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+", text
    )
    return [normalize_symbol_target(match) for match in matches]
