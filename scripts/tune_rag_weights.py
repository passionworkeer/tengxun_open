#!/usr/bin/env python3
"""
RRF 权重调优脚本

评估不同 BM25/Semantic/Graph 权重组合对各类 Failure Type 的影响，
按难度等级和失效类型分组输出 Markdown 表格。

用法:
    python scripts/tune_rag_weights.py --eval-cases data/eval_cases.json --repo-root external/celery
    python scripts/tune_rag_weights.py --top-k 5 --per-source 12 --rrf-k 30
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from rag import HybridRetriever, build_retriever
from rag.fusion import rrf_fuse_weighted
from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import recall_at_k, reciprocal_rank, mean_reciprocal_rank


# ─── Default weight combinations to evaluate ───────────────────────────────

DEFAULT_WEIGHT_COMBINATIONS: list[dict[str, float]] = [
    {"bm25": 0.33, "semantic": 0.33, "graph": 0.34},  # equal weights
    {"bm25": 0.25, "semantic": 0.05, "graph": 0.70},  # graph-dominant (current)
    {"bm25": 0.40, "semantic": 0.10, "graph": 0.50},  # bm25-heavy
    {"bm25": 0.50, "semantic": 0.05, "graph": 0.45},  # bm25-strong
    {"bm25": 0.20, "semantic": 0.10, "graph": 0.70},  # graph-strong
    {"bm25": 0.30, "semantic": 0.20, "graph": 0.50},  # balanced
    {"bm25": 0.15, "semantic": 0.05, "graph": 0.80},  # graph-overwhelming
    {"bm25": 0.45, "semantic": 0.15, "graph": 0.40},  # bm25+semantic
    {"bm25": 0.35, "semantic": 0.30, "graph": 0.35},  # semantic-heavy
    {"bm25": 0.10, "semantic": 0.20, "graph": 0.70},  # semantic+graph
]

# ─── Retrieval sources ──────────────────────────────────────────────────────

RETRIEVAL_SOURCES = ("bm25", "semantic", "graph", "fused")


# ─── Core evaluation ────────────────────────────────────────────────────────

def evaluate_weights(
    cases: list[EvalCase],
    retriever: HybridRetriever,
    weights: dict[str, float],
    top_k: int,
    per_source: int,
    query_mode: str,
    rrf_k: int,
) -> dict[str, Any]:
    """
    用指定权重对所有案例运行检索，计算融合后的指标。

    Returns a structured dict with overall, difficulty, and failure_type breakdowns.
    """
    fused_recalls: list[float] = []
    fused_rrs: list[float] = []
    difficulty_recalls: dict[str, list[float]] = defaultdict(list)
    difficulty_rrs: dict[str, list[float]] = defaultdict(list)
    ft_recalls: dict[str, list[float]] = defaultdict(list)
    ft_rrs: dict[str, list[float]] = defaultdict(list)

    for case in cases:
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

        fused_symbols = retriever.ranked_symbols(list(trace.fused_ids))
        fused_expanded = retriever.expand_candidate_fqns_from_chunk_ids(
            chunk_ids=list(trace.fused_ids),
            source="fused",
            query_text=" ".join(filter(None, [case.question, case.entry_symbol, case.entry_file])),
            entry_symbol=case.entry_symbol,
        )

        chunk_recall = recall_at_k(case.gold_fqns, fused_symbols, top_k)
        expanded_recall = recall_at_k(case.gold_fqns, fused_expanded, top_k)
        rr = reciprocal_rank(case.gold_fqns, fused_symbols)

        fused_recalls.append(chunk_recall)
        fused_rrs.append(rr)

        difficulty_recalls[case.difficulty].append(chunk_recall)
        difficulty_rrs[case.difficulty].append(rr)

        if case.failure_type:
            ft_recalls[case.failure_type].append(chunk_recall)
            ft_rrs[case.failure_type].append(rr)

    def _avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    def _bucket(
        recalls: dict[str, list[float]], rrs: dict[str, list[float]]
    ) -> dict[str, dict[str, Any]]:
        return {
            bucket: {"avg_recall": _avg(recalls[bucket]), "avg_rr": _avg(rrs[bucket]), "n": len(recalls[bucket])}
            for bucket in sorted(recalls)
            if recalls[bucket]
        }

    return {
        "weights": weights,
        "overall": {
            "avg_recall": _avg(fused_recalls),
            "avg_mrr": _avg(fused_rrs),
            "n": len(fused_recalls),
        },
        "by_difficulty": _bucket(difficulty_recalls, difficulty_rrs),
        "by_failure_type": _bucket(ft_recalls, ft_rrs),
    }


# ─── Grid search with per-source breakdown ─────────────────────────────────

def grid_search(
    cases: list[EvalCase],
    retriever: HybridRetriever,
    weight_combinations: list[dict[str, float]],
    top_k: int,
    per_source: int,
    query_mode: str,
    rrf_k: int,
) -> list[dict[str, Any]]:
    """
    对所有权重组合运行 grid search，返回结果列表（已按 overall avg_recall 降序）。
    """
    results: list[dict[str, Any]] = []
    for weights in weight_combinations:
        result = evaluate_weights(
            cases=cases,
            retriever=retriever,
            weights=weights,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
        )
        results.append(result)
        print(
            f"  weights=({weights['bm25']:.2f},{weights['semantic']:.2f},{weights['graph']:.2f}) "
            f"-> recall={result['overall']['avg_recall']:.4f}  mrr={result['overall']['avg_mrr']:.4f}"
        )
    results.sort(key=lambda r: r["overall"]["avg_recall"], reverse=True)
    return results


# ─── Markdown table formatting ─────────────────────────────────────────────

def _fmt(v: float) -> str:
    return f"{v:.4f}"


def _fmt_w(w: dict[str, float]) -> str:
    return f"bm25={w['bm25']:.2f} sem={w['semantic']:.2f} gr={w['graph']:.2f}"


def _col(label: str, val: float) -> str:
    return f"| {label} | {_fmt(val)} |"


def _sep() -> str:
    return "|---|--------|"


def _header(cols: list[str]) -> str:
    return "| Weights | " + " | ".join(cols) + " |\n" + _sep() + "\n"


def _row(w: dict[str, float], vals: list[float]) -> str:
    return "| " + _fmt_w(w) + " | " + " | ".join(_fmt(v) for v in vals) + " |"


def _blank_row(cols: int) -> str:
    return "| (blank) | " + " | ".join("-" * 7 for _ in range(cols)) + " |"


def build_markdown_table(results: list[dict[str, Any]]) -> str:
    """Build a Markdown report from grid-search results."""
    lines: list[str] = [
        "# RRF 权重调优报告",
        "",
        "评估目标：不同 BM25/Semantic/Graph 权重组合对检索 Recall@K 的影响。",
        "结果按 overall avg_recall 降序排列。",
        "",
    ]

    # ── Overall summary ────────────────────────────────────────────────
    lines.append("## 1. 总体指标（按 Recall@K 降序）\n")
    cols = ["Avg Recall", "Avg MRR", "# Cases"]
    lines.append(_header(cols))
    for r in results:
        lines.append(
            _row(r["weights"], [r["overall"]["avg_recall"], r["overall"]["avg_mrr"], r["overall"]["n"]])
        )
    lines.append("")

    # ── By difficulty ─────────────────────────────────────────────────
    # collect all difficulty buckets appearing across results
    diff_buckets: list[str] = []
    for r in results:
        for bucket in r["by_difficulty"]:
            if bucket not in diff_buckets:
                diff_buckets.append(bucket)

    if diff_buckets:
        lines.append("## 2. 按难度等级（Avg Recall@K）\n")
        lines.append("| Weights | " + " | ".join(f"{d.title()} |" for d in diff_buckets) + " Avg |")
        lines.append("|---|---|" + "|---:" * len(diff_buckets) + "---|")
        for r in results:
            vals = [r["by_difficulty"].get(d, {}).get("avg_recall", 0.0) for d in diff_buckets]
            avg = r["overall"]["avg_recall"]
            lines.append(
                "| "
                + _fmt_w(r["weights"])
                + " | "
                + " | ".join(_fmt(v) for v in vals)
                + f" | {_fmt(avg)} |"
            )
        lines.append("")

    # ── By failure type ───────────────────────────────────────────────
    ft_buckets: list[str] = []
    for r in results:
        for bucket in r["by_failure_type"]:
            if bucket not in ft_buckets:
                ft_buckets.append(bucket)

    if ft_buckets:
        lines.append("## 3. 按失效类型（Avg Recall@K）\n")
        lines.append("| Weights | " + " | ".join(f"{ft} |" for ft in ft_buckets) + " Avg |")
        lines.append("|---|---|" + "|---:" * len(ft_buckets) + "---|")
        for r in results:
            vals = [r["by_failure_type"].get(ft, {}).get("avg_recall", 0.0) for ft in ft_buckets]
            avg = r["overall"]["avg_recall"]
            lines.append(
                "| "
                + _fmt_w(r["weights"])
                + " | "
                + " | ".join(_fmt(v) for v in vals)
                + f" | {_fmt(avg)} |"
            )
        lines.append("")

    # ── MRR by failure type ────────────────────────────────────────────
    if ft_buckets:
        lines.append("## 4. 按失效类型（Avg MRR）\n")
        lines.append("| Weights | " + " | ".join(f"{ft} |" for ft in ft_buckets) + " Avg |")
        lines.append("|---|---|" + "|---:" * len(ft_buckets) + "---|")
        for r in results:
            vals = [r["by_failure_type"].get(ft, {}).get("avg_rr", 0.0) for ft in ft_buckets]
            avg = r["overall"]["avg_mrr"]
            lines.append(
                "| "
                + _fmt_w(r["weights"])
                + " | "
                + " | ".join(_fmt(v) for v in vals)
                + f" | {_fmt(avg)} |"
            )
        lines.append("")

    # ── Recommendation ───────────────────────────────────────────────
    if results:
        best = results[0]
        worst = results[-1]
        lines.append(
            "## 5. 推荐\n"
            f"- **当前最优**: BM25={best['weights']['bm25']:.2f}, "
            f"Semantic={best['weights']['semantic']:.2f}, "
            f"Graph={best['weights']['graph']:.2f} "
            f"(Recall={_fmt(best['overall']['avg_recall'])}, MRR={_fmt(best['overall']['avg_mrr'])})\n"
            f"- **最差**: BM25={worst['weights']['bm25']:.2f}, "
            f"Semantic={worst['weights']['semantic']:.2f}, "
            f"Graph={worst['weights']['graph']:.2f} "
            f"(Recall={_fmt(worst['overall']['avg_recall'])}, MRR={_fmt(worst['overall']['avg_mrr'])})\n"
            f"- **搜索空间**: {len(results)} 种权重组合\n"
        )

    return "\n".join(lines)


# ─── CLI ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RRF 权重调优：评估不同 BM25/Semantic/Graph 权重组合的检索效果。"
    )
    parser.add_argument(
        "--eval-cases",
        type=Path,
        default=_ROOT / "data/eval_cases.json",
        help="Path to evaluation cases JSON.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_ROOT / "external/celery",
        help="Path to the source repository for RAG indexing.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K for recall calculation.",
    )
    parser.add_argument(
        "--per-source",
        type=int,
        default=12,
        help="Number of results to keep per source before fusion.",
    )
    parser.add_argument(
        "--query-mode",
        choices=["question_only", "question_plus_entry"],
        default="question_plus_entry",
        help="Query construction mode.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=30,
        help="RRF reciprocal rank k parameter.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "reports/rag_weights_tuning.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional JSON output path for structured results.",
    )
    parser.add_argument(
        "--weights",
        default="",
        help="Comma-separated weight combos (override default grid). "
        "Format: bm25,semantic,graph[;bm25,semantic,graph[;...]] "
        "e.g. '0.33,0.33,0.34;0.25,0.05,0.70'",
    )
    return parser


def _parse_weights_arg(weights_arg: str) -> list[dict[str, float]]:
    """Parse --weights argument into list of weight dicts."""
    combos: list[dict[str, float]] = []
    for segment in weights_arg.split(";"):
        parts = [float(x.strip()) for x in segment.split(",")]
        if len(parts) != 3:
            raise ValueError(
                f"Each weight segment must have 3 comma-separated floats, got: {segment!r}"
            )
        combos.append({"bm25": parts[0], "semantic": parts[1], "graph": parts[2]})
    return combos


def main() -> int:
    args = build_parser().parse_args()

    # Load cases
    if not args.eval_cases.exists():
        print(f"Error: eval cases not found at {args.eval_cases}")
        return 1
    cases = load_eval_cases(args.eval_cases)
    print(f"Loaded {len(cases)} evaluation cases.")

    # Build retriever
    if not args.repo_root.exists():
        print(f"Error: repo root not found at {args.repo_root}")
        return 1
    print(f"Building RAG index from {args.repo_root} ...")
    retriever = build_retriever(args.repo_root)
    print(f"Index built: {len(retriever.chunks)} chunks.")

    # Determine weight combinations
    if args.weights:
        weight_combinations = _parse_weights_arg(args.weights)
    else:
        weight_combinations = DEFAULT_WEIGHT_COMBINATIONS

    print(f"Grid search over {len(weight_combinations)} weight combinations ...")
    results = grid_search(
        cases=cases,
        retriever=retriever,
        weight_combinations=weight_combinations,
        top_k=args.top_k,
        per_source=args.per_source,
        query_mode=args.query_mode,
        rrf_k=args.rrf_k,
    )

    # Write markdown report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_text = build_markdown_table(results)
    args.output.write_text(report_text + "\n", encoding="utf-8")
    print(f"\nMarkdown report saved to {args.output}")

    # Write JSON if requested
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"JSON results saved to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
