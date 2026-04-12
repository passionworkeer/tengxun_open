"""Tests for evaluation.evaluator — retrieval evaluation logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from evaluation.evaluator import (
    RETRIEVAL_SOURCES,
    _aggregate_bucket_metrics,
    _build_query_text,
    _summarize_ranked_lists,
    evaluate_retrieval,
)
from evaluation.loader import EvalCase


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def sample_cases() -> list[EvalCase]:
    return [
        EvalCase(
            case_id="easy_001",
            difficulty="easy",
            category="re_export",
            failure_type="Type C",
            question="Which real class does celery.Celery resolve to?",
            entry_file="celery/__init__.py",
            entry_symbol="celery.Celery",
            gold_fqns=("celery.app.base.Celery",),
            direct_gold_fqns=("celery.app.base.Celery",),
        ),
        EvalCase(
            case_id="hard_001",
            difficulty="hard",
            category="shared_task_registration",
            failure_type="Type B",
            question="When @shared_task decorates a function, which real app method ultimately creates the task instance?",
            entry_file="celery/app/__init__.py",
            entry_symbol="shared_task",
            gold_fqns=("celery.app.base.Celery._task_from_fun",),
            direct_gold_fqns=("celery.app.base.Celery._task_from_fun",),
        ),
        EvalCase(
            case_id="hard_004",
            difficulty="hard",
            category="symbol_by_name_resolution",
            failure_type="Type E",
            question="In celery.worker.strategy.default, what real class does task.Request resolve to?",
            entry_file="celery/worker/strategy.py",
            entry_symbol="task.Request",
            gold_fqns=("celery.worker.request.Request",),
            direct_gold_fqns=("celery.worker.request.Request",),
        ),
    ]


# ── RETRIEVAL_SOURCES ─────────────────────────────────────────────────


class TestRetrievalSources:
    def test_has_expected_sources(self) -> None:
        assert "bm25" in RETRIEVAL_SOURCES
        assert "semantic" in RETRIEVAL_SOURCES
        assert "graph" in RETRIEVAL_SOURCES
        assert "fused" in RETRIEVAL_SOURCES


# ── _build_query_text ──────────────────────────────────────────────────


class TestBuildQueryText:
    def test_question_only_mode(self) -> None:
        case = EvalCase(
            case_id="t1",
            difficulty="easy",
            category="cat",
            failure_type="",
            question="What does X resolve to?",
            entry_file="",
            entry_symbol="",
            gold_fqns=(),
        )
        result = _build_query_text(case, "question_only")
        assert result == "What does X resolve to?"

    def test_question_plus_entry_mode(self) -> None:
        case = EvalCase(
            case_id="t1",
            difficulty="easy",
            category="cat",
            failure_type="",
            question="What does X resolve to?",
            entry_file="celery/app/base.py",
            entry_symbol="Celery",
            gold_fqns=(),
        )
        result = _build_query_text(case, "question_plus_entry")
        assert "What does X resolve to?" in result
        assert "Celery" in result
        assert "celery/app/base.py" in result

    def test_question_plus_entry_missing_fields(self) -> None:
        case = EvalCase(
            case_id="t1",
            difficulty="easy",
            category="cat",
            failure_type="",
            question="What does X resolve to?",
            entry_file="",
            entry_symbol="",
            gold_fqns=(),
        )
        result = _build_query_text(case, "question_plus_entry")
        assert result == "What does X resolve to?"

    def test_unsupported_mode_raises(self) -> None:
        case = EvalCase(
            case_id="t1",
            difficulty="easy",
            category="cat",
            failure_type="",
            question="Q",
            entry_file="",
            entry_symbol="",
            gold_fqns=(),
        )
        with pytest.raises(ValueError, match="Unsupported query mode"):
            _build_query_text(case, "invalid_mode")


# ── _summarize_ranked_lists ───────────────────────────────────────────


class TestSummarizeRankedLists:
    def test_empty_cases_returns_zeros(self) -> None:
        result = _summarize_ranked_lists(cases=[], ranked_lists=[], top_k=5)
        assert result["avg_recall_at_k"] == 0.0
        assert result["mrr"] == 0.0
        assert result["difficulty_breakdown"] == {}

    def test_mismatched_lengths_raises(self) -> None:
        cases = [EvalCase(
            case_id="c1", difficulty="easy", category="c",
            failure_type="", question="Q",
            entry_file="", entry_symbol="",
            gold_fqns=("gold",),
        )]
        ranked_lists = [["a", "b"], ["c"]]  # 2 vs 1
        with pytest.raises(ValueError):
            _summarize_ranked_lists(cases, ranked_lists, top_k=5)

    def test_avg_recall_single_case_hit(self) -> None:
        cases = [EvalCase(
            case_id="c1", difficulty="easy", category="cat",
            failure_type="Type C", question="Q",
            entry_file="", entry_symbol="",
            gold_fqns=("celery.app.base.Celery",),
        )]
        ranked_lists = [["celery.app.base.Celery", "other"]]
        result = _summarize_ranked_lists(cases, ranked_lists, top_k=5)
        assert result["avg_recall_at_k"] == 1.0

    def test_avg_recall_single_case_miss(self) -> None:
        cases = [EvalCase(
            case_id="c1", difficulty="hard", category="cat",
            failure_type="Type E", question="Q",
            entry_file="", entry_symbol="",
            gold_fqns=("celery.app.base.Celery",),
        )]
        ranked_lists = [["other", "different"]]
        result = _summarize_ranked_lists(cases, ranked_lists, top_k=5)
        assert result["avg_recall_at_k"] == 0.0

    def test_difficulty_breakdown(self) -> None:
        cases = [
            EvalCase(
                case_id="c1", difficulty="easy", category="cat",
                failure_type="Type C", question="Q",
                entry_file="", entry_symbol="",
                gold_fqns=("gold",),
            ),
            EvalCase(
                case_id="c2", difficulty="hard", category="cat",
                failure_type="Type B", question="Q",
                entry_file="", entry_symbol="",
                gold_fqns=("gold2",),
            ),
        ]
        ranked_lists = [["gold"], ["gold2"]]
        result = _summarize_ranked_lists(cases, ranked_lists, top_k=5)
        assert "easy" in result["difficulty_breakdown"]
        assert "hard" in result["difficulty_breakdown"]

    def test_failure_type_breakdown(self) -> None:
        cases = [
            EvalCase(
                case_id="c1", difficulty="hard", category="cat",
                failure_type="Type B", question="Q",
                entry_file="", entry_symbol="",
                gold_fqns=("gold",),
            ),
            EvalCase(
                case_id="c2", difficulty="hard", category="cat",
                failure_type="Type E", question="Q",
                entry_file="", entry_symbol="",
                gold_fqns=("gold2",),
            ),
        ]
        ranked_lists = [["gold"], ["gold2"]]
        result = _summarize_ranked_lists(cases, ranked_lists, top_k=5)
        assert "Type B" in result["failure_type_breakdown"]
        assert "Type E" in result["failure_type_breakdown"]


# ── _aggregate_bucket_metrics ─────────────────────────────────────────


class TestAggregateBucketMetrics:
    def test_single_bucket(self) -> None:
        recall = {"TypeE": [1.0, 0.5]}
        rr = {"TypeE": [1.0, 0.5]}
        result = _aggregate_bucket_metrics(recall, rr)
        assert "TypeE" in result
        assert result["TypeE"]["avg_recall_at_k"] == 0.75
        assert result["TypeE"]["num_cases"] == 2

    def test_multiple_buckets(self) -> None:
        recall = {"easy": [1.0], "hard": [0.0, 0.5]}
        rr = {"easy": [1.0], "hard": [0.0, 0.5]}
        result = _aggregate_bucket_metrics(recall, rr)
        assert result["easy"]["avg_recall_at_k"] == 1.0
        assert result["hard"]["avg_recall_at_k"] == 0.25

    def test_empty_bucket_excluded(self) -> None:
        recall = {"TypeA": [], "TypeB": [0.8]}
        rr = {"TypeA": [], "TypeB": [0.8]}
        result = _aggregate_bucket_metrics(recall, rr)
        assert "TypeA" not in result
        assert "TypeB" in result


# ── evaluate_retrieval ────────────────────────────────────────────────


class TestEvaluateRetrieval:
    @pytest.fixture
    def mock_trace(self):
        """Build a mock RetrievalTrace for patching."""
        trace = MagicMock()
        trace.bm25 = ("c1",)
        trace.semantic = ("c1",)
        trace.graph = ("c2",)
        trace.fused_ids = ("c1", "c2")
        trace.fused = []
        return trace

    def test_returns_dict_with_required_keys(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = ["symbol"]
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = ["fqn"]

        result = evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
        )
        assert "num_cases" in result
        assert "fused_chunk_symbols" in result
        assert "source_breakdown" in result
        assert "cases" in result
        assert result["num_cases"] == len(sample_cases)

    def test_calls_retrieve_for_each_case(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = []
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = []

        evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
        )
        assert mock_retriever.retrieve_with_trace.call_count == len(sample_cases)

    def test_rrf_k_passed_to_retriever(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = []
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = []

        evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
            rrf_k=60,
        )
        mock_retriever.retrieve_with_trace.assert_called()
        call_kwargs = mock_retriever.retrieve_with_trace.call_args.kwargs
        assert call_kwargs.get("rrf_k") == 60

    def test_weights_passed_to_retriever(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = []
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = []
        weights = {"bm25": 0.2, "semantic": 0.1, "graph": 0.7}

        evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
            weights=weights,
        )
        call_kwargs = mock_retriever.retrieve_with_trace.call_args.kwargs
        assert call_kwargs.get("weights") == weights

    def test_per_case_has_correct_structure(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = ["sym1"]
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = ["fqn1"]

        result = evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
        )
        for case_result in result["cases"]:
            assert "id" in case_result
            assert "difficulty" in case_result
            assert "sources" in case_result
            assert "fused" in case_result["sources"]

    def test_source_breakdown_has_all_sources(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = []
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = []

        result = evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
        )
        for source in RETRIEVAL_SOURCES:
            assert source in result["source_breakdown"]

    def test_setting_includes_rrf_k_and_query_mode(
        self, sample_cases, mock_trace
    ) -> None:
        mock_retriever = MagicMock()
        mock_retriever.retrieve_with_trace.return_value = mock_trace
        mock_retriever.ranked_symbols.return_value = []
        mock_retriever.expand_candidate_fqns_from_chunk_ids.return_value = []

        result = evaluate_retrieval(
            cases=sample_cases,
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_only",
            rrf_k=50,
        )
        assert result["setting"]["rrf_k"] == 50
        assert result["setting"]["query_mode"] == "question_only"

    def test_empty_cases_returns_valid_structure(self) -> None:
        mock_retriever = MagicMock()
        result = evaluate_retrieval(
            cases=[],
            retriever=mock_retriever,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
        )
        assert result["num_cases"] == 0
        assert "fused_chunk_symbols" in result
        assert "cases" in result
