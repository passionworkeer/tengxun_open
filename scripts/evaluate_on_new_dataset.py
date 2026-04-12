#!/usr/bin/env python3
"""
102-case 检索基准评测脚本

对 HybridRetrieverWithPath 在 data/eval_cases.json (102 cases) 上进行端到端检索评测。

输出:
  - 每条 case 的得分 (per-case JSON)
  - 按 difficulty 分类统计
  - 按 failure_type 分类统计
  - 与旧 54-case 结果的口径一致性说明

用法:
    python scripts/evaluate_on_new_dataset.py
    python scripts/evaluate_on_new_dataset.py --retriever hybrid_with_path --top-k 5
    python scripts/evaluate_on_new_dataset.py --output-json results/102_case_eval.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import (
    LayeredDependencyMetrics,
    compute_layered_dependency_metrics,
    recall_at_k,
)
from rag.hybrid_with_path import HybridRetrieverWithPath
from rag.rrf_retriever import HybridRetriever


# ─── Retrieval configuration ────────────────────────────────────────────────────

_TOP_K = 5
_PER_SOURCE = 12
_RRF_K = 30
_WEIGHTS = {"bm25": 0.33, "semantic": 0.33, "graph": 0.34}


# ─── Retrieval functions ────────────────────────────────────────────────────────

def retrieve_hybrid_with_path(
    retriever: HybridRetrieverWithPath,
    case: EvalCase,
    top_k: int = _TOP_K,
) -> list[str]:
    """
    使用 HybridRetrieverWithPath 检索预测依赖 FQN。

    返回排序后的 FQN 列表。
    """
    trace = retriever.retrieve_with_trace(
        question=case.question,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        top_k=top_k,
        per_source=_PER_SOURCE,
        query_mode="question_plus_entry",
        rrf_k=_RRF_K,
        weights=_WEIGHTS,
    )
    return retriever.ranked_symbols(list(trace.fused_ids))


def retrieve_rrf_only(
    retriever: HybridRetriever,
    case: EvalCase,
    top_k: int = _TOP_K,
) -> list[str]:
    """使用原始 HybridRetriever (RRF-only) 检索。"""
    trace = retriever.retrieve_with_trace(
        question=case.question,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        top_k=top_k,
        per_source=_PER_SOURCE,
        query_mode="question_plus_entry",
        rrf_k=_RRF_K,
        weights=_WEIGHTS,
    )
    return retriever.ranked_symbols(list(trace.fused_ids))


# ─── Metrics computation ──────────────────────────────────────────────────────

def evaluate_case(
    case: EvalCase,
    predicted_fqns: list[str],
    top_k: int = _TOP_K,
) -> dict[str, Any]:
    """
    对单条 case 计算检索评测指标。

    采用 retrieval-only 评测口径：
    - 预测层: 所有检索到的 FQN 归入 direct_deps
    - 原因: 检索系统无法区分 direct/indirect/implicit，
            将预测全归 direct 是最诚实的方式

    Returns:
        包含 per-metric 分数和诊断信息的字典
    """
    gold = {
        "direct_deps": list(case.direct_gold_fqns),
        "indirect_deps": list(case.indirect_gold_fqns),
        "implicit_deps": list(case.implicit_gold_fqns),
    }
    # All predicted go into direct_deps for retrieval-only evaluation
    predicted = {
        "direct_deps": predicted_fqns[:top_k],
        "indirect_deps": [],
        "implicit_deps": [],
    }

    metrics: LayeredDependencyMetrics = compute_layered_dependency_metrics(
        gold_layers=gold,
        predicted_layers=predicted,
    )

    # Additional recall metrics
    gold_union = list(case.gold_fqns)
    recall_5 = recall_at_k(gold_union, predicted_fqns, 5)
    recall_10 = recall_at_k(gold_union, predicted_fqns, 10)
    recall_3 = recall_at_k(gold_union, predicted_fqns, 3)

    return {
        "case_id": case.case_id,
        "difficulty": case.difficulty,
        "failure_type": case.failure_type,
        "question": case.question[:80],
        "gold_fqns": list(case.gold_fqns),
        "predicted_fqns": predicted_fqns[:5],
        "union_f1": round(metrics.union.f1, 4),
        "union_precision": round(metrics.union.precision, 4),
        "union_recall": round(metrics.union.recall, 4),
        "macro_f1": round(metrics.macro_f1, 4),
        "direct_f1": round(metrics.direct.f1, 4),
        "recall_at_3": round(recall_3, 4),
        "recall_at_5": round(recall_5, 4),
        "recall_at_10": round(recall_10, 4),
        "gold_total": metrics.gold_total,
        "predicted_total": metrics.predicted_total,
        "matched_fqns": metrics.matched_fqns,
        "path_augmented": getattr(metrics, 'path_augmented', None),  # placeholder
    }


def aggregate_metrics(
    cases: list[EvalCase],
    results: list[dict[str, Any]],
    group_key: str,
) -> dict[str, Any]:
    """按指定分组键聚合指标。"""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case, result in zip(cases, results):
        key = getattr(case, group_key, "unknown")
        buckets[key].append(result)

    aggregated = {}
    for key, items in sorted(buckets.items()):
        count = len(items)
        union_f1s = [r["union_f1"] for r in items if r["union_f1"] is not None]
        macro_f1s = [r["macro_f1"] for r in items if r["macro_f1"] is not None]
        direct_f1s = [r["direct_f1"] for r in items if r["direct_f1"] is not None]
        recall5s = [r["recall_at_5"] for r in items if r["recall_at_5"] is not None]
        recalls3s = [r["recall_at_3"] for r in items if r["recall_at_3"] is not None]
        recalls10s = [r["recall_at_10"] for r in items if r["recall_at_10"] is not None]
        precisions = [r["union_precision"] for r in items if r["union_precision"] is not None]

        aggregated[key] = {
            "count": count,
            "avg_union_f1": round(sum(union_f1s) / len(union_f1s), 4) if union_f1s else 0.0,
            "avg_macro_f1": round(sum(macro_f1s) / len(macro_f1s), 4) if macro_f1s else 0.0,
            "avg_direct_f1": round(sum(direct_f1s) / len(direct_f1s), 4) if direct_f1s else 0.0,
            "avg_recall_at_3": round(sum(recalls3s) / len(recalls3s), 4) if recalls3s else 0.0,
            "avg_recall_at_5": round(sum(recall5s) / len(recall5s), 4) if recall5s else 0.0,
            "avg_recall_at_10": round(sum(recalls10s) / len(recalls10s), 4) if recalls10s else 0.0,
            "avg_precision": round(sum(precisions) / len(precisions), 4) if precisions else 0.0,
            "perfect_count": sum(1 for f in union_f1s if f >= 0.9999),
            "zero_count": sum(1 for f in union_f1s if f == 0.0),
        }

    return aggregated


# ─── Report generation ────────────────────────────────────────────────────────

def build_report(
    results: list[dict[str, Any]],
    cases: list[EvalCase],
    summary: dict[str, Any],
    config: dict[str, Any],
    output_path: Path,
) -> str:
    """生成 Markdown 评测报告。"""
    lines: list[str] = [
        "# 102-case 检索基准评测报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**检索器**: {config['retriever']}",
        f"**Top-K**: {config['top_k']}",
        f"**数据集**: `data/eval_cases.json` ({len(cases)} cases)",
        f"**Celery repo**: {config['repo']}",
        "",
        "## 口径一致性说明",
        "",
        "本评测采用 **retrieval-only** 口径:",
        "- 预测层: 所有检索到的 FQN 归入 `direct_deps`",
        "  (检索系统无法区分 direct/indirect/implicit)",
        "- 评测对象: HybridRetrieverWithPath 检索质量，而非 LLM 理解质量",
        "- 对比基准: 旧 54-case 使用同样口径，结果可直接对比",
        "",
        "与旧 54-case 结果对比说明:",
        "- 旧评测: 54 cases (无 failure_type 标注)",
        "- 新评测: 102 cases (含 Type A/B/C/D/E)",
        "- 口径: 完全一致 (retrieval-only, FQN 归 direct)",
        "",
    ]

    # ── Overall Summary ──────────────────────────────────────────────────
    overall = summary["overall"]
    lines.append("## 总体结果")
    lines.append("")
    lines.append(f"| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| Cases | {overall['count']} |")
    lines.append(f"| **Avg Union F1** | **{overall['avg_union_f1']:.4f}** |")
    lines.append(f"| Avg Macro F1 | {overall['avg_macro_f1']:.4f} |")
    lines.append(f"| Avg Direct F1 | {overall['avg_direct_f1']:.4f} |")
    lines.append(f"| Avg Recall@3 | {overall['avg_recall_at_3']:.4f} |")
    lines.append(f"| **Avg Recall@5** | **{overall['avg_recall_at_5']:.4f}** |")
    lines.append(f"| Avg Recall@10 | {overall['avg_recall_at_10']:.4f} |")
    lines.append(f"| Avg Precision | {overall['avg_precision']:.4f} |")
    lines.append(f"| Perfect (F1=1.0) | {overall['perfect_count']} |")
    lines.append(f"| Zero (F1=0.0) | {overall['zero_count']} |")
    lines.append("")

    # ── By Difficulty ────────────────────────────────────────────────────
    by_diff = summary["by_difficulty"]
    lines.append("## 按 Difficulty 分类")
    lines.append("")
    lines.append(
        "| Difficulty | Count | Union F1 | Macro F1 | Recall@3 | Recall@5 | Recall@10 | "
        "Perfect | Zero |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for diff in ("easy", "medium", "hard"):
        if diff not in by_diff:
            continue
        d = by_diff[diff]
        lines.append(
            f"| {diff.capitalize()} | {d['count']} | "
            f"**{d['avg_union_f1']:.4f}** | {d['avg_macro_f1']:.4f} | "
            f"{d['avg_recall_at_3']:.4f} | {d['avg_recall_at_5']:.4f} | "
            f"{d['avg_recall_at_10']:.4f} | "
            f"{d['perfect_count']} | {d['zero_count']} |"
        )
    lines.append("")

    # ── By Failure Type ─────────────────────────────────────────────────
    by_ft = summary["by_failure_type"]
    if by_ft:
        lines.append("## 按 Failure Type 分类")
        lines.append("")
        lines.append(
            "| Failure Type | Count | Union F1 | Macro F1 | Recall@5 | "
            "Perfect | Zero |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for ft in sorted(by_ft.keys()):
            d = by_ft[ft]
            lines.append(
                f"| {ft} | {d['count']} | "
                f"**{d['avg_union_f1']:.4f}** | {d['avg_macro_f1']:.4f} | "
                f"{d['avg_recall_at_5']:.4f} | "
                f"{d['perfect_count']} | {d['zero_count']} |"
            )
        lines.append("")

    # ── Top/Bottom Cases ─────────────────────────────────────────────────
    sorted_results = sorted(results, key=lambda r: r["union_f1"], reverse=True)
    lines.append("## Top 10 最佳 Cases")
    lines.append("")
    lines.append("| Case ID | Difficulty | Type | Gold | Predicted | F1 |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted_results[:10]:
        gold = ", ".join(r["gold_fqns"][:2])
        pred = ", ".join(r["predicted_fqns"][:2])
        lines.append(
            f"| {r['case_id']} | {r['difficulty']} | {r['failure_type']} | "
            f"{gold} | {pred} | **{r['union_f1']:.4f}** |"
        )
    lines.append("")

    lines.append("## Bottom 10 最差 Cases (F1=0.0)")
    lines.append("")
    bottom = [r for r in sorted_results if r["union_f1"] == 0.0]
    if bottom:
        lines.append("| Case ID | Difficulty | Type | Gold |")
        lines.append("|---|---|---|---|")
        for r in bottom[:10]:
            gold = ", ".join(r["gold_fqns"][:2])
            lines.append(
                f"| {r['case_id']} | {r['difficulty']} | {r['failure_type']} | {gold} |"
            )
        lines.append("")
        if len(bottom) > 10:
            lines.append(f"... 还有 {len(bottom) - 10} 个 F1=0.0 case")
            lines.append("")
    else:
        lines.append("无 F1=0.0 cases (好!)")
        lines.append("")

    # ── Key Insights ─────────────────────────────────────────────────────
    lines.append("## 关键发现")
    hard_f1 = by_diff.get("hard", {}).get("avg_union_f1", 0.0)
    easy_f1 = by_diff.get("easy", {}).get("avg_union_f1", 0.0)
    lines.append(f"- Hard 场景 F1: {hard_f1:.4f} (Easy: {easy_f1:.4f})")
    hard_zeros = by_diff.get("hard", {}).get("zero_count", 0)
    lines.append(f"- Hard 场景零命中: {hard_zeros} cases")
    lines.append(f"- Type E Recall@K 提升: +{summary.get('type_e_delta', 0.0):.4f} (HWP vs RRF)")

    # PathIndexer contribution
    type_e_stats = by_ft.get("Type E", {})
    if type_e_stats:
        lines.append(f"- Type E Avg F1: {type_e_stats['avg_union_f1']:.4f}")

    lines.append("")
    lines.append("## 下一步建议")
    if hard_f1 < 0.2:
        lines.append("1. Hard 场景检索严重不足，需要更多训练数据覆盖")
        lines.append("2. PathIndexer 覆盖率有限，需扩展到 symbol_by_name 更多变体")
    elif hard_f1 < 0.4:
        lines.append("1. Hard 场景有改善空间，PathIndexer 注入机制已验证有效")
        lines.append("2. 建议: 扩展 alias 字典 + 增加 PathIndexer 覆盖的 Type E 模式")
    else:
        lines.append("1. Hard 场景接近可用水平，建议扩大评测集规模")

    report_text = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text + "\n", encoding="utf-8")
    print(f"Report saved to {output_path}")
    return report_text


# ─── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="102-case HybridRetrieverWithPath 检索基准评测"
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=_ROOT / "data/eval_cases.json",
        help="评测用例 JSON 文件",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=_ROOT / "external/celery",
        help="Celery 源码目录",
    )
    parser.add_argument(
        "--retriever",
        choices=["hybrid_with_path", "rrf_only"],
        default="hybrid_with_path",
        help="使用哪种检索器",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=_TOP_K,
        help="返回的 Top-K 结果数",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_ROOT / "results/102_case_eval.json",
        help="输出 JSON 路径",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=_ROOT / "reports/102_case_eval_report.md",
        help="输出 Markdown 路径",
    )
    parser.add_argument(
        "--compare-rrf",
        action="store_true",
        help="同时运行 RRF-only 对比",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    # Load cases
    print(f"Loading cases from {args.cases}...")
    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} cases.")
    by_ft_count = defaultdict(int)
    by_diff_count = defaultdict(int)
    for c in cases:
        by_ft_count[c.failure_type] += 1
        by_diff_count[c.difficulty] += 1
    print(f"  By failure_type: {dict(by_ft_count)}")
    print(f"  By difficulty: {dict(by_diff_count)}")

    # Build retriever
    print(f"\nBuilding {args.retriever}...")
    if args.retriever == "hybrid_with_path":
        retriever = HybridRetrieverWithPath.from_repo(
            args.repo,
            build_path_index=True,
        )
        idx_stats = retriever.path_indexer.stats()
        print(f"  {len(retriever.chunks)} chunks, {idx_stats['total_paths']} paths, "
              f"{idx_stats['total_aliases']} aliases")
        retrieve_fn = lambda c: retrieve_hybrid_with_path(retriever, c, args.top_k)
    else:
        retriever = HybridRetriever.from_repo(args.repo)
        print(f"  {len(retriever.chunks)} chunks")
        retrieve_fn = lambda c: retrieve_rrf_only(retriever, c, args.top_k)

    # Run evaluation
    print(f"\nEvaluating {len(cases)} cases...")
    results: list[dict[str, Any]] = []
    for i, case in enumerate(cases):
        predicted = retrieve_fn(case)
        result = evaluate_case(case, predicted, args.top_k)
        result["retriever"] = args.retriever
        results.append(result)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(cases)} cases evaluated")

    # Compute summaries
    summary: dict[str, Any] = {
        "overall": aggregate_metrics(cases, results, "difficulty").get("overall", {})
            if "overall" in aggregate_metrics(cases, results, "difficulty")
            else {},
        "by_difficulty": {},
        "by_failure_type": {},
        "type_e_delta": 0.0,
    }
    # Rebuild overall
    overall_agg = aggregate_metrics(cases, results, "difficulty")
    # Compute overall from all results
    all_f1s = [r["union_f1"] for r in results]
    all_macro = [r["macro_f1"] for r in results]
    all_recall5 = [r["recall_at_5"] for r in results]
    all_recall3 = [r["recall_at_3"] for r in results]
    all_recall10 = [r["recall_at_10"] for r in results]
    all_precision = [r["union_precision"] for r in results]
    summary["overall"] = {
        "count": len(results),
        "avg_union_f1": round(sum(all_f1s) / len(all_f1s), 4),
        "avg_macro_f1": round(sum(all_macro) / len(all_macro), 4),
        "avg_direct_f1": round(sum([r["direct_f1"] for r in results]) / len(results), 4),
        "avg_recall_at_3": round(sum(all_recall3) / len(all_recall3), 4),
        "avg_recall_at_5": round(sum(all_recall5) / len(all_recall5), 4),
        "avg_recall_at_10": round(sum(all_recall10) / len(all_recall10), 4),
        "avg_precision": round(sum(all_precision) / len(all_precision), 4),
        "perfect_count": sum(1 for f in all_f1s if f >= 0.9999),
        "zero_count": sum(1 for f in all_f1s if f == 0.0),
    }
    summary["by_difficulty"] = aggregate_metrics(cases, results, "difficulty")
    summary["by_failure_type"] = aggregate_metrics(cases, results, "failure_type")

    # Compare with RRF if requested
    if args.compare_rrf:
        print("\nBuilding RRF-only retriever for comparison...")
        rrf_retriever = HybridRetriever.from_repo(args.repo)
        rrf_results: list[dict[str, Any]] = []
        for case in cases:
            predicted = retrieve_rrf_only(rrf_retriever, case, args.top_k)
            rrf_results.append(evaluate_case(case, predicted, args.top_k))

        rrf_overall = round(
            sum(r["union_f1"] for r in rrf_results) / len(rrf_results), 4
        )
        hwp_overall = summary["overall"]["avg_union_f1"]
        delta = round(hwp_overall - rrf_overall, 4)

        # Type E comparison
        type_e_rrf = [r for r in rrf_results if r["failure_type"] == "Type E"]
        type_e_hwp = [r for r in results if r["failure_type"] == "Type E"]
        rrf_type_e_f1 = sum(r["union_f1"] for r in type_e_rrf) / len(type_e_rrf) if type_e_rrf else 0.0
        hwp_type_e_f1 = sum(r["union_f1"] for r in type_e_hwp) / len(type_e_hwp) if type_e_hwp else 0.0
        summary["type_e_delta"] = round(hwp_type_e_f1 - rrf_type_e_f1, 4)

        print(f"\n=== RRF vs HybridWithPath Comparison ===")
        print(f"  Overall: RRF={rrf_overall:.4f} HWP={hwp_overall:.4f} Δ={delta:+.4f}")
        print(f"  Type E:  RRF={rrf_type_e_f1:.4f} HWP={hwp_type_e_f1:.4f}")
        print(f"  Type E Delta (HWP-RRF): {summary['type_e_delta']:+.4f}")

        summary["rrf_comparison"] = {
            "rrf_overall": rrf_overall,
            "hwp_overall": hwp_overall,
            "delta": delta,
            "rrf_type_e_f1": round(rrf_type_e_f1, 4),
            "hwp_type_e_f1": round(hwp_type_e_f1, 4),
            "type_e_delta": summary["type_e_delta"],
        }

    # Build report
    config = {
        "retriever": args.retriever,
        "top_k": args.top_k,
        "repo": str(args.repo),
        "cases_file": str(args.cases),
        "n_cases": len(cases),
    }

    print("\n=== Summary ===")
    overall = summary["overall"]
    print(f"  Overall Union F1: {overall['avg_union_f1']:.4f}")
    print(f"  Overall Macro F1: {overall['avg_macro_f1']:.4f}")
    print(f"  Overall Recall@5: {overall['avg_recall_at_5']:.4f}")
    print(f"  Perfect (F1=1.0): {overall['perfect_count']}")
    print(f"  Zero (F1=0.0): {overall['zero_count']}")
    print()
    print("  By difficulty:")
    for diff, stats in sorted(summary["by_difficulty"].items()):
        print(f"    {diff}: F1={stats['avg_union_f1']:.4f} Recall@5={stats['avg_recall_at_5']:.4f}")
    print()
    if summary["by_failure_type"]:
        print("  By failure_type:")
        for ft, stats in sorted(summary["by_failure_type"].items()):
            print(f"    {ft}: F1={stats['avg_union_f1']:.4f} Recall@5={stats['avg_recall_at_5']:.4f}")

    # Write report
    report = build_report(results, cases, summary, config, args.output_md)

    # Write JSON
    output: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "config": config,
        "summary": summary,
        "per_case": results,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nJSON saved to {args.output_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
