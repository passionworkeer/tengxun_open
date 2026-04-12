"""
RAG检索评测模块。

Exports:
    evaluate_retrieval()
    RETRIEVAL_SOURCES
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from .loader import EvalCase
from .metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank

# 支持的检索来源
RETRIEVAL_SOURCES = ("bm25", "semantic", "graph", "fused")


def evaluate_retrieval(
    cases: list[EvalCase],
    retriever,  # HybridRetriever
    top_k: int,
    per_source: int,
    query_mode: str,
    rrf_k: int = 30,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    运行RAG检索评测

    对每个案例执行三路检索（BM25/Semantic/Graph）并计算指标。

    Args:
        cases: 案例列表
        retriever: 混合检索器实例
        top_k: 取前K个结果计算指标
        per_source: 每个检索来源保留的结果数
        query_mode: 查询模式
        rrf_k: RRF融合参数
        weights: 加权融合权重，格式 {"bm25": 0.25, "semantic": 0.05, "graph": 0.7}

    Returns:
        包含各来源检索指标和详细案例结果的字典
    """
    chunk_rankings: dict[str, list[list[str]]] = {
        source: [] for source in RETRIEVAL_SOURCES
    }
    expanded_rankings: dict[str, list[list[str]]] = {
        source: [] for source in RETRIEVAL_SOURCES
    }
    per_case: list[dict[str, Any]] = []

    for case in cases:
        query_text = _build_query_text(case=case, query_mode=query_mode)
        trace = retriever.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )
        source_chunk_ids = {
            "bm25": list(trace.bm25),
            "semantic": list(trace.semantic),
            "graph": list(trace.graph),
            "fused": list(trace.fused_ids),
        }
        source_details: dict[str, Any] = {}

        for source_name, chunk_ids in source_chunk_ids.items():
            chunk_symbols = retriever.ranked_symbols(chunk_ids)
            expanded_fqns = retriever.expand_candidate_fqns_from_chunk_ids(
                chunk_ids=chunk_ids,
                source=source_name,
                query_text=query_text,
                entry_symbol=case.entry_symbol,
            )
            chunk_rankings[source_name].append(chunk_symbols)
            expanded_rankings[source_name].append(expanded_fqns)
            source_details[source_name] = {
                "chunk_symbol_top_hits": chunk_symbols[:top_k],
                "expanded_fqn_top_hits": expanded_fqns[:top_k],
                "chunk_symbol_recall_at_k": round(
                    recall_at_k(case.gold_fqns, chunk_symbols, top_k), 4
                ),
                "expanded_fqn_recall_at_k": round(
                    recall_at_k(case.gold_fqns, expanded_fqns, top_k), 4
                ),
                "chunk_symbol_reciprocal_rank": round(
                    reciprocal_rank(case.gold_fqns, chunk_symbols), 4
                ),
                "expanded_fqn_reciprocal_rank": round(
                    reciprocal_rank(case.gold_fqns, expanded_fqns), 4
                ),
            }

        per_case.append(
            {
                "id": case.case_id,
                "difficulty": case.difficulty,
                "category": case.category,
                "failure_type": case.failure_type,
                "source_schema": case.source_schema,
                "gold_fqns": list(case.gold_fqns),
                "sources": source_details,
            }
        )

    source_breakdown: dict[str, Any] = {}
    for source_name in RETRIEVAL_SOURCES:
        source_breakdown[source_name] = {
            "chunk_symbols": _summarize_ranked_lists(
                cases=cases,
                ranked_lists=chunk_rankings[source_name],
                top_k=top_k,
            ),
            "expanded_fqns": _summarize_ranked_lists(
                cases=cases,
                ranked_lists=expanded_rankings[source_name],
                top_k=top_k,
            ),
        }

    return {
        "num_cases": len(cases),
        "top_k": top_k,
        "setting": {
            "query_mode": query_mode,
            "rrf_k": rrf_k,
            "weights": weights,
            "query_inputs": (
                ["question"]
                if query_mode == "question_only"
                else ["question", "entry_symbol", "entry_file"]
            ),
            "per_source_depth": per_source,
            "gold_scope": {
                "legacy_v1": "gold_fqns",
                "schema_v2": "union(direct_deps, indirect_deps, implicit_deps)",
            },
            "ranking_views": {
                "chunk_symbols": "Uses retrieved chunk symbols only; no candidate expansion.",
                "expanded_fqns": "Uses retrieved chunks plus heuristic expansion over imports, string targets, and references.",
            },
        },
        "fused_chunk_symbols": source_breakdown["fused"]["chunk_symbols"],
        "fused_expanded_fqns": source_breakdown["fused"]["expanded_fqns"],
        "source_breakdown": source_breakdown,
        "cases": per_case,
    }


