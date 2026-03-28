#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from evaluation.baseline import EvalCase, load_eval_cases
from evaluation.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank
from experiments.dynamic_symbol_rag import build_dynamic_symbol_retriever
from rag.rrf_retriever import build_retriever


def build_query_text(case: EvalCase) -> str:
    return " ".join(
        part
        for part in (
            case.question.strip(),
            case.entry_symbol.strip(),
            case.entry_file.strip(),
        )
        if part
    )


def summarize_ranked_lists(
    cases: list[EvalCase],
    ranked_lists: list[list[str]],
    top_k: int,
) -> dict[str, float]:
    return {
        "avg_recall_at_k": round(
            mean(recall_at_k(case.gold_fqns, ranked, top_k) for case, ranked in zip(cases, ranked_lists)),
            4,
        )
        if cases
        else 0.0,
        "mrr": round(
            mean_reciprocal_rank(
                [case.gold_fqns for case in cases],
                ranked_lists,
            ),
            4,
        )
        if cases
        else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Type E dynamic-symbol retrieval experiment.")
    parser.add_argument("--repo-root", type=Path, default=Path("external/celery"))
    parser.add_argument("--cases", type=Path, default=Path("data/eval_cases.json"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/experiments/typee_dynamic_symbol_rag_v2.json"),
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--per-source", type=int, default=12)
    parser.add_argument("--rrf-k", type=int, default=30)
    args = parser.parse_args()

    cases = [case for case in load_eval_cases(args.cases) if case.failure_type == "Type E"]
    base = build_retriever(args.repo_root)
    enhanced = build_dynamic_symbol_retriever(args.repo_root)

    baseline_ranked: list[list[str]] = []
    enhanced_ranked: list[list[str]] = []
    rows: list[dict[str, Any]] = []

    for case in cases:
        query_text = build_query_text(case)

        base_trace = base.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=args.top_k,
            per_source=args.per_source,
            query_mode="question_plus_entry",
            rrf_k=args.rrf_k,
        )
        base_candidates = base.expand_candidate_fqns(
            base_trace.fused,
            query_text=query_text,
            entry_symbol=case.entry_symbol,
        )

        enhanced_trace = enhanced.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=args.top_k,
            per_source=args.per_source,
            query_mode="question_plus_entry",
            rrf_k=args.rrf_k,
        )
        enhanced_candidates = base.expand_candidate_fqns(
            enhanced_trace.fused,
            query_text=query_text,
            entry_symbol=case.entry_symbol,
        )

        baseline_ranked.append(base_candidates)
        enhanced_ranked.append(enhanced_candidates)

        base_recall = recall_at_k(case.gold_fqns, base_candidates, args.top_k)
        enhanced_recall = recall_at_k(case.gold_fqns, enhanced_candidates, args.top_k)
        row = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "implicit_level": case.implicit_level,
            "category": case.category,
            "baseline_recall_at_k": round(base_recall, 4),
            "enhanced_recall_at_k": round(enhanced_recall, 4),
            "baseline_mrr": round(reciprocal_rank(case.gold_fqns, base_candidates), 4),
            "enhanced_mrr": round(reciprocal_rank(case.gold_fqns, enhanced_candidates), 4),
            "delta_recall_at_k": round(enhanced_recall - base_recall, 4),
            "alias_hits": [
                {
                    "alias": hit.alias,
                    "target_symbol": hit.target_symbol,
                    "source_symbol": hit.source_symbol,
                    "match_type": hit.match_type,
                    "num_target_chunks": len(hit.target_chunk_ids),
                }
                for hit in enhanced_trace.alias_hits[:20]
            ],
            "num_alias_hits": len(enhanced_trace.alias_hits),
            "baseline_top_hits": base_candidates[: args.top_k],
            "enhanced_top_hits": enhanced_candidates[: args.top_k],
        }
        rows.append(row)

    summary = {
        "num_cases": len(cases),
        "top_k": args.top_k,
        "baseline": summarize_ranked_lists(cases, baseline_ranked, args.top_k),
        "enhanced": summarize_ranked_lists(cases, enhanced_ranked, args.top_k),
        "alias_coverage": round(
            sum(1 for row in rows if row["alias_hits"]) / len(rows),
            4,
        )
        if rows
        else 0.0,
        "match_type_distribution": {
            match_type: sum(
                1
                for row in rows
                for hit in row["alias_hits"]
                if hit["match_type"] == match_type
            )
            for match_type in sorted(
                {
                    hit["match_type"]
                    for row in rows
                    for hit in row["alias_hits"]
                }
            )
        },
        "improved_cases": sum(
            1 for row in rows if row["enhanced_recall_at_k"] > row["baseline_recall_at_k"]
        ),
        "regressed_cases": sum(
            1 for row in rows if row["enhanced_recall_at_k"] < row["baseline_recall_at_k"]
        ),
        "mrr_improved_cases": sum(
            1 for row in rows if row["enhanced_mrr"] > row["baseline_mrr"]
        ),
        "top_improvements": sorted(
            rows,
            key=lambda item: (
                item["delta_recall_at_k"],
                item["enhanced_mrr"] - item["baseline_mrr"],
            ),
            reverse=True,
        )[:10],
    }

    payload = {"summary": summary, "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved experiment report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
