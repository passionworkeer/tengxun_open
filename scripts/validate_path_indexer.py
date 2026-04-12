#!/usr/bin/env python3
"""
DependencyPathIndexer 验证脚本

对比 PathIndexer 和传统 RRF 检索在 Type E cases 上的表现。
评估指标：
  - Type E 路径召回率
  - 与传统 RRF 检索的互补性
  - 端到端 Hard 场景提升

用法:
    python scripts/validate_path_indexer.py
    python scripts/validate_path_indexer.py --cases data/eval_cases.json --repo external/celery
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from rag import build_retriever
from rag.dependency_path_indexer import DependencyPathIndexer
from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import recall_at_k


# ─── Metrics ─────────────────────────────────────────────────────────────────

def compute_path_recall(
    cases: list[EvalCase],
    indexer: DependencyPathIndexer,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    计算 PathIndexer 对 eval cases 的召回率。

    Returns per-case and aggregate recall metrics.
    """
    type_e_recalls: list[float] = []
    type_d_recalls: list[float] = []
    all_recalls: list[float] = []
    details: list[dict[str, Any]] = []

    for case in cases:
        if case.failure_type != "Type E":
            continue

        # Search paths
        paths = indexer.search_paths(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
        )

        # Extract FQNs from path results
        path_fqns = [p.resolved_fqn for p in paths]
        gold_fqns = list(case.gold_fqns)

        # Compute recall
        recall = recall_at_k(gold_fqns, path_fqns, top_k)
        type_e_recalls.append(recall)

        # Check if any path is an exact match
        exact_match = any(gold in path_fqns for gold in gold_fqns)

        details.append({
            "case_id": case.case_id,
            "question": case.question[:80],
            "gold_fqns": gold_fqns,
            "path_fqns": path_fqns[:3],
            "recall": recall,
            "exact_match": exact_match,
            "n_paths_found": len(paths),
        })

    avg_recall = sum(type_e_recalls) / len(type_e_recalls) if type_e_recalls else 0.0
    return {
        "n_type_e": len(type_e_recalls),
        "avg_recall": round(avg_recall, 4),
        "recalls": type_e_recalls,
        "details": details,
    }


def compute_rrf_recall(
    cases: list[EvalCase],
    retriever,  # HybridRetriever
    weights: dict[str, float],
    top_k: int = 5,
    per_source: int = 12,
) -> dict[str, Any]:
    """Compute traditional RRF recall for comparison."""
    type_e_recalls: list[float] = []
    details: list[dict[str, Any]] = []

    for case in cases:
        if case.failure_type != "Type E":
            continue

        trace = retriever.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode="question_plus_entry",
            rrf_k=30,
            weights=weights,
        )

        fused_symbols = retriever.ranked_symbols(list(trace.fused_ids))
        gold_fqns = list(case.gold_fqns)
        recall = recall_at_k(gold_fqns, fused_symbols, top_k)
        type_e_recalls.append(recall)

        exact_match = any(gold in fused_symbols for gold in gold_fqns)
        details.append({
            "case_id": case.case_id,
            "recall": recall,
            "exact_match": exact_match,
        })

    avg_recall = sum(type_e_recalls) / len(type_e_recalls) if type_e_recalls else 0.0
    return {
        "n_type_e": len(type_e_recalls),
        "avg_recall": round(avg_recall, 4),
        "recalls": type_e_recalls,
        "details": details,
    }


def compute_complementarity(
    cases: list[EvalCase],
    indexer: DependencyPathIndexer,
    retriever,
    weights: dict[str, float],
    top_k: int = 5,
) -> dict[str, Any]:
    """
    分析 PathIndexer 和 RRF 的互补性：
    - 哪些 case 只有 PathIndexer 命中？
    - 哪些 case 只有 RRF 命中？
    - 哪些 case 两者都命中？
    """
    type_e_cases = [c for c in cases if c.failure_type == "Type E"]

    path_only: list[str] = []
    rrf_only: list[str] = []
    both: list[str] = []
    neither: list[str] = []

    for case in type_e_cases:
        # PathIndexer
        paths = indexer.search_paths(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
        )
        path_fqns = {p.resolved_fqn for p in paths}

        # RRF
        trace = retriever.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
            per_source=12,
            query_mode="question_plus_entry",
            rrf_k=30,
            weights=weights,
        )
        rrf_fqns = set(retriever.ranked_symbols(list(trace.fused_ids)))

        gold_set = set(case.gold_fqns)

        path_hit = bool(gold_set & path_fqns)
        rrf_hit = bool(gold_set & rrf_fqns)

        if path_hit and rrf_hit:
            both.append(case.case_id)
        elif path_hit:
            path_only.append(case.case_id)
        elif rrf_hit:
            rrf_only.append(case.case_id)
        else:
            neither.append(case.case_id)

    return {
        "n_total": len(type_e_cases),
        "path_only": path_only,
        "rrf_only": rrf_only,
        "both": both,
        "neither": neither,
        "path_coverage": len(path_only) + len(both),
        "rrf_coverage": len(rrf_only) + len(both),
        "combined_coverage": len(both) + len(path_only) + len(rrf_only),
    }


