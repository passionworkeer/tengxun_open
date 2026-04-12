"""
RRF k-parameter tuning script.

Evaluates the effect of different RRF k values on retrieval quality,
focusing on Hard/Type E cases where k has the most impact.

Usage:
    python scripts/tune_rrf_k.py [--eval-cases data/eval_cases.json] [--repo-root external/celery]

Outputs:
    - Optimal k recommendation per difficulty and failure_type
    - Per-case detailed metrics across k values
    - Summary table with MRR and Recall@K for each k
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.evaluator import evaluate_retrieval
from evaluation.loader import EvalCase, load_eval_cases
from evaluation.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank
from rag.rrf_retriever import HybridRetriever


K_VALUES = [10, 20, 30, 50, 60]
DEFAULT_TOP_K = 5
DEFAULT_PER_SOURCE = 12


def _summarize(cases: list[EvalCase], results: list[dict], top_k: int) -> dict:
    """Summarize metrics for a result set."""
    gold_sets = [case.gold_fqns for case in cases]
    ranked_lists = [r["chunk_symbols"][:top_k] for r in results]
    return {
        "avg_recall": round(
            sum(recall_at_k(case.gold_fqns, ranked, top_k)
                for case, ranked in zip(cases, ranked_lists)) / len(cases), 4
        ) if cases else 0.0,
        "mrr": round(mean_reciprocal_rank(gold_sets, ranked_lists), 4),
    }


def _breakdown_by(
    cases: list[EvalCase],
    results: list[dict],
    key: str,  # "difficulty" or "failure_type"
    top_k: int,
) -> dict:
    buckets: dict[str, list[tuple]] = defaultdict(list)
    for case, result in zip(cases, results):
        bucket = getattr(case, key, "") or "unknown"
        ranked = result["chunk_symbols"][:top_k]
        rr = reciprocal_rank(case.gold_fqns, ranked)
        buckets[bucket].append((case.gold_fqns, ranked, rr))

    summary = {}
    for bucket, pairs in sorted(buckets.items()):
        golds, ranked_lists, rrs = zip(*pairs)
        recall_vals = [
            recall_at_k(g, r, top_k) for g, r, _ in pairs
        ]
        summary[bucket] = {
            "count": len(pairs),
            "avg_recall": round(sum(recall_vals) / len(recall_vals), 4),
            "mrr": round(sum(rrs) / len(rrs), 4),
        }
    return summary


def run_tuning(
    retriever: HybridRetriever,
    cases: list[EvalCase],
    k_values: list[int],
    top_k: int,
    per_source: int,
    query_mode: str,
) -> dict:
    """
    Run retrieval evaluation across multiple k values.

    Returns a dict with per-k results and cross-k comparison.
    """
    all_k_results: dict[int, dict] = {}
    per_case_across_k: dict[str, dict[int, dict]] = defaultdict(dict)

    for k in k_values:
        print(f"\n[RRF k={k}] Evaluating {len(cases)} cases...")
        eval_result = evaluate_retrieval(
            cases=cases,
            retriever=retriever,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=k,
        )

        fused_summary = eval_result["fused_chunk_symbols"]
        all_k_results[k] = {
            "avg_recall": fused_summary["avg_recall_at_k"],
            "mrr": fused_summary["mrr"],
            "difficulty_breakdown": fused_summary["difficulty_breakdown"],
            "failure_type_breakdown": fused_summary["failure_type_breakdown"],
            "cases": eval_result["cases"],
        }

        # Per-case results for cross-k analysis
        for case_result in eval_result["cases"]:
            case_id = case_result["id"]
            src = case_result["sources"]["fused"]
            per_case_across_k[case_id][k] = {
                "recall": src["chunk_symbol_recall_at_k"],
                "rr": src["chunk_symbol_reciprocal_rank"],
                "top_hits": src["chunk_symbol_top_hits"],
            }

    # Cross-k comparison
    print("\n" + "=" * 60)
    print("CROSS-K COMPARISON SUMMARY")
    print("=" * 60)

    comparison_rows = []
    for k in k_values:
        r = all_k_results[k]
        comparison_rows.append({
            "k": k,
            "avg_recall": r["avg_recall"],
            "mrr": r["mrr"],
        })
        print(f"  k={k:>3}: Recall@5={r['avg_recall']:.4f}  MRR={r['mrr']:.4f}")

    # Hard / Type E specific comparison
    print("\n" + "-" * 60)
    print("HARD CASES (difficulty=hard) BREAKDOWN")
    print("-" * 60)
    hard_cases = [c for c in cases if c.difficulty == "hard"]
    hard_case_ids = {c.case_id for c in hard_cases}

    for k in k_values:
        r = all_k_results[k]
        hard_breakdown = r["failure_type_breakdown"]
        type_e = hard_breakdown.get("Type E", {})
        type_b = hard_breakdown.get("Type B", {})
        type_a = hard_breakdown.get("Type A", {})
        type_d = hard_breakdown.get("Type D", {})
        print(
            f"  k={k:>3}: "
            f"TypeA(n={type_a.get('num_cases',0)},RR={type_a.get('avg_reciprocal_rank',0):.4f}) "
            f"TypeB(n={type_b.get('num_cases',0)},RR={type_b.get('avg_reciprocal_rank',0):.4f}) "
            f"TypeD(n={type_d.get('num_cases',0)},RR={type_d.get('avg_reciprocal_rank',0):.4f}) "
            f"TypeE(n={type_e.get('num_cases',0)},RR={type_e.get('avg_reciprocal_rank',0):.4f})"
        )

    # Find best k
    best_k_by_mrr = max(k_values, key=lambda k: all_k_results[k]["mrr"])
    best_k_by_recall = max(k_values, key=lambda k: all_k_results[k]["avg_recall"])

    # Find best k for Type E
    type_e_k_scores = {
        k: all_k_results[k]["failure_type_breakdown"].get("Type E", {}).get("avg_reciprocal_rank", 0.0)
        for k in k_values
    }
    best_k_for_type_e = max(k_values, key=lambda k: type_e_k_scores[k])

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    print(f"  Best k by overall MRR:         {best_k_by_mrr}")
    print(f"  Best k by overall Recall@5:     {best_k_by_recall}")
    print(f"  Best k for Type E cases:        {best_k_for_type_e}")
    print(f"  Best k for Hard cases:          {best_k_by_mrr}  (same as overall MRR)")

    recommendations = {
        "overall_mrr": best_k_by_mrr,
        "overall_recall": best_k_by_recall,
        "type_e": best_k_for_type_e,
        "hard": best_k_by_mrr,
        "k_scores": {
            k: {"recall": all_k_results[k]["avg_recall"], "mrr": all_k_results[k]["mrr"]}
            for k in k_values
        },
        "type_e_k_scores": type_e_k_scores,
    }

    # Detailed case-level analysis for Hard/Type E
    print("\n" + "-" * 60)
    print("HARD / TYPE E PER-CASE DETAIL (top k candidates)")
    print("-" * 60)
    hard_type_cases = [
        c for c in cases
        if c.difficulty == "hard" or c.failure_type in ("Type A", "Type B", "Type D", "Type E")
    ]
    for case in hard_type_cases[:10]:  # limit to first 10 for readability
        case_id = case.case_id
        print(f"\n  [{case_id}] difficulty={case.difficulty} failure_type={case.failure_type}")
        for k in k_values:
            cr = per_case_across_k[case_id].get(k)
            if cr:
                top = cr["top_hits"][:3]
                print(
                    f"    k={k:>3}: recall={cr['recall']:.2f} rr={cr['rr']:.2f} "
                    f"top3={top}"
                )

    return {
        "k_values": k_values,
        "per_k_results": all_k_results,
        "per_case_across_k": dict(per_case_across_k),
        "recommendations": recommendations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tune RRF k parameter on evaluation cases."
    )
    parser.add_argument(
        "--eval-cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to eval_cases.json",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("external/celery"),
        help="Path to celery source repository",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help="Top-K for retrieval (default: 5)",
    )
    parser.add_argument(
        "--per-source",
        type=int,
        default=DEFAULT_PER_SOURCE,
        help="Per-source depth (default: 12)",
    )
    parser.add_argument(
        "--query-mode",
        default="question_plus_entry",
        choices=["question_only", "question_plus_entry"],
        help="Query mode (default: question_plus_entry)",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default="10,20,30,50,60",
        help="Comma-separated k values to evaluate (default: 10,20,30,50,60)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional: write results JSON to this path",
    )

    args = parser.parse_args()

    # Load cases
    print(f"Loading eval cases from {args.eval_cases}...")
    cases = load_eval_cases(args.eval_cases)
    print(f"Loaded {len(cases)} cases.")

    # Build retriever
    print(f"Building retriever from {args.repo_root}...")
    retriever = HybridRetriever.from_repo(args.repo_root)
    print(f"Retriever ready: {len(retriever.chunks)} chunks indexed.")

    # Parse k values
    try:
        k_values = [int(k.strip()) for k in args.k_values.split(",") if k.strip()]
    except ValueError:
        print(f"ERROR: Invalid k-values string: {args.k_values}")
        sys.exit(1)

    # Run tuning
    result = run_tuning(
        retriever=retriever,
        cases=cases,
        k_values=k_values,
        top_k=args.top_k,
        per_source=args.per_source,
        query_mode=args.query_mode,
    )

    # Write output if requested
    if args.output:
        output_path = args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Strip large data from output for readability
        serializable = {
            "k_values": result["k_values"],
            "per_k_results": {
                k: {
                    "avg_recall": v["avg_recall"],
                    "mrr": v["mrr"],
                    "failure_type_breakdown": v["failure_type_breakdown"],
                    "difficulty_breakdown": v["difficulty_breakdown"],
                }
                for k, v in result["per_k_results"].items()
            },
            "recommendations": result["recommendations"],
        }
        output_path.write_text(json.dumps(serializable, indent=2), encoding="utf-8")
        print(f"\nResults written to {output_path}")


if __name__ == "__main__":
    main()
