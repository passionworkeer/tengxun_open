#!/usr/bin/env python3
"""
对单个结果文件做 strict 分层重评分。

支持常见的 simple result 结构：
- prediction
- extracted_prediction
- ground_truth（若缺失则按 case_id 从 eval_cases.json 回填）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import compute_layered_dependency_metrics


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_prediction(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("prediction", "extracted_prediction"):
        payload = item.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def _load_eval_ground_truth_map(path: Path) -> dict[str, dict[str, Any]]:
    data = _read_json(path)
    return {
        str(item["id"]): item.get("ground_truth", {})
        for item in data
        if isinstance(item, dict) and item.get("id")
    }


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(item[key]) for item in rows) / len(rows), 4) if rows else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Strictly rescore a single result file.")
    parser.add_argument("--path", type=Path, required=True, help="Result JSON path.")
    parser.add_argument(
        "--eval-cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Eval cases path used to backfill ground truth by case_id.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to <input>_strict.json",
    )
    args = parser.parse_args()

    eval_ground_truth_map = _load_eval_ground_truth_map(args.eval_cases)
    data = _read_json(args.path)
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array result file.")

    rows: list[dict[str, Any]] = []
    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for item in data:
        case_id = str(item.get("case_id", ""))
        ground_truth = item.get("ground_truth") or eval_ground_truth_map.get(case_id)
        if not isinstance(ground_truth, dict):
            continue
        scoring = compute_layered_dependency_metrics(ground_truth, _extract_prediction(item))
        row = {
            "case_id": case_id,
            "difficulty": str(item.get("difficulty", "")),
            "failure_type": str(item.get("failure_type", "")),
            "union_f1": round(scoring.union.f1, 4),
            "macro_f1": round(scoring.macro_f1, 4),
            "direct_f1": round(scoring.direct.f1, 4),
            "indirect_f1": round(scoring.indirect.f1, 4),
            "implicit_f1": round(scoring.implicit.f1, 4),
            "active_layer_count": scoring.active_layer_count,
            "exact_layer_match": scoring.exact_layer_match,
            "exact_union_match": scoring.exact_union_match,
            "matched_fqns": scoring.matched_fqns,
            "mislayered_matches": scoring.mislayered_matches,
            "mislayer_rate": round(scoring.mislayer_rate, 4),
            "scoring": scoring.as_dict(),
        }
        rows.append(row)
        if row["difficulty"]:
            by_difficulty[row["difficulty"]].append(row)

    payload = {
        "source_path": str(args.path),
        "overall": {
            "count": len(rows),
            "avg_union_f1": _avg(rows, "union_f1"),
            "avg_macro_f1": _avg(rows, "macro_f1"),
            "avg_direct_f1": _avg(rows, "direct_f1"),
            "avg_indirect_f1": _avg(rows, "indirect_f1"),
            "avg_implicit_f1": _avg(rows, "implicit_f1"),
            "layer_penalty": round(_avg(rows, "union_f1") - _avg(rows, "macro_f1"), 4),
            "avg_mislayer_rate": _avg(rows, "mislayer_rate"),
            "exact_layer_match_rate": round(
                sum(1 for item in rows if item["exact_layer_match"]) / len(rows), 4
            )
            if rows
            else 0.0,
        },
        "by_difficulty": {
            key: {
                "count": len(subset),
                "avg_union_f1": _avg(subset, "union_f1"),
                "avg_macro_f1": _avg(subset, "macro_f1"),
                "avg_mislayer_rate": _avg(subset, "mislayer_rate"),
            }
            for key, subset in sorted(by_difficulty.items())
        },
        "cases": rows,
    }

    output_path = args.output or args.path.with_name(f"{args.path.stem}_strict.json")
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved strict rescoring to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
