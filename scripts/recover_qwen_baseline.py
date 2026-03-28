#!/usr/bin/env python3
"""
从旧版 Qwen baseline 原始输出中恢复可解析的最终 JSON。

旧文件里常见模式是：
1. 先输出一个带 `...` 的示例 JSON
2. 再输出解释 / thinking
3. 最后才输出真正可解析的 JSON

本脚本会：
- 尝试提取最后一个合法的 {"ground_truth": ...} JSON 块
- 按 data/eval_cases.json 的顺序将 case_0 / case_1 映射回正式 case id
- 重新计算全量 54 case 的严格 F1（未恢复 case 记 0）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import compute_set_metrics


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_last_ground_truth_json(text: str) -> dict[str, list[str]] | None:
    needle = '"ground_truth"'
    positions: list[int] = []
    start = 0
    while True:
        idx = text.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1

    for pos in reversed(positions):
        left = text.rfind("{", 0, pos)
        while left != -1:
            depth = 0
            for right in range(left, len(text)):
                char = text[right]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        blob = text[left : right + 1]
                        try:
                            data = json.loads(blob)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(data, dict) and "ground_truth" in data:
                            gt = data["ground_truth"]
                            return {
                                "direct_deps": gt.get("direct_deps", []),
                                "indirect_deps": gt.get("indirect_deps", []),
                                "implicit_deps": gt.get("implicit_deps", []),
                            }
            left = text.rfind("{", 0, left)
    return None


def compute_f1(pred: dict[str, list[str]] | None, gt: dict[str, list[str]]) -> float:
    if not pred:
        return 0.0
    predicted = set(
        pred.get("direct_deps", [])
        + pred.get("indirect_deps", [])
        + pred.get("implicit_deps", [])
    )
    gold = set(
        gt.get("direct_deps", [])
        + gt.get("indirect_deps", [])
        + gt.get("implicit_deps", [])
    )
    return compute_set_metrics(list(gold), list(predicted)).f1


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover legacy Qwen baseline outputs.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/qwen_baseline.json"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/qwen_baseline_recovered_20260328.json"),
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=Path("results/qwen_baseline_recovered_summary_20260328.json"),
    )
    args = parser.parse_args()

    raw_results = load_json(args.input)
    cases = load_json(args.cases)

    if len(raw_results) != len(cases):
        raise SystemExit(
            f"Input results count {len(raw_results)} != eval cases count {len(cases)}"
        )

    recovered: list[dict[str, Any]] = []
    by_difficulty: dict[str, list[float]] = {}
    parsed_count = 0

    for idx, (item, case) in enumerate(zip(raw_results, cases)):
        prediction = extract_last_ground_truth_json(item.get("model_output", ""))
        if prediction:
            parsed_count += 1

        ground_truth = item["ground_truth"]
        score = round(compute_f1(prediction, ground_truth), 4)
        difficulty = case.get("difficulty", item.get("difficulty", "unknown"))
        by_difficulty.setdefault(difficulty, []).append(score)

        recovered.append(
            {
                "original_case_id": item.get("case_id"),
                "case_id": case["id"],
                "difficulty": difficulty,
                "category": case.get("category", item.get("category")),
                "failure_type": case.get("failure_type", "N/A"),
                "question": case.get("question", item.get("question")),
                "ground_truth": ground_truth,
                "prediction": prediction,
                "raw_output": item.get("model_output", ""),
                "f1": score,
                "recovered": prediction is not None,
            }
        )

    avg_f1 = round(sum(item["f1"] for item in recovered) / len(recovered), 4)
    summary = {
        "input_path": str(args.input),
        "cases_path": str(args.cases),
        "total_cases": len(recovered),
        "recovered_cases": parsed_count,
        "parse_failures": len(recovered) - parsed_count,
        "overall_avg_f1": avg_f1,
        "by_difficulty": {
            name: {
                "count": len(scores),
                "avg_f1": round(sum(scores) / len(scores), 4) if scores else 0.0,
            }
            for name, scores in sorted(by_difficulty.items())
        },
    }

    args.output.write_text(
        json.dumps(recovered, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Saved recovered results to {args.output}")
    print(f"Saved summary to {args.summary_output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
