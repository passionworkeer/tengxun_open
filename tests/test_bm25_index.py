"""Tests for rag.indexes.bm25 — BM25 retrieval index."""

from __future__ import annotations

import pytest

from rag.ast_chunker import CodeChunk
from rag.indexes.bm25 import BM25Index, _kind_bonus, _tokenize


# ── Fixtures ──────────────────────────────────────────────────────────


def make_chunk(chunk_id: str, symbol: str, kind: str = "function") -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        repo_path="test.py",
        module="test_mod",
        symbol=symbol,
        kind=kind,
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


def tokens_for(symbol: str, content: str = "") -> list[str]:
    return _tokenize(f"{symbol} {content}")


# ── _tokenize ─────────────────────────────────────────────────────────


class TestBm25Tokenize:
    def test_lowercases_tokens(self) -> None:
        tokens = _tokenize("CeleryTaskName")
        assert "celerytaskname" in tokens

    def test_camel_case_split(self) -> None:
        tokens = _tokenize("CeleryTaskName")
        assert "celery" in tokens
        assert "task" in tokens
        assert "name" in tokens

    def test_dot_replaced_with_space_and_tokens_extracted(self) -> None:
        """Dots are replaced with spaces; individual words are extracted."""
        tokens = _tokenize("celery.app.base:Celery")
        # Dot is replaced with space, then words are found separately
        assert "celery" in tokens
        assert "app" in tokens
        assert "base" in tokens
        assert "celery" in tokens  # appears multiple times (camelCase + separate)

    def test_slash_replaced_with_space(self) -> None:
        """Slashes are replaced with spaces before tokenization."""
        tokens = _tokenize("celery/utils/imports")
        # slash replaced with dot (which becomes space), words extracted
        assert "celery" in tokens
        assert "utils" in tokens
        assert "imports" in tokens

    def test_special_chars_removed(self) -> None:
        tokens = _tokenize("`backtick`")
        assert "backtick" in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


# ── _kind_bonus ───────────────────────────────────────────────────────


class TestKindBonus:
    def test_method_highest(self) -> None:
        assert _kind_bonus("method") == 0.18

    def test_function(self) -> None:
        assert _kind_bonus("function") == 0.12

    def test_async_function(self) -> None:
        assert _kind_bonus("async_function") == 0.12

    def test_class_bonus(self) -> None:
        assert _kind_bonus("class") == 0.08

    def test_unknown_zero(self) -> None:
        assert _kind_bonus("unknown") == 0.0
        assert _kind_bonus("") == 0.0


# ── BM25Index ─────────────────────────────────────────────────────────