# ─── Report ──────────────────────────────────────────────────────────────────

def build_report(
    path_metrics: dict[str, Any],
    rrf_metrics: dict[str, Any],
    complementarity: dict[str, Any],
    indexer_stats: dict[str, Any],
) -> str:
    """Build Markdown comparison report."""
    lines = [
        "# DependencyPathIndexer 验证报告",
        "",
        f"**Index stats**: {indexer_stats['total_paths']} paths, "
        f"{indexer_stats['unique_fqns']} unique FQNs, "
        f"{indexer_stats['total_aliases']} aliases loaded",
        "",
    ]

    # ── Type E Recall Comparison ───────────────────────────────────────
    lines.append("## 1. Type E Recall@K 对比")
    lines.append("")
    lines.append("| 方法 | Type E Avg Recall@K | # Cases |")
    lines.append("|---|---|---|")
    lines.append(f"| **DependencyPathIndexer** | **{path_metrics['avg_recall']:.4f}** | {path_metrics['n_type_e']} |")
    lines.append(f"| RRF (baseline) | {rrf_metrics['avg_recall']:.4f} | {rrf_metrics['n_type_e']} |")

    delta = path_metrics['avg_recall'] - rrf_metrics['avg_recall']
    improvement = (delta / rrf_metrics['avg_recall'] * 100) if rrf_metrics['avg_recall'] > 0 else 0
    lines.append("")
    lines.append(f"- PathIndexer vs RRF: {delta:+.4f} ({improvement:+.1f}%)")
    if path_metrics['avg_recall'] > rrf_metrics['avg_recall']:
        lines.append("- **PathIndexer 优于 RRF**（路径索引有效）")
    elif path_metrics['avg_recall'] < rrf_metrics['avg_recall']:
        lines.append("- RRF 优于 PathIndexer（两者互补才有效）")
    else:
        lines.append("- 两者相当")
    lines.append("")

    # ── Complementarity ───────────────────────────────────────────────
    lines.append("## 2. 互补性分析")
    lines.append("")
    n = complementarity["n_total"]
    lines.append(f"总 Type E cases: {n}")
    lines.append("")
    lines.append(f"| 类别 | 数量 | 占比 | Cases |")
    lines.append(f"|---|---|---|---|")
    lines.append(
        f"| 两者都命中 | {len(complementarity['both'])} | "
        f"{len(complementarity['both'])/n*100:.1f}% | "
        f"{', '.join(complementarity['both'][:5])}{'...' if len(complementarity['both']) > 5 else ''} |"
    )
    lines.append(
        f"| **仅 PathIndexer 命中** | {len(complementarity['path_only'])} | "
        f"{len(complementarity['path_only'])/n*100:.1f}% | "
        f"{', '.join(complementarity['path_only'][:5])}{'...' if len(complementarity['path_only']) > 5 else ''} |"
    )
    lines.append(
        f"| 仅 RRF 命中 | {len(complementarity['rrf_only'])} | "
        f"{len(complementarity['rrf_only'])/n*100:.1f}% | "
        f"{', '.join(complementarity['rrf_only'][:5])}{'...' if len(complementarity['rrf_only']) > 5 else ''} |"
    )
    lines.append(
        f"| 两者都未命中 | {len(complementarity['neither'])} | "
        f"{len(complementarity['neither'])/n*100:.1f}% | "
        f"{', '.join(complementarity['neither'][:5])}{'...' if len(complementarity['neither']) > 5 else ''} |"
    )
    lines.append("")

    combined = complementarity["combined_coverage"]
    lines.append(f"**组合覆盖率**: {combined}/{n} = {combined/n*100:.1f}%")
    if len(complementarity['path_only']) > 0:
        lines.append(f"PathIndexer 独有命中 {len(complementarity['path_only'])} 条，**证明了路径索引的独特价值**")
    lines.append("")

    # ── Per-case details ───────────────────────────────────────────────
    lines.append("## 3. Type E Case 详细召回")
    lines.append("")
    lines.append("| Case ID | Question (truncated) | Gold FQNs | Path FQNs | Path Recall |")
    lines.append("|---|---|---|---|---|")
    for detail in path_metrics.get("details", [])[:20]:
        q = detail["question"][:40]
        gold = ", ".join(detail["gold_fqns"][:2])
        path_fqns = ", ".join(str(f) for f in detail["path_fqns"][:2])
        lines.append(
            f"| {detail['case_id']} | {q}... | {gold} | {path_fqns} | "
            f"{detail['recall']:.2f} |"
        )
    lines.append("")

    # ── Conclusions ───────────────────────────────────────────────────
    lines.append("## 4. 结论")
    lines.append("")
    combined_pct = complementarity["combined_coverage"] / n * 100 if n > 0 else 0
    if combined_pct > 70:
        lines.append("**结论**: PathIndexer + RRF 组合可覆盖 70%+ 的 Type E cases，路径索引有效。")
    elif combined_pct > 50:
        lines.append("**结论**: PathIndexer + RRF 组合可覆盖 50%+ 的 Type E cases，有一定互补价值。")
    else:
        lines.append("**结论**: Type E 场景仍需更多工作，PathIndexer 单独效果有限。")

    if len(complementarity['path_only']) > len(complementarity['rrf_only']):
        lines.append(
            f"PathIndexer 独有命中 {len(complementarity['path_only'])} > "
            f"RRF 独有命中 {len(complementarity['rrf_only'])}，"
            "**路径索引是关键补充**。"
        )
    elif len(complementarity['path_only']) > 0:
        lines.append(
            f"PathIndexer 独有命中 {len(complementarity['path_only'])} 条，"
            "**证明了多跳符号解析路径索引的价值**。"
        )

    lines.append("")
    lines.append("### 下一步建议")
    if path_metrics['avg_recall'] > rrf_metrics['avg_recall']:
        lines.append("1. 将 DependencyPathIndexer 集成到 HybridRetriever 中作为专项检索源")
        lines.append("2. 在 RRF 融合时为 PathIndexer 结果添加权重")
        lines.append("3. 扩展 indexer 覆盖更多的 symbol_by_name 调用变体")
    else:
        lines.append("1. PathIndexer 单独效果不如 RRF，但互补性存在")
        lines.append("2. 建议作为 RRF 的 pre-filter 或 post-ranker")
        lines.append("3. 重点改进: 覆盖更多 symbol_by_name 模式（instantiate, import_object 等）")

    return "\n".join(lines)


