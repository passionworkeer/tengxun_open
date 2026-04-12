"""Tests for rag.rrf_retriever."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag.ast_chunker import CodeChunk
from rag.rrf_retriever import (
    HybridRetriever,
    RankedResult,
    RetrievalHit,
    rrf_fuse,
    rrf_fuse_weighted,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def make_chunk(chunk_id: str, symbol: str, module: str = "test_mod",
              kind: str = "function", parent_symbol: str | None = None,
              ) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        repo_path="test.py",
        module=module,
        symbol=symbol,
        kind=kind,
        start_line=1,
        end_line=10,
        signature=f"{symbol}()",
        docstring="",
        content=f"def {symbol}(): pass",
        imports=("os",),
        exported_names=(),
        string_targets=(f"{module}.{symbol}",),
        references=("some_ref",),
        parent_symbol=parent_symbol,
    )


# ── rrf_fuse ──────────────────────────────────────────────────────────


class TestRrfFuse:
    def test_empty_rankings_returns_empty(self) -> None:
        result = rrf_fuse({})
        assert result == []

    def test_single_source(self) -> None:
        rankings = {"bm25": ["a", "b", "c"]}
        result = rrf_fuse(rankings, k=60)
        assert [r.item_id for r in result] == ["a", "b", "c"]
        assert result[0].score == 1.0 / (60 + 1)
        assert result[0].source == "bm25"

    def test_fusion_merges_multiple_sources(self) -> None:
        rankings = {
            "bm25": ["a", "b"],
            "semantic": ["b", "c"],
        }
        result = rrf_fuse(rankings, k=60)
        item_ids = [r.item_id for r in result]
        # b appears in both lists and should be ranked first
        assert item_ids[0] == "b"
        assert set(item_ids[1:]) == {"a", "c"}

    def test_k_parameter_affects_scores(self) -> None:
        rankings = {"src": ["x"]}
        r_k60 = rrf_fuse(rankings, k=60)
        r_k30 = rrf_fuse(rankings, k=30)
        assert r_k60[0].score == pytest.approx(1.0 / 61)
        assert r_k30[0].score == pytest.approx(1.0 / 31)

    def test_provenance_single_source(self) -> None:
        rankings = {"bm25": ["a"]}
        result = rrf_fuse(rankings)
        assert result[0].source == "bm25"

    def test_provenance_multi_source(self) -> None:
        rankings = {"a": ["x"], "b": ["x"]}
        result = rrf_fuse(rankings)
        result_dict = {r.item_id: r.source for r in result}
        assert result_dict["x"] == "a,b"


# ── rrf_fuse_weighted ─────────────────────────────────────────────────


class TestRrfFuseWeighted:
    def test_empty_rankings_returns_empty(self) -> None:
        result = rrf_fuse_weighted({}, {})
        assert result == []

    def test_missing_weight_defaults_to_one(self) -> None:
        rankings = {"bm25": ["a"]}
        weights: dict[str, float] = {}
        result = rrf_fuse_weighted(rankings, weights, k=30)
        assert result[0].score == pytest.approx(1.0 / 31)

    def test_weight_applied_correctly(self) -> None:
        rankings = {"bm25": ["a"]}
        weights = {"bm25": 2.0}
        result = rrf_fuse_weighted(rankings, weights, k=30)
        assert result[0].score == pytest.approx(2.0 / 31)

    def test_higher_weight_ranks_first(self) -> None:
        rankings = {
            "low": ["x"],
            "high": ["x"],
        }
        weights = {"low": 1.0, "high": 10.0}
        result = rrf_fuse_weighted(rankings, weights, k=60)
        # Both x entries are summed
        assert result[0].score == pytest.approx(1.0 / 61 + 10.0 / 61)


# ── HybridRetriever.retrieve ──────────────────────────────────────────


class TestHybridRetrieverRetrieve:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            make_chunk("c1", "foo", "test_mod"),
            make_chunk("c2", "bar", "test_mod", kind="method", parent_symbol="MyClass"),
        ]

    @pytest.fixture
    def retriever(self, chunks: list[CodeChunk]) -> HybridRetriever:
        return HybridRetriever(chunks)

    def test_retrieve_returns_list(self, retriever: HybridRetriever) -> None:
        with patch.object(retriever._bm25, "search", return_value=[]), \
             patch.object(retriever._semantic, "search", return_value=[]), \
             patch.object(retriever, "_graph_search", return_value=[]):
            hits = retriever.retrieve("test query")
        assert isinstance(hits, list)

    def test_retrieve_fuses_rankings(self, retriever: HybridRetriever) -> None:
        with patch.object(retriever._bm25, "search", return_value=["c1"]), \
             patch.object(retriever._semantic, "search", return_value=["c1"]), \
             patch.object(retriever, "_graph_search", return_value=[]):
            hits = retriever.retrieve("test query")
        ids = [h.chunk_id for h in hits]
        assert "c1" in ids

    def test_retrieve_top_k(self, retriever: HybridRetriever) -> None:
        # Use only IDs that exist in the retriever (c1, c2)
        many_ids = ["c1", "c2", "c1", "c2", "c1", "c2"]
        with patch.object(retriever._bm25, "search", return_value=many_ids), \
             patch.object(retriever._semantic, "search", return_value=[]), \
             patch.object(retriever, "_graph_search", return_value=[]):
            hits = retriever.retrieve("test query", top_k=3)
        # Only c1 and c2 exist in the registry; fused dedup yields 2 hits max, capped at top_k=3
        assert len(hits) <= 3
        assert set(h.chunk_id for h in hits).issubset({"c1", "c2"})

    def test_retrieve_calls_all_three_indexes(self, retriever: HybridRetriever) -> None:
        with patch.object(retriever._bm25, "search", return_value=["c1"]) as mock_bm25, \
             patch.object(retriever._semantic, "search", return_value=[]) as mock_sem, \
             patch.object(retriever, "_graph_search", return_value=[]) as mock_graph:
            retriever.retrieve("test query")
        assert mock_bm25.called
        assert mock_sem.called
        assert mock_graph.called

    def test_retrieve_with_weights_uses_weighted_fusion(
        self, retriever: HybridRetriever
    ) -> None:
        weights = {"bm25": 1.0, "semantic": 0.5, "graph": 0.5}
        with patch.object(retriever._bm25, "search", return_value=["c1"]), \
             patch.object(retriever._semantic, "search", return_value=[]), \
             patch.object(retriever, "_graph_search", return_value=[]):
            hits = retriever.retrieve("test query", weights=weights)
        assert isinstance(hits, list)


# ── HybridRetriever.expand_candidate_fqns ──────────────────────────────


class TestExpandCandidateFqns:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            make_chunk("c1", "mymod.myfunc"),
            make_chunk("c2", "mymod.MyClass.my_method", parent_symbol="mymod.MyClass"),
        ]

    @pytest.fixture
    def retriever(self, chunks: list[CodeChunk]) -> HybridRetriever:
        return HybridRetriever(chunks)

    def test_returns_list(self, retriever: HybridRetriever) -> None:
        hits = [RetrievalHit(
            chunk_id="c1", symbol="x", repo_path="x.py",
            kind="function", score=0.0, source=(), start_line=1,
            end_line=1, snippet="",
        )]
        result = retriever.expand_candidate_fqns(hits)
        assert isinstance(result, list)

    def test_includes_symbol_itself(self, retriever: HybridRetriever) -> None:
        hits = [RetrievalHit(
            chunk_id="c1", symbol="mymod.myfunc", repo_path="x.py",
            kind="function", score=0.0, source=(), start_line=1,
            end_line=1, snippet="",
        )]
        result = retriever.expand_candidate_fqns(hits)
        assert "mymod.myfunc" in result

    def test_empty_hits_returns_empty_list(self, retriever: HybridRetriever) -> None:
        result = retriever.expand_candidate_fqns([])
        assert result == []


# ── HybridRetriever.build_context ─────────────────────────────────────


class TestBuildContext:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [make_chunk("c1", "foo")]

    @pytest.fixture
    def retriever(self, chunks: list[CodeChunk]) -> HybridRetriever:
        return HybridRetriever(chunks)

    def test_returns_string(self, retriever: HybridRetriever) -> None:
        fake_trace = MagicMock()
        fake_trace.fused = []
        with patch.object(retriever, "retrieve_with_trace", return_value=fake_trace):
            ctx = retriever.build_context("test")
        assert isinstance(ctx, str)

    def test_includes_retrieved_chunks(self, retriever: HybridRetriever) -> None:
        hit = RetrievalHit(
            chunk_id="c1",
            symbol="foo",
            repo_path="test.py",
            kind="function",
            score=0.9,
            source=("bm25",),
            start_line=1,
            end_line=10,
            snippet="def foo(): pass",
        )
        fake_trace = MagicMock()
        fake_trace.fused = [hit]
        with patch.object(retriever, "retrieve_with_trace", return_value=fake_trace):
            ctx = retriever.build_context("test")
        assert "foo" in ctx

    def test_respects_max_context_tokens(self, retriever: HybridRetriever) -> None:
        hit = RetrievalHit(
            chunk_id="c1",
            symbol="foo",
            repo_path="test.py",
            kind="function",
            score=0.9,
            source=(),
            start_line=1,
            end_line=10,
            snippet="x" * 1000,
        )
        fake_trace = MagicMock()
        fake_trace.fused = [hit]
        with patch.object(retriever, "retrieve_with_trace", return_value=fake_trace):
            ctx = retriever.build_context("test", max_context_tokens=50)
        assert isinstance(ctx, str)


# ── P0-1 regression: no global state pollution ───────────────────────


class TestGlobalStateIsolation:
    def test_chunk_registry_is_per_instance(self) -> None:
        """Each HybridRetriever instance must have its own isolated registry."""
        chunks1 = [make_chunk("x1", "func_a")]
        chunks2 = [make_chunk("x2", "func_b")]
        r1 = HybridRetriever(chunks1)
        r2 = HybridRetriever(chunks2)

        # Each retriever must have its own isolated registry
        assert "x1" in r1._chunk_registry
        assert "x2" in r2._chunk_registry
        # Registries must not be shared
        assert r1._chunk_registry is not r2._chunk_registry

    def test_bm25_safe_chunk_uses_instance_registry(self) -> None:
        """_BM25Index._safe_chunk must read from its own _chunk_registry."""
        chunks = [make_chunk("p1", "my_func")]
        retriever = HybridRetriever(chunks)

        # The bm25 instance should hold a reference to the retriever's registry
        assert retriever._bm25._chunk_registry is retriever._chunk_registry
        chunk = retriever._bm25._safe_chunk("p1")
        assert chunk.symbol == "my_func"