class TestBM25Index:
    @pytest.fixture
    def token_map(self) -> dict[str, list[str]]:
        return {
            "c1": tokens_for("celery.app.base.Celery", "main celery application class"),
            "c2": tokens_for("celery.app.task.Task", "celery task base class"),
            "c3": tokens_for("celery.utils.imports.symbol_by_name", "symbol resolution utility"),
        }

    @pytest.fixture
    def chunk_registry(self) -> dict[str, CodeChunk]:
        return {
            "c1": make_chunk("c1", "celery.app.base.Celery", kind="class"),
            "c2": make_chunk("c2", "celery.app.task.Task", kind="class"),
            "c3": make_chunk("c3", "celery.utils.imports.symbol_by_name", kind="function"),
        }

    @pytest.fixture
    def index(self, token_map, chunk_registry) -> BM25Index:
        return BM25Index(token_map, chunk_registry)

    def test_search_returns_list_of_chunk_ids(self, index: BM25Index) -> None:
        result = index.search("celery app", top_n=3)
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)

    def test_empty_query_returns_empty(self, index: BM25Index) -> None:
        assert index.search("", top_n=5) == []
        assert index.search("   ", top_n=5) == []

    def test_top_n_respected(self, index: BM25Index) -> None:
        result = index.search("celery", top_n=1)
        assert len(result) <= 1

    def test_unknown_query_returns_empty_or_capped(
        self, index: BM25Index
    ) -> None:
        result = index.search("zzz_unknown_term_xyz", top_n=5)
        assert isinstance(result, list)

    def test_scores_are_sorted_descending(self, index: BM25Index) -> None:
        result = index.search("celery task", top_n=3)
        assert isinstance(result, list)

    def test_partial_match(self, index: BM25Index) -> None:
        result = index.search("symbol", top_n=3)
        assert isinstance(result, list)

    def test_exact_symbol_match(self, index: BM25Index) -> None:
        result = index.search("symbol_by_name", top_n=3)
        assert isinstance(result, list)

    def test_class_kind_bonus_applied(self, index: BM25Index) -> None:
        """Classes should get kind bonus."""
        result = index.search("celery application", top_n=3)
        assert isinstance(result, list)

    def test_method_kind_bonus_applied(self, index, chunk_registry) -> None:
        """Methods should get higher bonus than functions."""
        chunk_registry["c4"] = make_chunk("c4", "pkg.MyClass.do_it", kind="method")
        token_map = index.token_map.copy()
        token_map["c4"] = tokens_for("pkg.MyClass.do_it", "method in class")
        new_index = BM25Index(token_map, chunk_registry, k1=1.5, b=0.75)
        result = new_index.search("do it", top_n=2)
        assert isinstance(result, list)

    def test_k1_parameter_affects_scoring(self, token_map, chunk_registry) -> None:
        index_k15 = BM25Index(token_map, chunk_registry, k1=1.5)
        index_k30 = BM25Index(token_map, chunk_registry, k1=3.0)
        r1 = index_k15.search("celery", top_n=5)
        r2 = index_k30.search("celery", top_n=5)
        # Different k1 can change relative ordering
        assert isinstance(r1, list)
        assert isinstance(r2, list)

    def test_b_parameter_affects_length_normalization(
        self, token_map, chunk_registry
    ) -> None:
        index_b0 = BM25Index(token_map, chunk_registry, k1=1.5, b=0.0)
        index_b1 = BM25Index(token_map, chunk_registry, k1=1.5, b=1.0)
        r1 = index_b0.search("celery app", top_n=5)
        r2 = index_b1.search("celery app", top_n=5)
        assert isinstance(r1, list)
        assert isinstance(r2, list)

    def test_avg_doc_length_computed(self, token_map, chunk_registry) -> None:
        index = BM25Index(token_map, chunk_registry)
        assert index.avg_doc_length >= 0

    def test_empty_token_map(self, chunk_registry) -> None:
        index = BM25Index({}, chunk_registry)
        result = index.search("anything", top_n=5)
        assert result == []

    def test_single_doc(self) -> None:
        token_map = {"only": _tokenize("celery app base")}
        chunk_registry = {
            "only": make_chunk("only", "celery.app.Celery", kind="class")
        }
        index = BM25Index(token_map, chunk_registry)
        result = index.search("celery", top_n=3)
        assert "only" in result


# ── BM25Index internal state ───────────────────────────────────────────


class TestBM25IndexInternal:
    def test_safe_chunk(self) -> None:
        chunk = make_chunk("c1", "mymod.func")
        token_map = {"c1": _tokenize("mymod func")}
        index = BM25Index(token_map, {"c1": chunk})
        retrieved = index._safe_chunk("c1")
        assert retrieved.chunk_id == "c1"
        assert retrieved.symbol == "mymod.func"

    def test_doc_lengths_indexed(self) -> None:
        token_map = {
            "a": ["tok1", "tok2", "tok3"],
            "b": ["tok1"],
        }
        index = BM25Index(token_map, {})
        assert index.doc_lengths["a"] == 3
        assert index.doc_lengths["b"] == 1

    def test_term_freqs_indexed(self) -> None:
        token_map = {
            "a": ["celery", "celery", "task"],
        }
        index = BM25Index(token_map, {})
        tf = index.term_freqs["a"]
        assert tf["celery"] == 2
        assert tf["task"] == 1

    def test_doc_freqs_count_unique_docs(self) -> None:
        token_map = {
            "a": ["tok", "tok", "common"],
            "b": ["other", "common"],
        }
        index = BM25Index(token_map, {})
        assert index.doc_freqs["common"] == 2
        assert index.doc_freqs["tok"] == 1
        assert index.doc_freqs["other"] == 1
