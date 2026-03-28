from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any

from openai import OpenAI

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_layered_dependency_metrics


def build_prompt_v2(case: EvalCase, context: str = "") -> str:
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    if context:
        parts.append(f"Context:\n{context.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'
    )
    return "\n\n".join(parts)


def parse_response(text: str) -> dict[str, list[str]] | None:
    try:
        text = text.strip()
        import re

        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
        else:
            data = json.loads(text.strip())
        gt = data.get("ground_truth", {})
        return {
            "direct_deps": gt.get("direct_deps", []),
            "indirect_deps": gt.get("indirect_deps", []),
            "implicit_deps": gt.get("implicit_deps", []),
        }
    except (json.JSONDecodeError, AttributeError, KeyError):
        return None


def compute_f1(pred: dict[str, list[str]], gt: dict[str, list[str]]) -> float:
    return compute_layered_dependency_metrics(gt, pred).union.f1


def run_gpt_eval(
    cases: list[EvalCase],
    api_key: str,
    base_url: str = "https://ai.td.ee/v1",
    model: str = "gpt-5.4",
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case, context="")
        prediction = None
        raw_output = None

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                    timeout=300,
                )
                msg = response.choices[0].message
                raw_output = msg.content if msg and msg.content else ""
                prediction = parse_response(raw_output)
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                import time

                time.sleep(5)
                raw_output = str(e)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) if case.direct_gold_fqns else [],
            "indirect_deps": list(case.indirect_gold_fqns)
            if case.indirect_gold_fqns
            else [],
            "implicit_deps": list(case.implicit_gold_fqns)
            if case.implicit_gold_fqns
            else [],
        }

        scoring = compute_layered_dependency_metrics(gt_dict, prediction or {})
        f1 = scoring.union.f1

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "model": model,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "f1": round(f1, 4),
            "macro_f1": round(scoring.macro_f1, 4),
            "mislayer_rate": round(scoring.mislayer_rate, 4),
            "strict_scoring": scoring.as_dict(),
        }
        results.append(result)
        print(f"  F1: {f1:.4f}", flush=True)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nAll {len(results)} cases completed. Results saved to {output_path}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run GPT5.4 evaluation on Celery dependency analysis."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to evaluation dataset.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        required=True,
        help="API key.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.4",
        help="Model name (default: gpt-5.4).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://ai.td.ee/v1",
        help="API base URL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/gpt5_eval_results.json"),
        help="Output path for results.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit number of cases (for testing).",
    )
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    run_gpt_eval(
        cases=cases,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        output_path=args.output,
        max_cases=args.max_cases,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