# ─── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="验证 DependencyPathIndexer 在 Type E cases 上的效果。"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=_ROOT / "data/eval_cases.json",
        help="Path to evaluation cases JSON.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=_ROOT / "external/celery",
        help="Path to Celery source repository.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-K for recall calculation.",
    )
    parser.add_argument(
        "--weights",
        default="0.33,0.33,0.34",
        help="RRF weights as bm25,semantic,graph (default: 0.33,0.33,0.34).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "reports/path_indexer_validation.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    # Load cases
    if not args.cases.exists():
        print(f"Error: eval cases not found at {args.cases}")
        return 1
    cases = load_eval_cases(args.cases)
    type_e_cases = [c for c in cases if c.failure_type == "Type E"]
    print(f"Loaded {len(cases)} cases, {len(type_e_cases)} Type E cases.")

    # Build indexer
    if not args.repo.exists():
        print(f"Error: repo not found at {args.repo}")
        return 1
    print(f"Building DependencyPathIndexer from {args.repo} ...")
    indexer = DependencyPathIndexer(args.repo)
    indexer.build_index()
    stats = indexer.stats()
    print(f"Index built: {stats['total_paths']} paths, {stats['total_aliases']} aliases loaded.")
    print(f"Path types: {stats['by_path_type']}")

    # Build RRF retriever (for comparison)
    print("Building RRF index ...")
    retriever = build_retriever(args.repo)
    print(f"RRF index: {len(retriever.chunks)} chunks.")

    # Parse weights
    parts = [float(x.strip()) for x in args.weights.split(",")]
    if len(parts) != 3:
        print("Error: --weights must have 3 comma-separated floats")
        return 1
    weights = {"bm25": parts[0], "semantic": parts[1], "graph": parts[2]}

    # Compute metrics
    print("\n=== Computing PathIndexer recall ===")
    path_metrics = compute_path_recall(cases, indexer, top_k=args.top_k)
    print(f"PathIndexer Type E recall: {path_metrics['avg_recall']:.4f}")

    print("\n=== Computing RRF baseline recall ===")
    rrf_metrics = compute_rrf_recall(
        cases, retriever, weights, top_k=args.top_k
    )
    print(f"RRF Type E recall: {rrf_metrics['avg_recall']:.4f}")

    print("\n=== Computing complementarity ===")
    complementarity = compute_complementarity(
        cases, indexer, retriever, weights, top_k=args.top_k
    )
    print(f"Combined coverage: {complementarity['combined_coverage']}/{complementarity['n_total']}")

    # Build report
    report = build_report(path_metrics, rrf_metrics, complementarity, stats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report + "\n", encoding="utf-8")
    print(f"\nReport saved to {args.output}")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                {
                    "path_metrics": path_metrics,
                    "rrf_metrics": rrf_metrics,
                    "complementarity": complementarity,
                    "indexer_stats": stats,
                    "weights": weights,
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"JSON saved to {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
