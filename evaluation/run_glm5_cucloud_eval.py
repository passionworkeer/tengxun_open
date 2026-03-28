from __future__ import annotations

import json
import argparse
import time
import re
import signal
from pathlib import Path
from typing import Any

import anthropic

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics


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


def parse_response(text: str | None) -> dict[str, list[str]] | None:
    if not text:
        return None
    try:
        text = text.strip()
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
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
        return None


def compute_f1(pred: dict[str, list[str]], gt: dict[str, list[str]]) -> float:
    all_pred = set(
        pred.get("direct_deps", [])
        + pred.get("indirect_deps", [])
        + pred.get("implicit_deps", [])
    )
    all_gt = set(
        gt.get("direct_deps", [])
        + gt.get("indirect_deps", [])
        + gt.get("implicit_deps", [])
    )
    metrics = compute_set_metrics(list(all_gt), list(all_pred))
    return metrics.f1


def _load_existing_results(output_path: Path | None) -> list[dict[str, Any]]:
    if output_path is None or not output_path.exists():
        return []
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


class RequestTimeoutError(TimeoutError):
    pass


def _alarm_handler(signum: int, frame: object) -> None:
    raise RequestTimeoutError("cucloud request timed out")


def _invoke_case_request(
    *,
    client: anthropic.Anthropic,
    prompt: str,
    model: str,
    max_tokens: int,
    timeout: int,
) -> tuple[str | None, str | None]:
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.alarm(timeout)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            timeout=timeout,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)

    raw_output = None
    thinking_output = None
    for block in response.content:
        text = getattr(block, "text", None)
        thinking = getattr(block, "thinking", None)
        if text and raw_output is None:
            raw_output = text
        if thinking and thinking_output is None:
            thinking_output = thinking
    return raw_output, thinking_output


def run_eval(
    cases: list[EvalCase],
    api_key: str,
    base_url: str,
    model: str = "glm-5",
    max_tokens: int = 8192,
    request_timeout: int = 180,
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    client = anthropic.Anthropic(base_url=base_url, api_key=api_key)

    if max_cases is not None:
        cases = cases[:max_cases]

    results = _load_existing_results(output_path)
    completed_case_ids = {item.get("case_id") for item in results}

    for i, case in enumerate(cases):
        if case.case_id in completed_case_ids:
            print(f"[{i + 1}/{len(cases)}] Skipping {case.case_id} (already done)", flush=True)
            continue

        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case, context="")
        prediction = None
        raw_output = None
        thinking_output = None

        for attempt in range(5):
            try:
                raw_output, thinking_output = _invoke_case_request(
                    client=client,
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    timeout=request_timeout,
                )

                if raw_output:
                    prediction = parse_response(raw_output)
                    if prediction:
                        break
                    print(
                        f"  Attempt {attempt + 1}: parse failed, retrying...",
                        flush=True,
                    )
                else:
                    print(f"  Attempt {attempt + 1}: empty content", flush=True)

                time.sleep(3)

            except Exception as e:
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                time.sleep(5)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) if case.direct_gold_fqns else [],
            "indirect_deps": list(case.indirect_gold_fqns)
            if case.indirect_gold_fqns
            else [],
            "implicit_deps": list(case.implicit_gold_fqns)
            if case.implicit_gold_fqns
            else [],
        }

        f1 = compute_f1(prediction or {}, gt_dict) if prediction else 0.0

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "model": model,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "thinking_output": thinking_output,
            "f1": round(f1, 4),
        }
        results.append(result)
        completed_case_ids.add(case.case_id)
        print(f"  F1: {f1:.4f}", flush=True)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nAll cases completed. Results saved to {output_path}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run GLM-5 evaluation via Anthropic SDK on cucloud."
    )
    parser.add_argument(
        "--api-key", type=str, default="sk-sp-oRAg9bMjrnEZjXpIW2NqXPeN6RtW3LpM"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://aigw-gzgy2.cucloud.cn:8443",
    )
    parser.add_argument("--model", type=str, default="glm-5")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/glm5_cucloud_eval_results.json"),
    )
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    run_eval(
        cases=cases,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        request_timeout=args.request_timeout,
        output_path=args.output,
        max_cases=args.max_cases,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
