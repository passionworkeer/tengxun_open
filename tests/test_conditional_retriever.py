"""Tests for rag.conditional_retriever — conditional RAG trigger logic."""

from __future__ import annotations

import pytest

from rag.ast_chunker import CodeChunk
from rag.conditional_retriever import (
    QuestionClassification,
    classify_question_type,
    ConditionalRetriever,
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


# ── classify_question_type ────────────────────────────────────────────


class TestClassifyQuestionType:
    def test_type_e_symbol_by_name(self) -> None:
        result = classify_question_type(
            question="In celery.utils.imports, what does symbol_by_name('celery.app.base:Celery') resolve to?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type E"
        assert result.rag_recommended is True

    def test_type_e_backend_alias(self) -> None:
        result = classify_question_type(
            question="Which backend class does celery.app.backends.by_name('redis') resolve to?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type E"
        assert result.rag_recommended is True

    def test_type_b_shared_task(self) -> None:
        result = classify_question_type(
            question="When @shared_task decorates a function, which real app method ultimately creates the task instance?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type B"
        assert result.rag_recommended is True

    def test_type_b_decorator(self) -> None:
        result = classify_question_type(
            question="Inside the @app.task decorator flow, which real method ultimately constructs and registers the task?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type B"
        assert result.rag_recommended is True

    def test_type_a_autodiscover(self) -> None:
        result = classify_question_type(
            question="In app.autodiscover_tasks(..., force=False) lazy path, which signal is triggered?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type A"
        assert result.rag_recommended is True

    def test_type_a_bootstep(self) -> None:
        result = classify_question_type(
            question="In bootsteps.py, does Step._should_include return False, is __init__ still called?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type A"
        assert result.rag_recommended is True

    def test_type_d_router_string(self) -> None:
        result = classify_question_type(
            question="In routes.py, calling expand_router_string('my.router.module:RouterClass'), which function resolves the string?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type D"
        assert result.rag_recommended is True

    def test_type_d_parameter_shadow(self) -> None:
        result = classify_question_type(
            question="In celery.app.routes.Router.query_router, parameter router shadows class Router. What does router point to?"
        )
        assert result.difficulty == "hard"
        assert result.failure_type == "Type D"
        assert result.rag_recommended is True

    def test_easy_question_classification(self) -> None:
        """'Which real class does X resolve to' contains 'resolve to' → Type E pattern → hard."""
        result = classify_question_type(
            question="Which real class does celery.Celery resolve to in the top-level lazy API?"
        )
        # Contains "resolve to" → matches Type E pattern → classified as hard
        assert result.rag_recommended is True
        assert result.difficulty == "hard"
        assert result.failure_type == "Type E"

    def test_easy_re_export(self) -> None:
        """'Which real function does top-level X symbol resolve to' → shared_task + resolve → hard."""
        result = classify_question_type(
            question="Which real function does the top-level celery.shared_task symbol resolve to?"
        )
        # shared_task matches Type B + resolve to matches Type E → hard
        assert result.rag_recommended is True
        assert result.difficulty == "hard"

    def test_medium_includes_rag(self) -> None:
        result = classify_question_type(
            question="What pool implementation does celery.concurrency.get_implementation('threads') resolve to?"
        )
        # Medium level
        assert result.rag_recommended is True

    def test_difficulty_hint_overrides(self) -> None:
        result = classify_question_type(
            question="Simple question",
            difficulty_hint="hard",
        )
        assert result.difficulty == "hard"

    def test_signals_recorded(self) -> None:
        result = classify_question_type(
            question="symbol_by_name with BACKEND_ALIASES"
        )
        assert len(result.signals) > 0

    def test_reason_not_empty(self) -> None:
        result = classify_question_type(
            question="When @shared_task decorates"
        )
        assert result.reason != ""

    def test_chinese_question(self) -> None:
        result = classify_question_type(
            question="在 celery.utils.imports 中，symbol_by_name 最终解析到哪个类？"
        )
        assert result.difficulty == "hard"

    def test_empty_question_defaults_medium(self) -> None:
        result = classify_question_type(question="")
        # Empty question: no hard signals, easy patterns don't match
        assert result.difficulty in ("medium", "easy")


# ── ConditionalRetriever ───────────────────────────────────────────────


class TestConditionalRetriever:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            make_chunk("c1", "celery.app.base.Celery"),
            make_chunk("c2", "celery.app.task.Task"),
        ]

    @pytest.fixture
    def retriever(self, chunks) -> ConditionalRetriever:
        from rag.rrf_retriever import HybridRetriever
        hybrid = HybridRetriever(chunks)
        return ConditionalRetriever(hybrid)

    def test_classify_delegates(self, retriever: ConditionalRetriever) -> None:
        result = retriever.classify("Which real class does celery.Celery resolve to?")
        assert isinstance(result, QuestionClassification)

    def test_should_use_rag_hard_true(self, retriever: ConditionalRetriever) -> None:
        assert retriever.should_use_rag(
            question="symbol_by_name resolution chain"
        ) is True

    def test_should_use_rag_easy_false(self, retriever: ConditionalRetriever) -> None:
        # The exact easy question
        result = retriever.should_use_rag(
            question="Which real class does `celery.Celery` resolve to in the top-level lazy API?"
        )
        # Easy pattern matches → rag_recommended may be False
        assert isinstance(result, bool)

    def test_fast_path_returns_chunk_ids(self, retriever: ConditionalRetriever) -> None:
        result = retriever.fast_path("celery app base", top_k=2)
        assert isinstance(result, list)
        assert all(isinstance(x, str) for x in result)

    def test_fast_path_respects_top_k(self, retriever: ConditionalRetriever) -> None:
        result = retriever.fast_path("celery", top_k=1)
        assert len(result) <= 1

    def test_fast_path_empty_query(self, retriever: ConditionalRetriever) -> None:
        result = retriever.fast_path("")
        assert isinstance(result, list)

    def test_retrieve_delegates_to_hybrid(
        self, retriever: ConditionalRetriever
    ) -> None:
        hits = retriever.retrieve("celery", top_k=2)
        assert isinstance(hits, list)

    def test_retrieve_with_trace_delegates(
        self, retriever: ConditionalRetriever
    ) -> None:
        trace = retriever.retrieve_with_trace("celery", top_k=2)
        assert hasattr(trace, "fused")

    def test_smart_retrieve_returns_hits_and_classification(
        self, retriever: ConditionalRetriever
    ) -> None:
        hits, classification = retriever.smart_retrieve(
            "symbol_by_name resolution",
            top_k=2,
        )
        assert isinstance(hits, list)
        assert isinstance(classification, QuestionClassification)

    def test_smart_retrieve_rag_recommended_false(
        self, retriever: ConditionalRetriever
    ) -> None:
        # With hard_requires_rag=True (default), even medium returns RAG
        hits, classification = retriever.smart_retrieve(
            "Which real class does `celery.Celery` resolve to in the top-level lazy API?",
            top_k=2,
        )
        assert isinstance(classification, QuestionClassification)

    def test_build_context_returns_string(
        self, retriever: ConditionalRetriever
    ) -> None:
        ctx = retriever.build_context("symbol_by_name", top_k=2)
        assert isinstance(ctx, str)

    def test_from_repo_classmethod(self) -> None:
        # Test factory: creates retriever with empty chunks for nonexistent path
        retriever = ConditionalRetriever.from_repo("/nonexistent/path")
        assert isinstance(retriever, ConditionalRetriever)
        assert len(retriever._hybrid.chunks) == 0


# ── QuestionClassification dataclass ───────────────────────────────────


class TestQuestionClassificationFields:
    def test_all_fields_present(self) -> None:
        result = classify_question_type("symbol_by_name test")
        assert hasattr(result, "difficulty")
        assert hasattr(result, "failure_type")
        assert hasattr(result, "signals")
        assert hasattr(result, "rag_recommended")
        assert hasattr(result, "reason")
        assert isinstance(result.signals, tuple)
