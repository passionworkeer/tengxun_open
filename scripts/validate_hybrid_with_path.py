#!/usr/bin/env python3
"""
Task 3: End-to-end validation of Type C/D/E pattern fixes + HybridRetrieverWithPath.

Compares:
  1. OLD vs NEW classify_question_type patterns (accuracy by failure_type)
  2. ORIGINAL HybridRetriever vs HybridRetrieverWithPath (Recall@K by failure_type)

Usage:
    python scripts/validate_hybrid_with_path.py
    python scripts/validate_hybrid_with_path.py --repo external/celery --top-k 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import recall_at_k, mean_reciprocal_rank
from rag.hybrid_with_path import HybridRetrieverWithPath
from rag.rrf_retriever import HybridRetriever
from rag.conditional_retriever import classify_question_type


# ─── OLD patterns (before fix) ────────────────────────────────────────────────

_OLD_TYPE_E_PATTERNS = [
    re.compile(r"symbol_by_name|by_name\(|import_object|config_from_object", re.I),
    re.compile(r"LOADER_ALIASES|BACKEND_ALIASES|ALIASES\[", re.I),
    re.compile(r"loader.*default|default.*loader", re.I),
    re.compile(r"strategy.*default|default.*strategy", re.I),
    re.compile(r"task\.Request|task\.Strategy", re.I),
    re.compile(r"symbol.*resolution|resolve.*to", re.I),
    re.compile(r"最终|real class|real function|最终解析", re.I),
    re.compile(r"django.*fixup|fixup|django.*task", re.I),
]
_OLD_TYPE_D_PATTERNS = [
    re.compile(r"parameter.*shadow|shadow.*parameter|router.*string", re.I),
    re.compile(r"expand_router|RouterClass|register_type", re.I),
    re.compile(r"_chain|chain.*vs|registered.*class|subclass.*instance", re.I),
    re.compile(r"inline.*import|lazy.*import|import.*inside", re.I),
    re.compile(r"subtask|maybe_subtask|signature", re.I),
    re.compile(r"celery\.canvas\.(subtask|maybe_subtask)", re.I),
]


def classify_old(case: EvalCase) -> str:
    """Classify using OLD patterns (no Type C)."""
    combined = " ".join([case.question, case.entry_symbol or "", case.entry_file or ""])
    signals: list[str] = []
    for p in _OLD_TYPE_E_PATTERNS:
        if p.search(combined):
            signals.append("TypeE")
    for p in _OLD_TYPE_D_PATTERNS:
        if p.search(combined):
            signals.append("TypeD")
    # Old logic: D before E
    if "TypeD" in signals:
        return "Type D"
    if "TypeE" in signals:
        return "Type E"
    return ""


def classify_new(case: EvalCase) -> str:
    """Classify using NEW patterns (with Type C)."""
    from rag.conditional_retriever import classify_question_type as _new_classify
    result = _new_classify(
        question=case.question,
        entry_symbol=case.entry_symbol or "",
        entry_file=case.entry_file or "",
    )
    return result.failure_type


# ─── Metrics ──────────────────────────────────────────────────────────────────

def compute_recall_by_type(
    cases: list[EvalCase],
    retriever,
    weights: dict[str, float],
    top_k: int = 5,
) -> dict[str, dict]:
    """Compute Recall@K for each failure_type group."""
    by_type: dict[str, list[float]] = defaultdict(list)
    by_type_detail: dict[str, list[dict]] = defaultdict(list)

    for case in cases:
        if not case.gold_fqns:
            continue
        try:
            trace = retriever.retrieve_with_trace(
                question=case.question,
                entry_symbol=case.entry_symbol or "",
                entry_file=case.entry_file or "",
                top_k=top_k,
                per_source=12,
                query_mode="question_plus_entry",
                rrf_k=30,
                weights=weights,
            )
        except Exception:
            recall = 0.0
            trace_fused_ids = []
        else:
            fused_symbols = retriever.ranked_symbols(list(trace.fused_ids))
            recall = recall_at_k(list(case.gold_fqns), fused_symbols, top_k)
            trace_fused_ids = list(trace.fused_ids)

        ft = case.failure_type or "unknown"
        by_type[ft].append(recall)
        by_type_detail[ft].append({
            "case_id": case.case_id,
            "question": case.question[:60],
            "gold_fqns": list(case.gold_fqns)[:3],
            "fused_symbols": fused_symbols[:3] if 'fused_symbols' in dir() else [],
            "recall": recall,
        })

    result = {}
    for ft, recalls in sorted(by_type.items()):
        result[ft] = {
            "total": len(recalls),
            "avg_recall": round(sum(recalls) / len(recalls), 4) if recalls else 0.0,
            "recall_sum": round(sum(recalls), 4),
            "perfect": sum(1 for r in recalls if r == 1.0),
            "zero": sum(1 for r in recalls if r == 0.0),
            "details": by_type_detail[ft],
        }
    return result


# ─── Report builders ─────────────────────────────────────────────────────────

def build_pattern_fix_report(
    cases: list[EvalCase],
) -> dict:
    """Compare OLD vs NEW classification patterns."""
    old_correct = defaultdict(int)
    new_correct = defaultdict(int)
    old_total = defaultdict(int)
    new_total = defaultdict(int)
    old_detail = defaultdict(list)
    new_detail = defaultdict(list)

    for case in cases:
        ft = case.failure_type or ""
        if not ft:
            continue
        old_total[ft] += 1
        new_total[ft] += 1

        old_pred = classify_old(case)
        new_pred = classify_new(case)

        old_ok = old_pred == ft
        new_ok = new_pred == ft

        if old_ok:
            old_correct[ft] += 1
        if new_ok:
            new_correct[ft] += 1

        if not old_ok or not new_ok:
            entry = {
                "case_id": case.case_id,
                "question": case.question[:80],
                "gt": ft,
                "old_pred": old_pred or "(empty)",
                "new_pred": new_pred or "(empty)",
            }
            if not new_ok:
                new_detail[ft].append(entry)
            if not old_ok:
                old_detail[ft].append(entry)

    rows = []
    all_types = sorted(set(list(old_total.keys()) + list(new_total.keys())))
    for ft in all_types:
        ot = old_total[ft]
        nt = new_total[ft]
        oc = old_correct.get(ft, 0)
        nc = new_correct.get(ft, 0)
        rows.append({
            "failure_type": ft,
            "old_total": ot,
            "new_total": nt,
            "old_correct": oc,
            "new_correct": nc,
            "old_accuracy": round(oc / ot * 100, 1) if ot else 0,
            "new_accuracy": round(nc / nt * 100, 1) if nt else 0,
            "improvement": round((nc / nt * 100 if nt else 0) - (oc / ot * 100 if ot else 0), 1),
            "old_missed": ot - oc,
            "new_missed": nt - nc,
            "old_detail": old_detail.get(ft, []),
            "new_detail": new_detail.get(ft, []),
        })

    # Totals
    old_all = sum(old_correct.values())
    new_all = sum(new_correct.values())
    total_all = sum(old_total.values())

    return {
        "total_cases": total_all,
        "old_total_correct": old_all,
        "new_total_correct": new_all,
        "old_overall_accuracy": round(old_all / total_all * 100, 1) if total_all else 0,
        "new_overall_accuracy": round(new_all / total_all * 100, 1) if total_all else 0,
        "overall_improvement": round((new_all / total_all * 100 if total_all else 0) - (old_all / total_all * 100 if total_all else 0), 1),
        "per_type": rows,
    }


def build_retrieval_comparison(
    cases: list[EvalCase],
    original_retriever: HybridRetriever,
    hybrid_with_path: HybridRetrieverWithPath,
    weights: dict[str, float],
    top_k: int,
) -> dict:
    """Compare original HybridRetriever vs HybridRetrieverWithPath Recall@K."""
    print("  Computing original HybridRetriever Recall@K...")
    original_recalls = compute_recall_by_type(cases, original_retriever, weights, top_k)
    print("  Computing HybridRetrieverWithPath Recall@K...")
    with_path_recalls = compute_recall_by_type(cases, hybrid_with_path, weights, top_k)

    all_types = sorted(set(list(original_recalls.keys()) + list(with_path_recalls.keys())))
    rows = []
    for ft in all_types:
        orig = original_recalls.get(ft, {"avg_recall": 0.0, "total": 0, "perfect": 0, "zero": 0})
        with_p = with_path_recalls.get(ft, {"avg_recall": 0.0, "total": 0, "perfect": 0, "zero": 0})
        delta = with_p["avg_recall"] - orig["avg_recall"]
        rows.append({
            "failure_type": ft,
            "total": orig["total"],
            "original_avg_recall": orig["avg_recall"],
            "with_path_avg_recall": with_p["avg_recall"],
            "delta": round(delta, 4),
            "delta_pct": round(delta / orig["avg_recall"] * 100, 1) if orig["avg_recall"] > 0 else 0,
            "original_perfect": orig["perfect"],
            "with_path_perfect": with_p["perfect"],
            "perfect_improvement": with_p["perfect"] - orig["perfect"],
            "original_zero": orig["zero"],
            "with_path_zero": with_p["zero"],
        })

    return {"per_type": rows, "top_k": top_k}


# ─── Markdown report ──────────────────────────────────────────────────────────

def build_markdown_report(
    pattern_report: dict,
    retrieval_report: dict,
    output_path: Path,
) -> str:
    lines = [
        "# HybridRetrieverWithPath + Type C/D/E Pattern Fix Validation Report",
        "",
        f"**Generated**: standalone run",
        f"**Total cases**: {pattern_report['total_cases']}",
        "",
    ]

    # ── Section 1: Pattern Fix ───────────────────────────────────────────
    lines.append("## 1. Type C/D/E Pattern Fix Comparison")
    lines.append("")
    lines.append("### Classification Accuracy: OLD vs NEW patterns")
    lines.append("")
    lines.append(
        f"**Overall**: OLD {pattern_report['old_overall_accuracy']}% "
        f"({pattern_report['old_total_correct']}/{pattern_report['total_cases']}) "
        f"→ NEW {pattern_report['new_overall_accuracy']}% "
        f"({pattern_report['new_total_correct']}/{pattern_report['total_cases']}) "
        f"**({pattern_report['overall_improvement']:+.1f}%)**"
    )
    lines.append("")
    lines.append(
        "| Failure Type | Total | OLD Acc | NEW Acc | Improvement | "
        "OLD Missed | NEW Missed |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|"
    )
    for row in pattern_report["per_type"]:
        arrow = "↑" if row["improvement"] > 0 else "↓" if row["improvement"] < 0 else "="
        lines.append(
            f"| {row['failure_type']} | {row['old_total']} | "
            f"{row['old_accuracy']}% | **{row['new_accuracy']}%** | "
            f"{arrow}{abs(row['improvement']):.1f}% | "
            f"{row['old_missed']} | {row['new_missed']} |"
        )
    lines.append("")

    # Detail misses for key types
    for row in pattern_report["per_type"]:
        if row["failure_type"] in ("Type C", "Type D", "Type E") and row["new_missed"] > 0:
            lines.append(f"### {row['failure_type']} Missed Cases ({row['new_missed']})")
            lines.append("")
            for m in row["new_detail"][:5]:
                lines.append(
                    f"- `{m['case_id']}`: {m['question'][:70]} "
                    f"[pred={m['new_pred']}, gt={m['gt']}]"
                )
            if len(row["new_detail"]) > 5:
                lines.append(f"  ... and {len(row['new_detail']) - 5} more")
            lines.append("")

    # ── Section 2: Retrieval Comparison ─────────────────────────────────
    lines.append("## 2. Retrieval Recall@K Comparison (RRF vs HybridWithPath)")
    lines.append("")
    lines.append(f"**Top-K**: {retrieval_report['top_k']}")
    lines.append("")
    lines.append(
        "| Failure Type | Total | RRF Recall@K | HybridWithPath Recall@K | Delta | "
        "RRF Perfect | HWP Perfect |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for row in retrieval_report["per_type"]:
        arrow = "↑" if row["delta"] > 0 else "↓" if row["delta"] < 0 else "="
        lines.append(
            f"| {row['failure_type']} | {row['total']} | "
            f"{row['original_avg_recall']:.4f} | "
            f"**{row['with_path_avg_recall']:.4f}** | "
            f"{arrow}{row['delta']:+.4f} | "
            f"{row['original_perfect']} | {row['with_path_perfect']} |"
        )
    lines.append("")

    # ── Section 3: Conclusions ──────────────────────────────────────────
    lines.append("## 3. Conclusions")
    type_c_row = next((r for r in pattern_report["per_type"] if r["failure_type"] == "Type C"), None)
    type_d_row = next((r for r in pattern_report["per_type"] if r["failure_type"] == "Type D"), None)
    type_e_row = next((r for r in pattern_report["per_type"] if r["failure_type"] == "Type E"), None)

    if type_c_row:
        old_acc = type_c_row["old_accuracy"]
        new_acc = type_c_row["new_accuracy"]
        lines.append(f"- **Type C**: {old_acc}% → **{new_acc}%** "
                     f"({type_c_row['improvement']:+.1f}% improvement)")
    if type_d_row:
        old_acc = type_d_row["old_accuracy"]
        new_acc = type_d_row["new_accuracy"]
        lines.append(f"- **Type D**: {old_acc}% → **{new_acc}%** "
                     f"({type_d_row['improvement']:+.1f}% improvement)")
    if type_e_row:
        old_acc = type_e_row["old_accuracy"]
        new_acc = type_e_row["new_accuracy"]
        lines.append(f"- **Type E**: {old_acc}% → **{new_acc}%** "
                     f"({type_e_row['improvement']:+.1f}% improvement)")

    lines.append("")
    lines.append("### Next Steps")
    lines.append("1. Review remaining Type C/D/E misses in detail above")
    lines.append("2. For Type E cases where HybridWithPath improves, verify path bonus is appropriate")
    lines.append("3. Consider increasing path_score_bonus if PathIndexer is under-boosted")
    lines.append("")

    report_text = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    print(f"Report saved to {output_path}")
    return report_text


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Type C/D/E pattern fixes + HybridRetrieverWithPath."
    )
    parser.add_argument(
        "--cases", type=Path,
        default=_ROOT / "data/eval_cases.json",
        help="Path to evaluation cases JSON.",
    )
    parser.add_argument(
        "--repo", type=Path,
        default=_ROOT / "external/celery",
        help="Path to Celery source repository.",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Top-K for recall calculation.",
    )
    parser.add_argument(
        "--weights", default="0.33,0.33,0.34",
        help="RRF weights as bm25,semantic,graph.",
    )
    parser.add_argument(
        "--output", type=Path,
        default=_ROOT / "reports/hybrid_with_path_validation.md",
        help="Output markdown report path.",
    )
    parser.add_argument(
        "--json-output", type=Path,
        default=_ROOT / "reports/hybrid_with_path_validation.json",
        help="Output JSON report path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    # Load cases
    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} cases.")

    # Parse weights
    parts = [float(x.strip()) for x in args.weights.split(",")]
    weights = {"bm25": parts[0], "semantic": parts[1], "graph": parts[2]}

    # ── Part 1: Pattern fix validation ───────────────────────────────────
    print("\n=== Part 1: Pattern Fix Validation ===")
    pattern_report = build_pattern_fix_report(cases)
    print(f"Overall OLD accuracy: {pattern_report['old_overall_accuracy']}% "
          f"({pattern_report['old_total_correct']}/{pattern_report['total_cases']})")
    print(f"Overall NEW accuracy: {pattern_report['new_overall_accuracy']}% "
          f"({pattern_report['new_total_correct']}/{pattern_report['total_cases']})")
    print()
    for row in pattern_report["per_type"]:
        arrow = "↑" if row["improvement"] > 0 else "=" if row["improvement"] == 0 else "↓"
        print(f"  {row['failure_type']:8s}: {row['old_accuracy']:5.1f}% → {row['new_accuracy']:5.1f}% {arrow} "
              f"({row['new_missed']} missed)")

    # ── Part 2: Retrieval comparison ─────────────────────────────────────
    if not args.repo.exists():
        print(f"\nError: repo not found at {args.repo}")
        print("Skipping retrieval comparison (repo not available).")
        hybrid_report = {"per_type": [], "top_k": args.top_k}
    else:
        print(f"\n=== Part 2: Retrieval Comparison ===")
        print(f"Building HybridRetriever (RRF baseline)...")
        original_retriever = HybridRetriever.from_repo(args.repo)
        print(f"  {len(original_retriever.chunks)} chunks indexed.")

        print(f"Building HybridRetrieverWithPath...")
        hybrid_with_path = HybridRetrieverWithPath.from_repo(
            args.repo,
            build_path_index=True,
        )
        idx_stats = hybrid_with_path.path_indexer.stats()
        print(f"  {len(hybrid_with_path.chunks)} chunks, "
              f"{idx_stats['total_paths']} paths, "
              f"{idx_stats['total_aliases']} aliases.")

        hybrid_report = build_retrieval_comparison(
            cases, original_retriever, hybrid_with_path, weights, args.top_k
        )

        print()
        for row in hybrid_report["per_type"]:
            arrow = "↑" if row["delta"] > 0 else "=" if row["delta"] == 0 else "↓"
            print(f"  {row['failure_type']:8s}: RRF={row['original_avg_recall']:.4f} "
                  f"→ HWP={row['with_path_avg_recall']:.4f} {arrow}")

    # ── Build report ─────────────────────────────────────────────────────
    print("\n=== Building Report ===")
    report = build_markdown_report(pattern_report, hybrid_report, args.output)

    # JSON output
    full_json = {
        "pattern_fix": pattern_report,
        "retrieval_comparison": hybrid_report,
        "config": {
            "top_k": args.top_k,
            "weights": weights,
            "repo": str(args.repo),
            "cases_file": str(args.cases),
        },
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(full_json, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"JSON report saved to {args.json_output}")

    print(f"\nMarkdown report:\n{report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
