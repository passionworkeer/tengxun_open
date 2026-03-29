#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from evaluation.baseline import EvalCase, load_eval_cases
from experiments.conditional_rag import choose_case_score, predict_implicit_level


def main() -> int:
    parser = argparse.ArgumentParser(description="Conditional RAG trigger policy experiment.")
    parser.add_argument("--cases", type=Path, default=Path("data/eval_cases.json"))
    parser.add_argument(
        "--rag-results",
        type=Path,
        default=Path("results/gpt_rag_e2e_54cases_20260328.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/experiments/conditional_rag_policy.json"),
    )
    parser.add_argument("--threshold", type=int, default=3)
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    case_map = {case.case_id: case for case in cases}
    rag_rows = json.loads(args.rag_results.read_text(encoding="utf-8"))

    policy_rows: list[dict[str, Any]] = []
    exact_hits = 0
    threshold_hits = 0
    difficulty_totals: dict[str, list[float]] = defaultdict(list)

    for row in rag_rows:
        case = case_map[row["case_id"]]
        prediction = predict_implicit_level(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
        )
        actual_level = case.implicit_level or 1
        exact_hits += int(prediction.predicted_level == actual_level)
        threshold_hits += int((prediction.predicted_level >= args.threshold) == (actual_level >= args.threshold))

        conditional_score = choose_case_score(
            case_result=row,
            should_use_rag=prediction.should_use_rag,
        )
        oracle_score = choose_case_score(
            case_result=row,
            should_use_rag=actual_level >= args.threshold,
        )
        no_rag_score = float(row["no_rag"]["f1"])
        with_rag_score = float(row["with_rag"]["f1"])
        difficulty_totals[case.difficulty].append(conditional_score)
        policy_rows.append(
            {
                "case_id": case.case_id,
                "difficulty": case.difficulty,
                "failure_type": case.failure_type,
                "actual_implicit_level": actual_level,
                "predicted_implicit_level": prediction.predicted_level,
                "should_use_rag": prediction.should_use_rag,
                "prediction_reasons": list(prediction.reasons),
                "no_rag_f1": no_rag_score,
                "with_rag_f1": with_rag_score,
                "conditional_f1": round(conditional_score, 4),
                "oracle_threshold_f1": round(oracle_score, 4),
            }
        )

    total = len(policy_rows) or 1
    summary = {
        "num_cases": len(policy_rows),
        "threshold": args.threshold,
        "classifier": {
            "exact_accuracy": round(exact_hits / total, 4),
            "threshold_accuracy": round(threshold_hits / total, 4),
            "predicted_level_distribution": dict(
                sorted(Counter(row["predicted_implicit_level"] for row in policy_rows).items())
            ),
        },
        "policy": {
            "avg_no_rag_f1": round(sum(row["no_rag_f1"] for row in policy_rows) / total, 4),
            "avg_with_rag_f1": round(sum(row["with_rag_f1"] for row in policy_rows) / total, 4),
            "avg_conditional_f1": round(sum(row["conditional_f1"] for row in policy_rows) / total, 4),
            "avg_oracle_threshold_f1": round(
                sum(row["oracle_threshold_f1"] for row in policy_rows) / total,
                4,
            ),
            "rag_activation_rate": round(
                sum(1 for row in policy_rows if row["should_use_rag"]) / total,
                4,
            ),
            "difficulty_breakdown": {
                difficulty: round(sum(values) / len(values), 4)
                for difficulty, values in sorted(difficulty_totals.items())
            },
        },
        "top_rag_avoids": sorted(
            (
                row
                for row in policy_rows
                if not row["should_use_rag"] and row["no_rag_f1"] >= row["with_rag_f1"]
            ),
            key=lambda item: item["no_rag_f1"] - item["with_rag_f1"],
            reverse=True,
        )[:10],
    }

    payload = {"summary": summary, "cases": policy_rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved policy report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
