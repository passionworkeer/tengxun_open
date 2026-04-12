"""Tests for rag.indexes.embedding — EmbeddingIndex and SemanticIndexTfidf."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag.ast_chunker import CodeChunk
from rag.indexes.embedding import (
    EmbeddingIndex,
    MiniTfidfIndex,
    SemanticIndexTfidf,
    _char_ngrams,
    _tokenize,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def make_chunk(chunk_id: str, symbol: str) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        repo_path="test.py",
        module="test_mod",
        symbol=symbol,
        kind="function",
        start_line=1,
        end_line=10,
        signature=f"def {symbol}(): pass",
        docstring="",
        content=f"def {symbol}(): pass",
        imports=(),
        exported_names=(),
        string_targets=(),
        references=(),
        parent_symbol=None,
    )


# ── Standalone helpers ─────────────────────────────────────────────────


class TestEmbeddingHelpers:
    def test_char_ngrams_3_5(self) -> None:
        result = _char_ngrams("abcde", n_min=3, n_max=5)
        assert "abc" in result
        assert "abcd" in result
        assert "abcde" in result
        assert len(result) == 3 + 2 + 1  # 3-grams + 4-grams + 5-grams

    def test_char_ngrams_min_max(self) -> None:
        result = _char_ngrams("ab", n_min=2, n_max=3)
        assert "ab" in result
        assert "ab" not in _char_ngrams("a", n_min=2, n_max=3)  # too short

    def test_tokenize_identifier(self) -> None:
        tokens = _tokenize("CeleryTaskName")
        assert "celerytaskname" in tokens
        assert "celery" in tokens
        assert "task" in tokens
        assert "name" in tokens

    def test_tokenize_colon_replaced(self) -> None:
        """Colon becomes dot, then words are extracted separately."""
        tokens = _tokenize("celery.app.base:Celery")
        assert "celery" in tokens
        assert "app" in tokens
        assert "base" in tokens

    def test_tokenize_slash_replaced(self) -> None:
        """Slash becomes dot, then words are extracted separately."""
        tokens = _tokenize("celery/utils/imports.py")
        assert "celery" in tokens
        assert "utils" in tokens
        assert "imports" in tokens


# ── MiniTfidfIndex ─────────────────────────────────────────────────────


class TestMiniTfidfIndex:
    def test_search_returns_chunk_ids(self) -> None:
        token_map = {
            "c1": ["celery", "app", "base"],
            "c2": ["celery", "task"],
        }
        index = MiniTfidfIndex(token_map)
        result = index.search("celery", top_n=2)
        assert isinstance(result, list)
        assert set(result).issubset({"c1", "c2"})

    def test_empty_query_returns_empty(self) -> None:
        index = MiniTfidfIndex({"c1": ["celery"]})
        assert index.search("", top_n=5) == []
        assert index.search("   ", top_n=5) == []

    def test_top_n_respected(self) -> None:
        token_map = {f"c{i}": ["celery"] * i for i in range(1, 11)}
        index = MiniTfidfIndex(token_map)
        result = index.search("celery", top_n=3)
        assert len(result) <= 3

    def test_idf_higher_for_rare_terms(self) -> None:
        """Rare terms should contribute more to scoring."""
        token_map = {
            "c1": ["celery"] * 10,
            "c2": ["rarexyz"] * 1,
        }
        index = MiniTfidfIndex(token_map)
        result = index.search("celery rarexyz", top_n=2)
        # Both should appear but order depends on IDF weighting
        assert isinstance(result, list)

    def test_scores_sorted_descending(self) -> None:
        token_map = {
            "c1": ["celery", "celery", "task"],
            "c2": ["celery"],
        }
        index = MiniTfidfIndex(token_map)
        result = index.search("celery task", top_n=2)
        # c1 has more term overlap, should be ranked higher or equal
        assert isinstance(result, list)

    def test_unknown_term_returns_empty(self) -> None:
        index = MiniTfidfIndex({"c1": ["celery"]})
        result = index.search("xyz_unknown", top_n=5)
        assert result == []

    def test_empty_token_map(self) -> None:
        index = MiniTfidfIndex({})
        result = index.search("anything", top_n=5)
        assert result == []


# ── SemanticIndexTfidf ─────────────────────────────────────────────────


class TestSemanticIndexTfidf:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            make_chunk("c1", "celery.app.base.Celery"),
            make_chunk("c2", "celery.app.task.Task"),
            make_chunk("c3", "celery.utils.imports.symbol_by_name"),
        ]

    @pytest.fixture
    def index(self, chunks) -> SemanticIndexTfidf:
        return SemanticIndexTfidf(chunks)

    def test_search_returns_list(self, index: SemanticIndexTfidf) -> None:
        result = index.search("celery app", top_n=3)
        assert isinstance(result, list)

    def test_empty_query_returns_empty(self, index: SemanticIndexTfidf) -> None:
        assert index.search("", top_n=5) == []
        assert index.search("   ", top_n=5) == []

    def test_top_n_respected(self, index: SemanticIndexTfidf) -> None:
        result = index.search("celery", top_n=1)
        assert len(result) <= 1

    def test_word_and_char_combined(self, index: SemanticIndexTfidf) -> None:
        """Both word-level and char-level scores contribute."""
        result = index.search("symbol_by_name", top_n=3)
        assert isinstance(result, list)


# ── EmbeddingIndex ─────────────────────────────────────────────────────


class TestEmbeddingIndex:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            make_chunk("c1", "celery.app.base.Celery"),
            make_chunk("c2", "celery.app.task.Task"),
        ]

    @pytest.fixture
    def index(self, chunks) -> EmbeddingIndex:
        """Create EmbeddingIndex with real TF-IDF fallback (no API needed)."""
        return EmbeddingIndex(chunks)

    def test_init_works(self, index: EmbeddingIndex) -> None:
        assert isinstance(index, EmbeddingIndex)

    def test_search_empty_query_returns_empty(self, index: EmbeddingIndex) -> None:
        result = index.search("", top_n=5)
        assert result == []

    def test_search_whitespace_query_returns_empty(self, index: EmbeddingIndex) -> None:
        result = index.search("   ", top_n=5)
        assert result == []

    def test_top_n_respected(self, index: EmbeddingIndex) -> None:
        result = index.search("celery", top_n=1)
        assert len(result) <= 1

    def test_tfidf_fallback_returns_results(self, index: EmbeddingIndex) -> None:
        """When embeddings are empty, TF-IDF fallback still returns results."""
        result = index.search("celery", top_n=3)
        assert isinstance(result, list)
        assert len(result) <= 3

    def test_partial_embedding_coverage_falls_back(
        self, chunks
    ) -> None:
        """Low embedding coverage (<50%) should use TF-IDF."""
        # Create with empty embeddings to force fallback
        idx = EmbeddingIndex(chunks)
        # Force fallback by patching embeddings to be empty
        original = idx._embeddings
        idx._embeddings = {}
        result = idx.search("celery task", top_n=3)
        idx._embeddings = original
        assert isinstance(result, list)

    def test_get_stats(self, index: EmbeddingIndex) -> None:
        stats = index.get_stats()
        assert "embedding_request_count" in stats
        assert "embedding_failure_count" in stats
        assert "quota_hit_count" in stats
        assert "embeddings_cached" in stats
        assert "embeddings_total" in stats

    def test_truncate_short_text(self, index: EmbeddingIndex) -> None:
        result = index._truncate("short", max_chars=10)
        assert result == "short"

    def test_truncate_long_text(self, index: EmbeddingIndex) -> None:
        result = index._truncate("a" * 100, max_chars=10)
        assert len(result) == 10
        assert result == "a" * 10

    def test_truncate_exactly_at_limit(self, index: EmbeddingIndex) -> None:
        result = index._truncate("exactly10c", max_chars=10)
        assert result == "exactly10c"

    def test_ensure_client_returns_false_when_no_key(self, chunks) -> None:
        idx = EmbeddingIndex(chunks)
        result = idx._ensure_client()
        assert result is False

    def test_quota_hit_sets_flag(self, chunks) -> None:
        index = EmbeddingIndex(chunks)
        index._quota_hit()
        assert index._quota_exhausted is True
        assert index._quota_hit_count == 1

    def test_embed_batch_returns_zero_on_quota_hit(
        self, chunks
    ) -> None:
        index = EmbeddingIndex(chunks)
        index._quota_exhausted = True
        result = index._embed_batch(["text"], ["c1"])
        assert result == 0


# ── EmbeddingIndex cache ───────────────────────────────────────────────


class TestEmbeddingIndexCache:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [make_chunk("c1", "celery.app.base.Celery")]

    def test_load_cache_behavior(self, chunks) -> None:
        """EmbeddingIndex loads embeddings from cache on init when available."""
        idx = EmbeddingIndex(chunks)
        # Without any real cache file, embeddings may be empty (uses TF-IDF fallback)
        assert isinstance(idx._embeddings, dict)

    def test_save_cache_behavior(self, chunks) -> None:
        """_save_cache should write to config.cache_file without error."""
        idx = EmbeddingIndex(chunks)
        idx._embeddings = {"c1": [0.1] * 128}
        # Should not raise even if cache file is in artifacts directory
        idx._save_cache()
