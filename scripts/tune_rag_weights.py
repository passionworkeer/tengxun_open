#!/usr/bin/env python3
"""
RRF 贝叶斯权重调优脚本

用贝叶斯优化（Optuna TPE）替代网格穷举，针对 Type E（Hard 场景瓶颈）
定向调 BM25/Semantic/Graph 权重，并输出参数敏感性分析。

用法:
    python scripts/tune_rag_weights.py --trials 50 --focus-type-e
    python scripts/tune_rag_weights.py --trials 30 --top-k 5 --output reports/bayesian_weights.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import optuna
from optuna.trial import Trial as _Trial

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from rag import HybridRetriever, build_retriever
from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import recall_at_k, reciprocal_rank


# ─── Recall function ────────────────────────────────────────────────────────

def compute_recall(
    cases: list[EvalCase],
    retriever: HybridRetriever,
    weights: dict[str, float],
    top_k: int,
    per_source: int,
    query_mode: str,
    rrf_k: int,
) -> dict[str, Any]:
    """Run retrieval and compute per-case recall for each failure-type bucket."""
    ft_recalls: dict[str, list[float]] = defaultdict(list)
    all_recalls: list[float] = []

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
            query_text=" ".join(
                filter(None, [case.question, case.entry_symbol, case.entry_file])
            ),
            entry_symbol=case.entry_symbol,
        )
        chunk_recall = recall_at_k(case.gold_fqns, fused_symbols, top_k)
        expanded_recall = recall_at_k(case.gold_fqns, fused_expanded, top_k)
        best_recall = max(chunk_recall, expanded_recall)

        all_recalls.append(best_recall)
        if case.failure_type:
            ft_recalls[case.failure_type].append(best_recall)

    def _avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "overall_avg_recall": _avg(all_recalls),
        "overall_mrr": _avg(
            [
                reciprocal_rank(case.gold_fqns, retriever.ranked_symbols(list(
                    retriever.retrieve_with_trace(
                        question=case.question,
                        entry_symbol=case.entry_symbol,
                        entry_file=case.entry_file,
                        top_k=top_k,
                        per_source=per_source,
                        query_mode=query_mode,
                        rrf_k=rrf_k,
                        weights=weights,
                    ).fused_ids
                )))
                for case in cases
            ]
        ),
        "n": len(all_recalls),
        "by_ft": {
            ft: {"avg_recall": _avg(recalls), "n": len(recalls)}
            for ft, recalls in ft_recalls.items()
        },
    }


# ─── One retrieval run (cached in-memory per weight combo) ──────────────────

# In-process cache: weight_key -> {case_id -> trace}
_trace_cache: dict[str, dict[str, Any]] = {}


def _weights_key(w: dict[str, float]) -> str:
    return f"{w['bm25']:.4f},{w['semantic']:.4f},{w['graph']:.4f}"


def _run_retrieval_once(
    cases: list[EvalCase],
    weights: dict[str, float],
    top_k: int,
    per_source: int,
    query_mode: str,
    rrf_k: int,
) -> None:
    global retriever
    """Pre-populate trace cache for all cases with given weights (one pass)."""
    key = _weights_key(weights)
    if key in _trace_cache:
        return
    cache: dict[str, Any] = {}
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
            query_text=" ".join(
                filter(None, [case.question, case.entry_symbol, case.entry_file])
            ),
            entry_symbol=case.entry_symbol,
        )
        cache[case.case_id] = {
            "fused_symbols": fused_symbols,
            "fused_expanded": fused_expanded,
            "trace": trace,
        }
    _trace_cache[key] = cache


def _recall_from_cache(
    cases: list[EvalCase],
    weights: dict[str, float],
) -> dict[str, Any]:
    """Compute recall from pre-cached traces (no additional retrieval needed)."""
    key = _weights_key(weights)
    cache = _trace_cache.get(key, {})

    ft_recalls: dict[str, list[float]] = defaultdict(list)
    all_recalls: list[float] = []
    all_rrs: list[float] = []

    for case in cases:
        cached = cache.get(case.case_id)
        if cached is None:
            all_recalls.append(0.0)
            all_rrs.append(0.0)
            continue
        fused_symbols = cached["fused_symbols"]
        fused_expanded = cached["fused_expanded"]
        chunk_recall = recall_at_k(case.gold_fqns, fused_symbols, top_k)
        expanded_recall = recall_at_k(case.gold_fqns, fused_expanded, top_k)
        best_recall = max(chunk_recall, expanded_recall)
        rr = reciprocal_rank(case.gold_fqns, fused_symbols)
        all_recalls.append(best_recall)
        all_rrs.append(rr)
        if case.failure_type:
            ft_recalls[case.failure_type].append(best_recall)

    def _avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    return {
        "overall_avg_recall": _avg(all_recalls),
        "overall_mrr": _avg(all_rrs),
        "n": len(all_recalls),
        "by_ft": {
            ft: {"avg_recall": _avg(recalls), "n": len(recalls)}
            for ft, recalls in ft_recalls.items()
        },
    }


# ─── Baseline recalls (uniform weights) ────────────────────────────────────

BASELINE_WEIGHTS = {"bm25": 0.33, "semantic": 0.33, "graph": 0.34}

# Will be set in main()
top_k: int = 5
per_source: int = 12
query_mode: str = "question_plus_entry"
rrf_k: int = 30
focus_types: list[str] = []
all_cases: list[EvalCase] = []
retriever: HybridRetriever | None = None


# ─── Optuna objective ────────────────────────────────────────────────────────

def _objective(trial: _Trial) -> float:  # type: ignore[no-redef]
    global retriever
    """Optuna objective: maximize focus-type recall, break ties with overall recall."""
    # Sample from Dirichlet to ensure weights sum to 1 and are non-negative
    bm25_raw = trial.suggest_float("bm25_raw", 0.01, 1.0, step=0.01)
    sem_raw = trial.suggest_float("semantic_raw", 0.01, 1.0, step=0.01)
    total = bm25_raw + sem_raw + 0.01
    bm25 = bm25_raw / total
    sem = sem_raw / total
    graph = 1.0 - bm25 - sem

    # Ensure all weights >= 0.01 (avoid degenerate solutions)
    if graph < 0.01:
        graph = 0.01
        remaining = 0.99
        bm25 = remaining * bm25 / (bm25 + sem) if (bm25 + sem) > 0 else 0.495
        sem = remaining - bm25

    weights = {"bm25": round(bm25, 4), "semantic": round(sem, 4), "graph": round(graph, 4)}

    _run_retrieval_once(all_cases, weights, top_k, per_source, query_mode, rrf_k)
    result = _recall_from_cache(all_cases, weights)

    # Primary: focus types recall
    if focus_types:
        focus_recalls = [
            result["by_ft"].get(ft, {}).get("avg_recall", 0.0)
            for ft in focus_types
            if ft in result["by_ft"]
        ]
        primary = sum(focus_recalls) / len(focus_recalls) if focus_recalls else 0.0
    else:
        primary = result["overall_avg_recall"]

    # Secondary: overall recall (for tie-breaking)
    secondary = result["overall_avg_recall"]

    trial.set_user_attr("weights", weights)
    trial.set_user_attr("overall_recall", result["overall_avg_recall"])
    trial.set_user_attr("overall_mrr", result["overall_mrr"])
    trial.set_user_attr("by_ft", result["by_ft"])

    # Multi-objective: maximize primary recall, use secondary as tie-breaker
    # Optuna maximizes, so return primary directly
    return primary


# ─── Parameter sensitivity analysis ─────────────────────────────────────────

def _sensitivity_analysis() -> dict[str, Any]:
    """
    定向分析每个参数对 Type E recall 的敏感性。

    思路：固定其他两个参数为 baseline，只变化目标参数，
    观察 recall 随该参数的变化趋势。
    """
    global top_k, per_source, query_mode, rrf_k, all_cases, retriever
    results: dict[str, list[tuple[float, float]]] = {}
    type_e_cases = [c for c in all_cases if c.failure_type == "Type E"]

    if not type_e_cases:
        return {"error": "No Type E cases found"}

    # ── Graph weight sweep (most relevant for multi-hop Type E) ──
    graph_sweep: list[tuple[float, float]] = []
    for graph_w in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        remaining = 1.0 - graph_w
        bm25_w = remaining / 2
        sem_w = remaining / 2
        weights = {"bm25": round(bm25_w, 4), "semantic": round(sem_w, 4), "graph": round(graph_w, 4)}
        _run_retrieval_once(all_cases, weights, top_k, per_source, query_mode, rrf_k)
        res = _recall_from_cache(all_cases, weights)
        recall = res["by_ft"].get("Type E", {}).get("avg_recall", 0.0)
        graph_sweep.append((graph_w, recall))
    results["graph_weight"] = graph_sweep

    # ── BM25 weight sweep ──
    bm25_sweep: list[tuple[float, float]] = []
    for bm25_w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
        remaining = 1.0 - bm25_w
        graph_w = remaining * 0.8
        sem_w = remaining * 0.2
        weights = {"bm25": round(bm25_w, 4), "semantic": round(sem_w, 4), "graph": round(graph_w, 4)}
        _run_retrieval_once(all_cases, weights, top_k, per_source, query_mode, rrf_k)
        res = _recall_from_cache(all_cases, weights)
        recall = res["by_ft"].get("Type E", {}).get("avg_recall", 0.0)
        bm25_sweep.append((bm25_w, recall))
    results["bm25_weight"] = bm25_sweep

    # ── Semantic weight sweep ──
    sem_sweep: list[tuple[float, float]] = []
    for sem_w in [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]:
        remaining = 1.0 - sem_w
        graph_w = remaining * 0.8
        bm25_w = remaining * 0.2
        weights = {"bm25": round(bm25_w, 4), "semantic": round(sem_w, 4), "graph": round(graph_w, 4)}
        _run_retrieval_once(all_cases, weights, top_k, per_source, query_mode, rrf_k)
        res = _recall_from_cache(all_cases, weights)
        recall = res["by_ft"].get("Type E", {}).get("avg_recall", 0.0)
        sem_sweep.append((sem_w, recall))
    results["semantic_weight"] = sem_sweep

    # ── Analyze sensitivity ──
    sensitivity: dict[str, float] = {}
    for param, sweep in results.items():
        if len(sweep) >= 2:
            vals = [v for _, v in sweep]
            delta = max(vals) - min(vals)
            sensitivity[param] = round(delta, 4)

    most_sensitive = max(sensitivity, key=sensitivity.get) if sensitivity else None

    # Find optimal for each parameter
    optimal: dict[str, float] = {}
    for param, sweep in results.items():
        best_w, best_r = max(sweep, key=lambda x: x[1])
        optimal[param] = best_w

    return {
        "sensitivity": sensitivity,
        "most_sensitive_param": most_sensitive,
        "optimal_per_param": optimal,
        "sweeps": results,
    }


# ─── Baseline comparison ─────────────────────────────────────────────────────

def _baseline_comparison() -> dict[str, Any]:
    """Compute baseline (uniform weights) and best Bayesian result."""
    global retriever
    _run_retrieval_once(
        all_cases, BASELINE_WEIGHTS,
        top_k, per_source, query_mode, rrf_k
    )
    return _recall_from_cache(all_cases, BASELINE_WEIGHTS)


# ─── Report generation ──────────────────────────────────────────────────────

def build_markdown_report(
    study: optuna.Study,
    sensitivity: dict[str, Any],
    baseline: dict[str, Any],
    best_weights: dict[str, float],
    focus_types: list[str],
    trials_run: int,
) -> str:
    """Build a Markdown report with Bayesian optimization results."""
    lines: list[str] = [
        "# RRF 贝叶斯权重调优报告",
        "",
        f"**优化目标**: {' + '.join(focus_types) if focus_types else 'Overall Recall@K'}",
        f"**优化方法**: Optuna TPE (Tree-structured Parzen Estimator)",
        f"**试验次数**: {trials_run}",
        f"**搜索空间**: BM25, Semantic (Graph = 1 - BM25 - Semantic)",
        "",
    ]

    # ── Section 1: Baseline vs Optimized ────────────────────────────
    lines.append("## 1. Baseline vs Bayesian 最优")
    lines.append("")
    lines.append("| 权重配置 | Overall Recall | Overall MRR | Type E Recall | Type D Recall |")
    lines.append("|---|---|---|---|---|")

    baseline_type_e = baseline.get("by_ft", {}).get("Type E", {}).get("avg_recall", 0.0)
    baseline_type_d = baseline.get("by_ft", {}).get("Type D", {}).get("avg_recall", 0.0)

    best_result = study.best_value
    best_overall = study.best_trial.user_attrs.get("overall_recall", 0.0)
    best_mrr = study.best_trial.user_attrs.get("overall_mrr", 0.0)
    best_ft = study.best_trial.user_attrs.get("by_ft", {})
    best_type_e = best_ft.get("Type E", {}).get("avg_recall", 0.0)
    best_type_d = best_ft.get("Type D", {}).get("avg_recall", 0.0)

    baseline_str = (
        f"bm25={BASELINE_WEIGHTS['bm25']:.2f} "
        f"sem={BASELINE_WEIGHTS['semantic']:.2f} "
        f"gr={BASELINE_WEIGHTS['graph']:.2f}"
    )
    best_str = (
        f"bm25={best_weights['bm25']:.2f} "
        f"sem={best_weights['semantic']:.2f} "
        f"gr={best_weights['graph']:.2f}"
    )

    lines.append(
        f"| baseline ({baseline_str}) | {baseline['overall_avg_recall']:.4f} | "
        f"{baseline['overall_mrr']:.4f} | {baseline_type_e:.4f} | {baseline_type_d:.4f} |"
    )
    lines.append(
        f"| **Bayesian 最优** ({best_str}) | **{best_overall:.4f}** | "
        f"**{best_mrr:.4f}** | **{best_type_e:.4f}** | **{best_type_d:.4f}** |"
    )
    delta_e = best_type_e - baseline_type_e
    delta_o = best_overall - baseline["overall_avg_recall"]
    lines.append("")
    lines.append(f"- Type E recall 提升: {delta_e:+.4f} ({delta_e/baseline_type_e*100:+.1f}%)" if baseline_type_e else "- (no Type E baseline)")
    lines.append(f"- Overall recall 提升: {delta_o:+.4f} ({delta_o/baseline['overall_avg_recall']*100:+.1f}%)" if baseline["overall_avg_recall"] else "")
    lines.append("")

    # ── Section 2: Parameter Sensitivity ───────────────────────────
    lines.append("## 2. 参数敏感性分析（定向调参）")
    lines.append("")
    if "error" not in sensitivity:
        sens = sensitivity.get("sensitivity", {})
        most = sensitivity.get("most_sensitive_param", "N/A")
        optimal = sensitivity.get("optimal_per_param", {})

        lines.append(f"**最敏感参数**: `{most}` (Type E recall delta = {sens.get(most, 0):.4f})")
        lines.append("")
        lines.append("各参数最优值（Type E recall 最优时）:")
        for param, val in optimal.items():
            lines.append(f"- {param}: {val:.2f}")
        lines.append("")
        lines.append("### 参数 sweep 详情")
        lines.append("")
        for param, sweep in sensitivity.get("sweeps", {}).items():
            lines.append(f"**{param}** (Type E Recall@K):")
            for w, r in sweep:
                bar = "█" * int(r * 20)
                lines.append(f"  {w:.2f}: {r:.4f} {bar}")
            lines.append("")
    else:
        lines.append(f"无法进行敏感性分析: {sensitivity['error']}")
        lines.append("")

    # ── Section 3: Top 5 Bayesian trials ───────────────────────────
    lines.append("## 3. Bayesian 优化 Top-5 试验")
    lines.append("")
    sorted_trials = sorted(
        study.trivals,
        key=lambda t: (t.value or 0, t.user_attrs.get("overall_recall", 0)),
        reverse=True,
    )
    lines.append("| # | BM25 | Semantic | Graph | Primary Recall | Overall Recall | Type E |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, trial in enumerate(sorted_trials[:5]):
        w = trial.user_attrs.get("weights", {})
        ft = trial.user_attrs.get("by_ft", {})
        type_e_r = ft.get("Type E", {}).get("avg_recall", 0.0)
        lines.append(
            f"| {i+1} | {w.get('bm25', 0):.2f} | {w.get('semantic', 0):.2f} | "
            f"{w.get('graph', 0):.2f} | {trial.value or 0:.4f} | "
            f"{trial.user_attrs.get('overall_recall', 0):.4f} | {type_e_r:.4f} |"
        )
    lines.append("")

    # ── Section 4: Conclusions ─────────────────────────────────────
    lines.append("## 4. 调参结论")
    lines.append("")
    if "error" not in sensitivity and sensitivity.get("most_sensitive_param"):
        most = sensitivity["most_sensitive_param"]
        sens = sensitivity["sensitivity"]
        lines.append(f"### 参数重要性排序（Type E 场景）")
        sorted_params = sorted(sens.items(), key=lambda x: x[1], reverse=True)
        for rank, (param, delta) in enumerate(sorted_params, 1):
            lines.append(f"{rank}. **{param}**: Type E recall 波动幅度 = {delta:.4f}")
        lines.append("")
        lines.append("### 推荐权重组合（有解释的）")
        if best_type_e > baseline_type_e:
            lines.append(
                f"- **最优组合**: BM25={best_weights['bm25']:.2f}, "
                f"Semantic={best_weights['semantic']:.2f}, Graph={best_weights['graph']:.2f}"
            )
            if most == "graph_weight":
                lines.append(
                    f"  - 理由: Graph 权重对 Type E 场景最敏感，"
                    f"从 baseline {BASELINE_WEIGHTS['graph']:.2f} "
                    f"调整到 {best_weights['graph']:.2f} 带来最大收益"
                )
            elif most == "bm25_weight":
                lines.append(
                    f"  - 理由: BM25 对 Type E 场景最敏感，"
                    f"提高 BM25 权重有助于检索 symbol_by_name 调用的字符串字面量"
                )
        else:
            lines.append("- 当前权重组合对 Type E 无显著提升，Hard 场景需要更根本的方法（如 DependencyPathIndexer）")
    else:
        lines.append("- 无法得出参数敏感性结论（数据不足）")

    lines.append("")
    lines.append("### 下一步建议")
    if best_type_e < 0.5:
        lines.append(
            "1. **Type E recall 仍在 0.5 以下，RRF 权重调优已触及天花板**"
        )
        lines.append(
            "2. **应转向 DependencyPathIndexer**：索引 A→B→C 路径，"
            "专门解决 symbol_by_name 多跳检索问题"
        )
        lines.append(
            "3. 当前最优权重仅提供边际收益，核心技术突破在于路径索引"
        )
    elif best_type_e < 0.7:
        lines.append("1. Type E recall 有改善，继续探索 graph 权重上界")
        lines.append("2. 考虑结合 DependencyPathIndexer 作为专项检索")
    else:
        lines.append("1. Type E recall 已达到较好水平，可固定当前权重")
        lines.append("2. 考虑端到端验证 ConditionalRetriever 策略")

    return "\n".join(lines)


# ─── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RRF 贝叶斯权重调优：用 Optuna TPE 替代网格穷举，定向优化 Type E 场景。"
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
        help="Number of results per source before fusion.",
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
        "--trials",
        type=int,
        default=50,
        help="Number of Bayesian optimization trials.",
    )
    parser.add_argument(
        "--focus-type-e",
        action="store_true",
        help="Optimize specifically for Type E recall (Hard 场景瓶颈).",
    )
    parser.add_argument(
        "--focus-types",
        type=str,
        default="",
        help="Comma-separated failure types to focus on (e.g. 'Type E,Type D').",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "reports/bayesian_weights.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional JSON output path for structured results.",
    )
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Skip the parameter sensitivity sweep (faster, only Bayesian).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    return parser


def main() -> int:
    global top_k, per_source, query_mode, rrf_k, focus_types, all_cases, retriever

    args = build_parser().parse_args()

    # Load cases
    if not args.eval_cases.exists():
        print(f"Error: eval cases not found at {args.eval_cases}")
        return 1
    all_cases = load_eval_cases(args.eval_cases)
    print(f"Loaded {len(all_cases)} evaluation cases.")

    # Focus types
    if args.focus_type_e:
        focus_types = ["Type E"]
    elif args.focus_types:
        focus_types = [t.strip() for t in args.focus_types.split(",")]
    else:
        focus_types = []
    if focus_types:
        print(f"Focus types: {focus_types}")
    else:
        print("Optimizing for overall Recall@K (no focus types)")

    # Config
    top_k = args.top_k
    per_source = args.per_source
    query_mode = args.query_mode
    rrf_k = args.rrf_k

    # Build retriever
    if not args.repo_root.exists():
        print(f"Error: repo root not found at {args.repo_root}")
        return 1
    print(f"Building RAG index from {args.repo_root} ...")
    retriever = build_retriever(args.repo_root)
    print(f"Index built: {len(retriever.chunks)} chunks.")

    # ── Sensitivity analysis (pre-Bayesian) ──────────────────────────
    sensitivity: dict[str, Any] = {}
    if not args.skip_sensitivity:
        print("\n=== Phase 1: Parameter Sensitivity Analysis ===")
        sensitivity = _sensitivity_analysis()
        if "error" not in sensitivity:
            sens = sensitivity.get("sensitivity", {})
            most = sensitivity.get("most_sensitive_param", "N/A")
            print(f"Most sensitive parameter for Type E: {most}")
            for param, delta in sorted(sens.items(), key=lambda x: x[1], reverse=True):
                opt = sensitivity.get("optimal_per_param", {}).get(param, "?")
                print(f"  {param}: delta={delta:.4f}, optimal={opt:.2f}")
        else:
            print(f"Sensitivity analysis skipped: {sensitivity.get('error')}")

    # ── Baseline ────────────────────────────────────────────────────
    print("\n=== Phase 2: Baseline (uniform weights) ===")
    baseline = _baseline_comparison()
    baseline_e = baseline.get("by_ft", {}).get("Type E", {}).get("avg_recall", 0.0)
    print(f"Baseline: overall={baseline['overall_avg_recall']:.4f}, Type E={baseline_e:.4f}")

    # ── Bayesian optimization ───────────────────────────────────────
    print(f"\n=== Phase 3: Bayesian Optimization ({args.trials} trials) ===")

    # Prune trials with 0 improvement for 10 consecutive trials
    def _pruner(trial: optuna.trial.Trial) -> optuna.trial.TrialState:
        # Simple median pruner: stop if no improvement for 5 trials
        study = trial.study
        if len(study.trials) < 5:
            return optuna.trial.TrialState.RUNNING
        recent = study.trials[-5:]
        best_recent = max((t.value or 0) for t in recent)
        if (trial.value or 0) < best_recent * 0.8:
            return optuna.trial.TrialState.PRUNED
        return optuna.trial.TrialState.RUNNING

    sampler = optuna.samplers.TPESampler(seed=args.seed)
    pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)
    study = optuna.create_study(
        study_name="rrf_weight_optimization",
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
    )

    study.optimize(_objective, n_trials=args.trials, show_progress_bar=True)

    best_weights = study.best_trial.user_attrs.get("weights", {})
    best_result = study.best_value
    print(f"\nBest trial: {best_weights}")
    print(f"Best primary recall: {best_result:.4f}")
    print(f"Best overall recall: {study.best_trial.user_attrs.get('overall_recall', 0):.4f}")
    print(f"Best Type E recall: {study.best_trial.user_attrs.get('by_ft', {}).get('Type E', {}).get('avg_recall', 0):.4f}")

    # ── Report ───────────────────────────────────────────────────────
    report = build_markdown_report(
        study=study,
        sensitivity=sensitivity,
        baseline=baseline,
        best_weights=best_weights,
        focus_types=focus_types,
        trials_run=args.trials,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"\nReport saved to {args.output}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                {
                    "best_weights": best_weights,
                    "best_primary_recall": best_result,
                    "best_overall_recall": study.best_trial.user_attrs.get("overall_recall", 0),
                    "best_type_e_recall": study.best_trial.user_attrs.get("by_ft", {}).get("Type E", {}).get("avg_recall", 0),
                    "baseline": baseline,
                    "sensitivity": sensitivity,
                    "n_trials": args.trials,
                    "n_cases": len(all_cases),
                    "focus_types": focus_types,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"JSON results saved to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