def _summarize_ranked_lists(
    cases: Sequence[EvalCase],
    ranked_lists: Sequence[Sequence[str]],
    top_k: int,
) -> dict[str, Any]:
    """
    汇总排序列表的评测指标

    按难度等级和失效类型分别计算 Recall@K 和 MRR。
    """
    if len(cases) != len(ranked_lists):
        raise ValueError("Cases and ranked_lists must be aligned.")

    gold_sets = [case.gold_fqns for case in cases]
    recall_by_difficulty: dict[str, list[float]] = defaultdict(list)
    rr_by_difficulty: dict[str, list[float]] = defaultdict(list)
    recall_by_failure_type: dict[str, list[float]] = defaultdict(list)
    rr_by_failure_type: dict[str, list[float]] = defaultdict(list)
    for case, ranked in zip(cases, ranked_lists):
        recall_score = recall_at_k(case.gold_fqns, ranked, top_k)
        rr_score = reciprocal_rank(case.gold_fqns, ranked)
        recall_by_difficulty[case.difficulty].append(recall_score)
        rr_by_difficulty[case.difficulty].append(rr_score)
        if case.failure_type:
            recall_by_failure_type[case.failure_type].append(recall_score)
            rr_by_failure_type[case.failure_type].append(rr_score)

    return {
        "avg_recall_at_k": round(
            sum(
                recall_at_k(case.gold_fqns, ranked, top_k)
                for case, ranked in zip(cases, ranked_lists)
            )
            / len(cases),
            4,
        )
        if cases
        else 0.0,
        "mrr": round(mean_reciprocal_rank(gold_sets, ranked_lists), 4),
        "difficulty_breakdown": _aggregate_bucket_metrics(
            recall_by_difficulty,
            rr_by_difficulty,
        ),
        "failure_type_breakdown": _aggregate_bucket_metrics(
            recall_by_failure_type,
            rr_by_failure_type,
        ),
    }


def _aggregate_bucket_metrics(
    recall_buckets: dict[str, list[float]],
    rr_buckets: dict[str, list[float]],
) -> dict[str, Any]:
    """
    聚合指标桶的统计数据

    计算每个桶（难度等级/失效类型）的平均召回率和平均倒数排名。
    """
    return {
        bucket: {
            "avg_recall_at_k": round(sum(recall_values) / len(recall_values), 4),
            "avg_reciprocal_rank": round(
                sum(rr_buckets[bucket]) / len(rr_buckets[bucket]),
                4,
            ),
            "num_cases": len(recall_values),
        }
        for bucket, recall_values in sorted(recall_buckets.items())
        if recall_values
    }


def _build_query_text(case: EvalCase, query_mode: str) -> str:
    """
    构建检索查询文本

    Args:
        case: 评测案例
        query_mode: 查询模式
            - question_only: 仅使用问题文本
            - question_plus_entry: 正式 entry-guided 口径，同时使用问题和提供的入口元数据

    Returns:
        组装后的查询文本
    """
    if query_mode == "question_only":
        return case.question.strip()
    if query_mode != "question_plus_entry":
        raise ValueError(f"Unsupported query mode: {query_mode}")
    return " ".join(
        part
        for part in (
            case.question.strip(),
            case.entry_symbol.strip(),
            case.entry_file.strip(),
        )
        if part
    )
