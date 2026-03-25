from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    difficulty: str
    question: str
    gold_fqns: list[str]


def load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for item in raw:
        cases.append(
            EvalCase(
                case_id=str(item.get("id", "")),
                difficulty=str(item.get("difficulty", "unknown")),
                question=str(item.get("question", "")),
                gold_fqns=list(item.get("gold_fqns", [])),
            )
        )
    return cases


def summarize_cases(cases: list[EvalCase]) -> dict[str, Any]:
    difficulty_counter = Counter(case.difficulty for case in cases)
    avg_gold_targets = (
        sum(len(case.gold_fqns) for case in cases) / len(cases) if cases else 0.0
    )
    return {
        "num_cases": len(cases),
        "difficulty_distribution": dict(sorted(difficulty_counter.items())),
        "avg_gold_targets": round(avg_gold_targets, 2),
        "has_minimum_required_cases": len(cases) >= 50,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize the current eval dataset scaffold."
    )
    parser.add_argument(
        "--eval-cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to the curated evaluation dataset.",
    )
    parser.add_argument(
        "--mode",
        choices=["baseline", "all"],
        default="baseline",
        help="Report mode placeholder for future experiments.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cases = load_eval_cases(args.eval_cases)
    summary = summarize_cases(cases)
    summary["mode"] = args.mode
    summary["next_step"] = (
        "Populate data/eval_cases.json with manually curated Celery cases."
        if not cases
        else "Ready to plug in model inference and metric computation."
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

