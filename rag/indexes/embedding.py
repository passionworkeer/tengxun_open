"""
Embedding-based index with TF-IDF fallback.

Exports:
    EmbeddingIndex (aliased as _EmbeddingIndex for internal use)
    SemanticIndexTfidf (aliased as _SemanticIndexTfidf)
    MiniTfidfIndex   (aliased as _MiniTfidfIndex)
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from ...ast_chunker import CodeChunk

_EMBED_BATCH_SIZE = 50
_logger = logging.getLogger(__name__)


def _char_ngrams(text: str, n_min: int, n_max: int) -> list[str]:
    text = text.lower()
    result: list[str] = []
    for n in range(n_min, n_max + 1):
        for i in range(len(text) - n + 1):
            result.append(text[i : i + n])
    return result


def _tokenize(text: str) -> list[str]:
    """Tokenize text for TF-IDF indexing."""
    _TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
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


class SemanticIndexTfidf:
    """
    TF-IDF回退索引

    当嵌入API不可用时的回退方案。
    结合词级TF-IDF和字符n-gram进行检索。
    """

    def __init__(self, chunks: list["CodeChunk"]) -> None:
        self.chunk_ids = [c.chunk_id for c in chunks]
        word_map: dict[str, list[str]] = {}
        for chunk in chunks:
            text = " ".join([chunk.symbol, chunk.signature, chunk.content])
            word_map[chunk.chunk_id] = _tokenize(text)
        self._word_index = MiniTfidfIndex(word_map)
        char_map: dict[str, list[str]] = {}
        for chunk in chunks:
            text = chunk.symbol + " " + chunk.signature
            char_map[chunk.chunk_id] = _char_ngrams(text, n_min=3, n_max=5)
        self._char_index = MiniTfidfIndex(char_map)

    def search(self, query: str, top_n: int) -> list[str]:
        if not query.strip():
            return []
        word_results = self._word_index.search(query, top_n=top_n)
        char_results = self._char_index.search(query, top_n=top_n)
        scores: dict[str, float] = {}
        for rank, cid in enumerate(word_results, 1):
            scores[cid] = scores.get(cid, 0.0) + (1.0 / rank) * 0.6
        for rank, cid in enumerate(char_results, 1):
            scores[cid] = scores.get(cid, 0.0) + (1.0 / rank) * 0.4
        return [
            cid
            for cid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[
                :top_n
            ]
        ]


class MiniTfidfIndex:
    """Lightweight TF-IDF using raw term frequencies + IDF approximation."""

    def __init__(self, token_map: dict[str, list[str]]) -> None:
        self.token_map = token_map
        self.doc_freqs: Counter[str] = Counter()
        for tokens in token_map.values():
            self.doc_freqs.update(set(tokens))
        self.num_docs = len(token_map)

    def search(self, query: str, top_n: int) -> list[str]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        tf_freq = Counter(q_tokens)
        scores: list[tuple[float, str]] = []
        for cid, tokens in self.token_map.items():
            doc_tf = Counter(tokens)
            score = 0.0
            for tok in q_tokens:
                df = self.doc_freqs.get(tok, 0)
                if df == 0:
                    continue
                idf = math.log((self.num_docs + 1) / (df + 1)) + 1.0
                score += idf * doc_tf.get(tok, 0)
            if score:
                scores.append((score, cid))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [cid for _, cid in scores[:top_n]]


class EmbeddingIndex:
    """
    Real embedding index using provider-aware embeddings.

    Uses cache-first strategy: load from disk cache if available,
    otherwise fall back to TF-IDF. Pre-computation script can build
    the cache offline when rate limits allow.
    """

    def __init__(self, chunks: list["CodeChunk"], *, repo_root: str | Path = "") -> None:
        from ..embedding_provider import (
            EmbeddingProviderClient,
            load_embedding_cache,
            resolve_embedding_config,
            save_embedding_cache,
        )

        self.chunk_ids = [c.chunk_id for c in chunks]
        self._chunk_texts: dict[str, str] = {
            c.chunk_id: f"{c.symbol} {c.signature} {c.content}" for c in chunks
        }
        self._fallback = SemanticIndexTfidf(chunks)
        self._client: EmbeddingProviderClient | None = None
        self._config = resolve_embedding_config()
        self._embeddings: dict[str, list[float]] = {}
        self._repo_root = str(repo_root)
        self._quota_exhausted = False
        self._embedding_request_count = 0
        self._embedding_failure_count = 0
        self._quota_hit_count = 0

        if self._config.cache_file.exists():
            self._load_cache()

        cached = len(self._embeddings)
        if cached == len(self.chunk_ids):
            print(
                f"[EmbeddingIndex] All {cached} embeddings loaded from cache "
                f"({self._config.provider_label})"
            )
            return

        missing = [cid for cid in self.chunk_ids if cid not in self._embeddings]
        print(
            f"[EmbeddingIndex] Cache loaded: {cached}/{len(self.chunk_ids)} "
            f"from {self._config.cache_file} ({self._config.provider_label})"
        )

    def _truncate(self, text: str, max_chars: int = 2000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    def _ensure_client(self) -> bool:
        from ..embedding_provider import EmbeddingProviderClient

        if self._client is not None:
            return not self._quota_exhausted
        if self._quota_exhausted:
            return False
        try:
            self._client = EmbeddingProviderClient(self._config)
            if not self._client.available():
                return False
            return True
        except Exception:
            self._embedding_failure_count += 1
            return False

    def _quota_hit(self) -> None:
        self._quota_exhausted = True
        self._quota_hit_count += 1
        self._client = None

    def _embed_batch(self, texts: list[str], chunk_ids: list[str]) -> int:
        if not self._ensure_client():
            return 0
        import time

        for attempt in range(3):
            try:
                embeddings = self._client.batch_embed(texts)
                if not embeddings:
                    raise RuntimeError("empty embeddings response")
                for cid, emb in zip(chunk_ids, embeddings):
                    self._embeddings[cid] = emb
                self._embedding_request_count += 1
                return len(embeddings)
            except Exception as exc:
                if "429" in str(exc) and attempt == 0:
                    print(f"[EmbeddingIndex] API quota exhausted, stopping")
                    self._quota_hit()
                    return 0
                wait = (attempt + 1) * 5
                print(f"[EmbeddingIndex] Batch failed ({exc}), retrying in {wait}s...")
                time.sleep(wait)
        return 0

    def _embed_chunks(self, chunk_ids: list[str]) -> None:
        texts = [self._truncate(self._chunk_texts[cid]) for cid in chunk_ids]
        total = len(chunk_ids)
        done = 0
        batch_size = _EMBED_BATCH_SIZE
        print(f"[EmbeddingIndex] Embedding {total} chunks...")

        for i in range(0, total, batch_size):
            batch_ids = chunk_ids[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            n = self._embed_batch(batch_texts, batch_ids)
            if n == 0:
                print(
                    f"[EmbeddingIndex] Batch embedding failed at {i}/{total}, stopping"
                )
                break
            done += n
            print(f"[EmbeddingIndex]   {done}/{total}")
            import time

            time.sleep(1)

        if done == total:
            self._save_cache()
        elif done > 0:
            print(f"[EmbeddingIndex] Partial embedding: {done}/{total}, saving cache")
            self._save_cache()

    def _load_cache(self) -> None:
        from ..embedding_provider import load_embedding_cache

        try:
            self._embeddings = load_embedding_cache(
                self._config,
                valid_chunk_ids=set(self.chunk_ids),
            )
            print(
                f"[EmbeddingIndex] Cache loaded: {len(self._embeddings)}/{len(self.chunk_ids)}"
            )
        except Exception:
            self._embeddings = {}

    def _save_cache(self) -> None:
        from ..embedding_provider import save_embedding_cache

        try:
            save_embedding_cache(self._config, self._embeddings)
            print(f"[EmbeddingIndex] Cache saved: {len(self._embeddings)} chunks")
        except Exception as exc:
            print(f"[EmbeddingIndex] Cache save failed: {exc}")

    def search(self, query: str, top_n: int) -> list[str]:
        if not query.strip():
            return []

        embed_coverage = len(self._embeddings) / len(self.chunk_ids)

        if embed_coverage < 0.5:
            _logger.debug(
                "[EmbeddingIndex] Fallback to TF-IDF: coverage %.2f < 0.5", embed_coverage
            )
            return self._fallback.search(query, top_n)

        if not self._ensure_client():
            _logger.debug(
                "[EmbeddingIndex] Fallback to TF-IDF: client unavailable "
                "(failures=%d, quota_hits=%d)",
                self._embedding_failure_count,
                self._quota_hit_count,
            )
            return self._fallback.search(query, top_n)

        try:
            q_emb = self._client.embed_query(query)
        except Exception as exc:
            if "429" in str(exc):
                print(f"[EmbeddingIndex] API quota exhausted, using TF-IDF only")
                self._quota_hit()
            return self._fallback.search(query, top_n)

        # Embedding-based scores for chunks that have embeddings
        embed_scores: dict[str, float] = {}
        for cid, emb in self._embeddings.items():
            dot = sum(a * b for a, b in zip(q_emb, emb))
            embed_scores[cid] = (dot + 1.0) / 2.0

        # TF-IDF scores for top candidates (fallback for non-embedded chunks)
        tfidf_ids = self._fallback.search(query, top_n=top_n * 4)
        tfidf_scores_raw = {cid: 0.0 for cid in tfidf_ids}
        for rank, cid in enumerate(tfidf_ids, 1):
            tfidf_scores_raw[cid] = 1.0 / rank

        max_emb = max(embed_scores.values()) if embed_scores else 1.0
        max_tfidf = max(tfidf_scores_raw.values()) if tfidf_scores_raw else 1.0

        # Combine: real-embedded chunks use hybrid score, rest use TF-IDF only
        candidates = set(embed_scores) | set(tfidf_scores_raw)
        hybrid_scores: list[tuple[float, str]] = []
        for cid in candidates:
            emb = embed_scores.get(cid, 0.0) / max_emb
            tfidf = tfidf_scores_raw.get(cid, 0.0) / max_tfidf
            if cid in embed_scores:
                combined = emb * 0.7 + tfidf * 0.3
            else:
                combined = tfidf
            hybrid_scores.append((combined, cid))

        hybrid_scores.sort(key=lambda x: x[0], reverse=True)
        return [cid for _, cid in hybrid_scores[:top_n]]

    def get_stats(self) -> dict[str, int | float]:
        """Return monitoring counters for diagnostics."""
        return {
            "embedding_request_count": self._embedding_request_count,
            "embedding_failure_count": self._embedding_failure_count,
            "quota_hit_count": self._quota_hit_count,
            "embeddings_cached": len(self._embeddings),
            "embeddings_total": len(self.chunk_ids),
        }


# Aliases for internal use
EmbeddingIndex.__name__ = "_EmbeddingIndex"
SemanticIndexTfidf.__name__ = "_SemanticIndexTfidf"
MiniTfidfIndex.__name__ = "_MiniTfidfIndex"
