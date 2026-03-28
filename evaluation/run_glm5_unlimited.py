"""
GLM-5 完整输出评测脚本 - 用 requests 直连 cucloud，捕获完整 thinking 块

问题：GLM-5 是思考模型，1024 token 不够。
修复：requests 直连 cucloud API，max_tokens=16384，捕获 thinking + text。
"""

from __future__ import annotations

import json
import argparse
import os
import time
import re
from pathlib import Path
from typing import Any

import requests

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics


BASE_URL = "https://aigw-gzgy2.cucloud.cn:8443"
API_KEY = os.environ.get("CUCLOUD_API_KEY", "")
MODEL = "glm-5"
MAX_TOKENS = 16384


def build_prompt(case: EvalCase, context: str = "") -> str:
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


def run_eval(
    cases: list[EvalCase],
    api_key: str,
    base_url: str,
    model: str = MODEL,
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True, end=" ")

        prompt = build_prompt(case, context="")
        prediction = None
        raw_output = None
        thinking_output = None

        for attempt in range(5):
            try:
                resp = requests.post(
                    f"{base_url}/v1/messages",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": model,
                        "max_tokens": MAX_TOKENS,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("content", [])

                raw_output = None
                thinking_output = None

                for block in content:
                    if block.get("type") == "text":
                        raw_output = block.get("text", "")
                    elif block.get("type") == "thinking":
                        thinking_output = block.get("thinking", "")

                if raw_output:
                    prediction = parse_response(raw_output)
                    if prediction:
                        break
                    print(
                        f"\n  attempt {attempt + 1}: parse failed (raw_len={len(raw_output)}), retrying...",
                        flush=True,
                    )
                else:
                    print(f"\n  attempt {attempt + 1}: empty content", flush=True)

                time.sleep(5)

            except Exception as e:
                wait = 10 * (attempt + 1)
                print(
                    f"\n  attempt {attempt + 1} ERROR: {e}, retrying in {wait}s...",
                    flush=True,
                )
                time.sleep(wait)

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
            "failure_type": getattr(case, "failure_type", ""),
            "model": model,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "thinking_output": thinking_output,
            "f1": round(f1, 4),
        }
        results.append(result)
        print(
            f"F1={f1:.4f} | raw_len={len(raw_output or '')} | thinking_len={len(thinking_output or '')}",
            flush=True,
        )

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nDone. Results saved to {output_path}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="GLM-5 完整输出评测（requests 直连）")
    parser.add_argument("--api-key", type=str, default=API_KEY)
    parser.add_argument("--base-url", type=str, default=BASE_URL)
    parser.add_argument("--model", type=str, default=MODEL)
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/glm5_cucloud_full_tokens.json"),
    )
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("CUCLOUD_API_KEY is not set and --api-key was not provided.")

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} cases. max_tokens={MAX_TOKENS}")

    run_eval(
        cases=cases,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        output_path=args.output,
        max_cases=args.max_cases,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
