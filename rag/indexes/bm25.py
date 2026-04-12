"""
BM25 retrieval index.

Exports:
    BM25Index (aliased as _BM25Index for internal use)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..ast_chunker import CodeChunk


_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 indexing."""
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


def _kind_bonus(kind: str) -> float:
    """Bonus score based on code element kind."""
    if kind == "method":
        return 0.18
    if kind in {"function", "async_function"}:
        return 0.12
    if kind == "class":
        return 0.08
    return 0.0


class BM25Index:
    """
    BM25检索索引

    BM25是一种基于词频的经典检索算法。
    参数：
    - k1: 词频饱和参数（默认1.5）
    - b: 文档长度归一化参数（默认0.75）
    """

    def __init__(
        self,
        token_map: dict[str, list[str]],
        chunk_registry: dict[str, "CodeChunk"],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.token_map = token_map
        self._chunk_registry = chunk_registry
        self.doc_lengths = {
            chunk_id: len(tokens) for chunk_id, tokens in token_map.items()
        }
        self.avg_doc_length = (
            sum(self.doc_lengths.values()) / len(self.doc_lengths)
            if self.doc_lengths
            else 0.0
        )
        self.term_freqs = {
            chunk_id: Counter(tokens) for chunk_id, tokens in token_map.items()
        }
        self.doc_freqs: Counter[str] = Counter()
        for tokens in token_map.values():
            self.doc_freqs.update(set(tokens))
        self.num_docs = len(token_map)

    def search(self, query: str, top_n: int) -> list[str]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores: list[tuple[float, str]] = []
        for chunk_id, frequencies in self.term_freqs.items():
            doc_length = self.doc_lengths[chunk_id]
            score = 0.0
            for token in query_tokens:
                tf = frequencies.get(token, 0)
                if tf == 0:
                    continue
                doc_freq = self.doc_freqs.get(token, 0)
                idf = math.log(1 + (self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5))
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_length / (self.avg_doc_length or 1.0)
                )
                score += idf * (tf * (self.k1 + 1)) / denominator
            if score:
                chunk = self._safe_chunk(chunk_id)
                score += _kind_bonus(chunk.kind)
                scores.append((score, chunk_id))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [chunk_id for _, chunk_id in scores[:top_n]]

    def _safe_chunk(self, chunk_id: str) -> "CodeChunk":
        return self._chunk_registry[chunk_id]


# Alias for internal use
BM25Index.__name__ = "_BM25Index"
