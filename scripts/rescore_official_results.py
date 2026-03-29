#!/usr/bin/env python3
"""
对现有正式结果做严格分层重评分。

不重新调用模型，只利用已有 per-case 预测结果离线重算：
- union F1（旧口径）
- macro F1（strict 分层口径）
- direct / indirect / implicit 三层指标
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import compute_layered_dependency_metrics

RESULTS_DIR = ROOT / "results"
STRICT_DIR = RESULTS_DIR / "strict_metrics_20260329"
REPORT_PATH = ROOT / "reports" / "strict_scoring_audit_20260329.md"
EVAL_CASES_PATH = ROOT / "data" / "eval_cases.json"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _extract_prediction(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("prediction", "extracted_prediction"):
        payload = item.get(key)
        if isinstance(payload, dict):
            return payload
    return {}


def _load_eval_ground_truth_map() -> dict[str, dict[str, Any]]:
    data = _read_json(EVAL_CASES_PATH)
    return {
        str(item["id"]): item.get("ground_truth", {})
        for item in data
        if isinstance(item, dict) and item.get("id")
    }


def _build_case_row(
    *,
    source: str,
    case_id: str,
    difficulty: str,
    failure_type: str,
    ground_truth: dict[str, Any],
    prediction: dict[str, Any],
) -> dict[str, Any]:
    scoring = compute_layered_dependency_metrics(ground_truth, prediction)
    return {
        "source": source,
        "case_id": case_id,
        "difficulty": difficulty,
        "failure_type": failure_type,
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


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def avg(key: str, subset: list[dict[str, Any]]) -> float:
        return round(sum(float(item[key]) for item in subset) / len(subset), 4) if subset else 0.0

    overall = {
        "count": len(rows),
        "avg_union_f1": avg("union_f1", rows),
        "avg_macro_f1": avg("macro_f1", rows),
        "avg_direct_f1": avg("direct_f1", rows),
        "avg_indirect_f1": avg("indirect_f1", rows),
        "avg_implicit_f1": avg("implicit_f1", rows),
        "layer_penalty": round(avg("union_f1", rows) - avg("macro_f1", rows), 4),
        "avg_mislayer_rate": avg("mislayer_rate", rows),
        "exact_layer_match_rate": round(
            sum(1 for item in rows if item["exact_layer_match"]) / len(rows), 4
        )
        if rows
        else 0.0,
    }

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        "by_difficulty": defaultdict(list),
        "by_failure_type": defaultdict(list),
    }
    for row in rows:
        grouped["by_difficulty"][row["difficulty"]].append(row)
        grouped["by_failure_type"][row["failure_type"]].append(row)

    summary = {"overall": overall}
    for name, bucket in grouped.items():
        summary[name] = {
            key: {
                "count": len(subset),
                "avg_union_f1": avg("union_f1", subset),
                "avg_macro_f1": avg("macro_f1", subset),
                "avg_direct_f1": avg("direct_f1", subset),
                "avg_indirect_f1": avg("indirect_f1", subset),
                "avg_implicit_f1": avg("implicit_f1", subset),
                "layer_penalty": round(
                    avg("union_f1", subset) - avg("macro_f1", subset), 4
                ),
                "avg_mislayer_rate": avg("mislayer_rate", subset),
            }
            for key, subset in sorted(bucket.items())
            if key
        }
    return summary


def _rescore_simple(
    path: Path,
    source_name: str,
    eval_ground_truth_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    data = _read_json(path)
    rows: list[dict[str, Any]] = []
    for item in data:
        case_id = str(item.get("case_id", ""))
        ground_truth = item.get("ground_truth") or eval_ground_truth_map.get(case_id)
        if not isinstance(ground_truth, dict):
            continue
        rows.append(
            _build_case_row(
                source=source_name,
                case_id=case_id,
                difficulty=str(item.get("difficulty", "")),
                failure_type=str(item.get("failure_type", "")),
                ground_truth=ground_truth,
                prediction=_extract_prediction(item),
            )
        )
    return {"source_path": str(path.relative_to(ROOT)), "cases": rows, "summary": _summarize(rows)}


def _rescore_gpt_rag(path: Path) -> dict[str, Any]:
    data = _read_json(path)
    paired_rows: list[dict[str, Any]] = []
    no_rag_rows: list[dict[str, Any]] = []
    with_rag_rows: list[dict[str, Any]] = []

    for item in data:
        ground_truth = item.get("ground_truth")
        if not isinstance(ground_truth, dict):
            continue

        no_rag = _build_case_row(
            source="gpt_rag_no_rag",
            case_id=str(item.get("case_id", "")),
            difficulty=str(item.get("difficulty", "")),
            failure_type=str(item.get("failure_type", "")),
            ground_truth=ground_truth,
            prediction=item.get("no_rag", {}).get("prediction", {}) if isinstance(item.get("no_rag"), dict) else {},
        )
        with_rag = _build_case_row(
            source="gpt_rag_with_rag",
            case_id=str(item.get("case_id", "")),
            difficulty=str(item.get("difficulty", "")),
            failure_type=str(item.get("failure_type", "")),
            ground_truth=ground_truth,
            prediction=item.get("with_rag", {}).get("prediction", {}) if isinstance(item.get("with_rag"), dict) else {},
        )
        no_rag_rows.append(no_rag)
        with_rag_rows.append(with_rag)
        paired_rows.append(
            {
                "case_id": item.get("case_id", ""),
                "difficulty": item.get("difficulty", ""),
                "failure_type": item.get("failure_type", ""),
                "union_delta": round(with_rag["union_f1"] - no_rag["union_f1"], 4),
                "macro_delta": round(with_rag["macro_f1"] - no_rag["macro_f1"], 4),
            }
        )

    return {
        "source_path": str(path.relative_to(ROOT)),
        "no_rag": {"cases": no_rag_rows, "summary": _summarize(no_rag_rows)},
        "with_rag": {"cases": with_rag_rows, "summary": _summarize(with_rag_rows)},
        "paired_delta": {
            "avg_union_delta": round(
                sum(item["union_delta"] for item in paired_rows) / len(paired_rows), 4
            )
            if paired_rows
            else 0.0,
            "avg_macro_delta": round(
                sum(item["macro_delta"] for item in paired_rows) / len(paired_rows), 4
            )
            if paired_rows
            else 0.0,
            "cases": paired_rows,
        },
    }


def _build_report(summary_map: dict[str, Any]) -> str:
    lines = [
        "# 严格分层评分审计（2026-03-29）",
        "",
        "## 总览",
        "",
        "| Experiment | Avg Union F1 | Avg Active-Layer Macro F1 | Avg Mislayer Rate | Exact Layer Match Rate |",
        "|---|---:|---:|---:|---:|",
    ]

    ordered_keys = [
        "gpt_baseline",
        "glm_baseline",
        "qwen_baseline_recovered",
        "pe_baseline",
        "pe_system_prompt",
        "pe_cot",
        "pe_fewshot",
        "pe_postprocess",
        "qwen_pe_only",
        "qwen_rag_only",
        "qwen_pe_rag",
        "qwen_ft_only",
        "qwen_pe_ft",
        "qwen_pe_rag_ft",
    ]

    for key in ordered_keys:
        payload = summary_map.get(key)
        if not payload:
            continue
        overall = payload["summary"]["overall"]
        lines.append(
            f"| {key} | {overall['avg_union_f1']:.4f} | {overall['avg_macro_f1']:.4f} | "
            f"{overall['avg_mislayer_rate']:.4f} | {overall['exact_layer_match_rate']:.4f} |"
        )

    gpt_rag = summary_map.get("gpt_rag_e2e")
    if gpt_rag:
        lines.extend(
            [
                "",
                "## GPT RAG Delta",
                "",
                f"- No-RAG avg union F1: `{gpt_rag['no_rag']['summary']['overall']['avg_union_f1']:.4f}`",
                f"- With-RAG avg union F1: `{gpt_rag['with_rag']['summary']['overall']['avg_union_f1']:.4f}`",
                f"- No-RAG avg active-layer macro F1: `{gpt_rag['no_rag']['summary']['overall']['avg_macro_f1']:.4f}`",
                f"- With-RAG avg active-layer macro F1: `{gpt_rag['with_rag']['summary']['overall']['avg_macro_f1']:.4f}`",
                f"- No-RAG avg mislayer rate: `{gpt_rag['no_rag']['summary']['overall']['avg_mislayer_rate']:.4f}`",
                f"- With-RAG avg mislayer rate: `{gpt_rag['with_rag']['summary']['overall']['avg_mislayer_rate']:.4f}`",
                f"- Avg union delta: `{gpt_rag['paired_delta']['avg_union_delta']:+.4f}`",
                f"- Avg macro delta: `{gpt_rag['paired_delta']['avg_macro_delta']:+.4f}`",
                "",
            ]
        )

    lines.extend(
        [
            "## 解释",
            "",
            "- `union F1` 是旧口径，只看三层并集后的 FQN 命中。",
            "- `macro F1` 是 strict 主口径，只对 gold 或 prediction 非空的 active layers 求平均。",
            "- `mislayer rate` 衡量“FQN 命中了，但放错层”的比例；越高越差。",
            "- `layer penalty = union - active-layer macro` 只作为辅助参考，不再单独作为主结论指标。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    STRICT_DIR.mkdir(parents=True, exist_ok=True)
    eval_ground_truth_map = _load_eval_ground_truth_map()

    sources: dict[str, Any] = {}
    simple_sources = {
        "gpt_baseline": RESULTS_DIR / "gpt5_eval_results.json",
        "glm_baseline": RESULTS_DIR / "glm_eval_results.json",
        "qwen_baseline_recovered": RESULTS_DIR / "qwen_baseline_recovered_20260328.json",
        "pe_baseline": RESULTS_DIR / "pe_eval_54_20260328" / "pe_baseline.json",
        "pe_system_prompt": RESULTS_DIR / "pe_eval_54_20260328" / "pe_system_prompt.json",
        "pe_cot": RESULTS_DIR / "pe_eval_54_20260328" / "pe_cot.json",
        "pe_fewshot": RESULTS_DIR / "pe_eval_54_20260328" / "pe_fewshot.json",
        "pe_postprocess": RESULTS_DIR / "pe_eval_54_20260328" / "pe_postprocess.json",
        "qwen_pe_only": RESULTS_DIR / "qwen_pe_only_20260328.json",
        "qwen_rag_only": RESULTS_DIR / "qwen_rag_only_google_20260328.json",
        "qwen_pe_rag": RESULTS_DIR / "qwen_pe_rag_google_20260328.json",
        "qwen_ft_only": RESULTS_DIR / "qwen_ft_20260327_160136.json",
        "qwen_pe_ft": RESULTS_DIR / "qwen_pe_ft_20260327_162308.json",
        "qwen_pe_rag_ft": RESULTS_DIR / "qwen_pe_rag_ft_google_20260328.json",
    }

    for name, path in simple_sources.items():
        if not path.exists():
            continue
        payload = _rescore_simple(path, name, eval_ground_truth_map)
        sources[name] = payload
        _write_json(STRICT_DIR / f"{name}.json", payload)

    gpt_rag_path = RESULTS_DIR / "gpt_rag_e2e_54cases_20260328.json"
    if gpt_rag_path.exists():
        payload = _rescore_gpt_rag(gpt_rag_path)
        sources["gpt_rag_e2e"] = payload
        _write_json(STRICT_DIR / "gpt_rag_e2e.json", payload)

    _write_json(STRICT_DIR / "summary.json", sources)
    REPORT_PATH.write_text(_build_report(sources), encoding="utf-8")

    print(f"Saved strict metrics to {STRICT_DIR}")
    print(f"Saved report to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
