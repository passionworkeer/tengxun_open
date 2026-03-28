#!/usr/bin/env python3
"""
整理 GLM-5 官方评测结果，保留原始文件并输出：
- 逐 case FQN 评分明细
- 难度 / failure type / category 分层统计
- 原始 thinking 输出摘要
- Markdown 报告与图表
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.metrics import compute_set_metrics


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_fqns(block: dict[str, list[str]] | None) -> list[str]:
    if not isinstance(block, dict):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for key in ("direct_deps", "indirect_deps", "implicit_deps"):
        items = block.get(key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if value and value not in seen:
                seen.add(value)
                ordered.append(value)
    return ordered


def enrich_case(
    stable_item: dict[str, Any],
    case_meta: dict[str, Any],
    raw_item: dict[str, Any] | None,
) -> dict[str, Any]:
    gold_fqns = normalize_fqns(stable_item.get("ground_truth"))
    predicted_fqns = normalize_fqns(stable_item.get("prediction"))
    metrics = compute_set_metrics(gold_fqns, predicted_fqns)

    gold_set = set(gold_fqns)
    predicted_set = set(predicted_fqns)
    matched = [item for item in predicted_fqns if item in gold_set]
    missing = [item for item in gold_fqns if item not in predicted_set]
    extra = [item for item in predicted_fqns if item not in gold_set]

    raw_response = raw_item.get("raw_response") if isinstance(raw_item, dict) else None
    raw_usage = raw_response.get("usage") if isinstance(raw_response, dict) else None

    return {
        "case_id": stable_item["case_id"],
        "difficulty": case_meta.get("difficulty", stable_item.get("difficulty", "unknown")),
        "category": case_meta.get("category", stable_item.get("category", "N/A")),
        "failure_type": case_meta.get("failure_type", "N/A"),
        "question": stable_item.get("question"),
        "entry_symbol": case_meta.get("entry_symbol"),
        "entry_file": case_meta.get("entry_file"),
        "requested_model": stable_item.get("model"),
        "response_model": stable_item.get("response_model"),
        "stable_finish_reason": stable_item.get("finish_reason"),
        "raw_finish_reason": raw_item.get("finish_reason") if raw_item else None,
        "precision": round(metrics.precision, 4),
        "recall": round(metrics.recall, 4),
        "f1": round(metrics.f1, 4),
        "gold_count": len(gold_fqns),
        "predicted_count": len(predicted_fqns),
        "matched_count": len(matched),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "gold_fqns": gold_fqns,
        "predicted_fqns": predicted_fqns,
        "matched_fqns": matched,
        "missing_fqns": missing,
        "extra_fqns": extra,
        "raw_reasoning_length": len(raw_item.get("reasoning_output") or "") if raw_item else 0,
        "raw_answer_length": len(raw_item.get("raw_output") or "") if raw_item else 0,
        "raw_usage": raw_usage,
        "raw_output_preview": (raw_item.get("raw_output") or "")[:500] if raw_item else "",
    }


def avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    precision_scores = [float(item["precision"]) for item in cases]
    recall_scores = [float(item["recall"]) for item in cases]
    f1_scores = [float(item["f1"]) for item in cases]
    pass_count = sum(1 for score in f1_scores if score > 0)
    exact_match_count = sum(1 for score in f1_scores if score == 1.0)

    by_difficulty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_failure_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    raw_finish_counter: Counter[str] = Counter()

    for item in cases:
        by_difficulty[item["difficulty"]].append(item)
        by_failure_type[item["failure_type"]].append(item)
        by_category[item["category"]].append(item)
        raw_finish_counter[str(item.get("raw_finish_reason") or "N/A")] += 1

    def summarize_bucket(bucket: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name, items in bucket.items():
            rows.append(
                {
                    "name": name,
                    "count": len(items),
                    "avg_precision": avg([float(item["precision"]) for item in items]),
                    "avg_recall": avg([float(item["recall"]) for item in items]),
                    "avg_f1": avg([float(item["f1"]) for item in items]),
                    "zero_f1_count": sum(1 for item in items if float(item["f1"]) == 0.0),
                }
            )
        return sorted(rows, key=lambda row: (-row["avg_f1"], row["name"]))

    top_cases = sorted(cases, key=lambda item: (-float(item["f1"]), item["case_id"]))[:10]
    bottom_cases = sorted(cases, key=lambda item: (float(item["f1"]), item["case_id"]))[:10]

    return {
        "total_cases": len(cases),
        "avg_precision": avg(precision_scores),
        "avg_recall": avg(recall_scores),
        "avg_f1": avg(f1_scores),
        "pass_rate": round(pass_count / len(cases), 4) if cases else 0.0,
        "exact_match_rate": round(exact_match_count / len(cases), 4) if cases else 0.0,
        "zero_f1_count": sum(1 for score in f1_scores if score == 0.0),
        "raw_finish_reason_counts": dict(raw_finish_counter),
        "avg_raw_reasoning_length": avg([float(item["raw_reasoning_length"]) for item in cases]),
        "difficulty_summary": summarize_bucket(by_difficulty),
        "failure_type_summary": summarize_bucket(by_failure_type),
        "category_summary": summarize_bucket(by_category),
        "top_cases": [
            {
                "case_id": item["case_id"],
                "difficulty": item["difficulty"],
                "category": item["category"],
                "f1": item["f1"],
                "matched_count": item["matched_count"],
                "gold_count": item["gold_count"],
            }
            for item in top_cases
        ],
        "bottom_cases": [
            {
                "case_id": item["case_id"],
                "difficulty": item["difficulty"],
                "category": item["category"],
                "f1": item["f1"],
                "missing_fqns": item["missing_fqns"],
                "extra_fqns": item["extra_fqns"],
            }
            for item in bottom_cases
        ],
    }


def build_comparison_to_gpt(
    glm_cases: list[dict[str, Any]],
    gpt_results: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    if not gpt_results:
        return None

    gpt_map = {item["case_id"]: float(item["f1"]) for item in gpt_results}
    rows: list[dict[str, Any]] = []
    for item in glm_cases:
        gpt_f1 = gpt_map.get(item["case_id"])
        if gpt_f1 is None:
            continue
        glm_f1 = float(item["f1"])
        rows.append(
            {
                "case_id": item["case_id"],
                "difficulty": item["difficulty"],
                "category": item["category"],
                "gpt_f1": round(gpt_f1, 4),
                "glm_f1": round(glm_f1, 4),
                "delta": round(glm_f1 - gpt_f1, 4),
            }
        )

    if not rows:
        return None

    return {
        "glm_better": sum(1 for row in rows if row["delta"] > 0),
        "gpt_better": sum(1 for row in rows if row["delta"] < 0),
        "tied": sum(1 for row in rows if row["delta"] == 0),
        "top_glm_wins": sorted(rows, key=lambda row: row["delta"], reverse=True)[:10],
        "top_gpt_wins": sorted(rows, key=lambda row: row["delta"])[:10],
    }


def write_report(
    output_path: Path,
    summary: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> None:
    def bucket_table(rows: list[dict[str, Any]], limit: int | None = None) -> list[str]:
        selected = rows if limit is None else rows[:limit]
        if not selected:
            return ["| N/A | 0 | 0.0000 | 0.0000 | 0.0000 | 0 |"]
        return [
            f"| {row['name']} | {row['count']} | {row['avg_precision']:.4f} | {row['avg_recall']:.4f} | {row['avg_f1']:.4f} | {row['zero_f1_count']} |"
            for row in selected
        ]

    lines = [
        "# GLM-5 官方评测整理报告",
        "",
        "## 总览",
        "",
        f"- 样本数：`{summary['total_cases']}`",
        f"- 平均 Precision：`{summary['avg_precision']:.4f}`",
        f"- 平均 Recall：`{summary['avg_recall']:.4f}`",
        f"- 平均 F1：`{summary['avg_f1']:.4f}`",
        f"- Pass Rate (F1>0)：`{summary['pass_rate'] * 100:.1f}%`",
        f"- Exact Match Rate (F1=1)：`{summary['exact_match_rate'] * 100:.1f}%`",
        f"- F1=0 数量：`{summary['zero_f1_count']}`",
        f"- 平均 reasoning 长度：`{summary['avg_raw_reasoning_length']:.1f}` 字符",
        "",
        "## 原始 thinking 结束状态",
        "",
        "| Finish Reason | Count |",
        "|---------------|-------|",
    ]
    for name, count in sorted(summary["raw_finish_reason_counts"].items()):
        lines.append(f"| {name} | {count} |")

    lines.extend(
        [
            "",
            "## 难度分层",
            "",
            "| Difficulty | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |",
            "|------------|-------|---------------|------------|--------|------|",
            *bucket_table(summary["difficulty_summary"]),
            "",
            "## Failure Type 分层",
            "",
            "| Failure Type | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |",
            "|--------------|-------|---------------|------------|--------|------|",
            *bucket_table(summary["failure_type_summary"]),
            "",
            "## Category 分层 Top 15",
            "",
            "| Category | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |",
            "|----------|-------|---------------|------------|--------|------|",
            *bucket_table(summary["category_summary"], limit=15),
            "",
            "## 表现最好的 10 个 case",
            "",
            "| Case | Difficulty | Category | F1 | Matched / Gold |",
            "|------|------------|----------|----|----------------|",
        ]
    )
    for row in summary["top_cases"]:
        lines.append(
            f"| {row['case_id']} | {row['difficulty']} | {row['category']} | {row['f1']:.4f} | {row['matched_count']} / {row['gold_count']} |"
        )

    lines.extend(
        [
            "",
            "## 表现最差的 10 个 case",
            "",
            "| Case | Difficulty | Category | F1 | Missing FQNs | Extra FQNs |",
            "|------|------------|----------|----|--------------|------------|",
        ]
    )
    for row in summary["bottom_cases"]:
        missing = ", ".join(row["missing_fqns"][:3]) or "-"
        extra = ", ".join(row["extra_fqns"][:3]) or "-"
        lines.append(
            f"| {row['case_id']} | {row['difficulty']} | {row['category']} | {row['f1']:.4f} | {missing} | {extra} |"
        )

    if comparison:
        lines.extend(
            [
                "",
                "## 与 GPT-5.4 对比",
                "",
                f"- GLM 更好：`{comparison['glm_better']}`",
                f"- GPT 更好：`{comparison['gpt_better']}`",
                f"- 持平：`{comparison['tied']}`",
                "",
                "### GLM 提升最大的 10 个 case",
                "",
                "| Case | Difficulty | GPT F1 | GLM F1 | Delta |",
                "|------|------------|--------|--------|-------|",
            ]
        )
        for row in comparison["top_glm_wins"]:
            lines.append(
                f"| {row['case_id']} | {row['difficulty']} | {row['gpt_f1']:.4f} | {row['glm_f1']:.4f} | {row['delta']:+.4f} |"
            )
        lines.extend(
            [
                "",
                "### GPT 提升最大的 10 个 case",
                "",
                "| Case | Difficulty | GPT F1 | GLM F1 | Delta |",
                "|------|------------|--------|--------|-------|",
            ]
        )
        for row in comparison["top_gpt_wins"]:
            lines.append(
                f"| {row['case_id']} | {row['difficulty']} | {row['gpt_f1']:.4f} | {row['glm_f1']:.4f} | {row['delta']:+.4f} |"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_chart(
    output_path: Path,
    summary: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("GLM-5 Official Evaluation Analysis", fontsize=16, fontweight="bold")

    ax1 = axes[0, 0]
    metric_names = ["Precision", "Recall", "F1"]
    metric_values = [
        summary["avg_precision"],
        summary["avg_recall"],
        summary["avg_f1"],
    ]
    bars = ax1.bar(metric_names, metric_values, color=["#4e79a7", "#f28e2b", "#59a14f"])
    ax1.set_ylim(0, 1.0)
    ax1.set_title("Overall Set Metrics")
    for bar, value in zip(bars, metric_values):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center")

    ax2 = axes[0, 1]
    difficulty_rows = summary["difficulty_summary"]
    labels = [row["name"] for row in difficulty_rows]
    f1_vals = [row["avg_f1"] for row in difficulty_rows]
    ax2.bar(labels, f1_vals, color="#e15759")
    ax2.set_ylim(0, 1.0)
    ax2.set_title("Average F1 by Difficulty")
    ax2.set_ylabel("F1")

    ax3 = axes[1, 0]
    failure_rows = sorted(summary["failure_type_summary"], key=lambda row: row["name"])
    failure_labels = [row["name"] for row in failure_rows]
    failure_vals = [row["avg_f1"] for row in failure_rows]
    ax3.bar(failure_labels, failure_vals, color="#76b7b2")
    ax3.set_ylim(0, 1.0)
    ax3.set_title("Average F1 by Failure Type")
    ax3.set_ylabel("F1")

    ax4 = axes[1, 1]
    if comparison:
        vals = [comparison["glm_better"], comparison["gpt_better"], comparison["tied"]]
        cmp_bars = ax4.bar(["GLM Better", "GPT Better", "Tied"], vals, color=["#59a14f", "#e15759", "#9c755f"])
        ax4.set_title("Head-to-Head vs GPT-5.4")
        for bar, value in zip(cmp_bars, vals):
            ax4.text(bar.get_x() + bar.get_width() / 2, value + 0.3, str(value), ha="center")
    else:
        finish_rows = summary["raw_finish_reason_counts"]
        finish_labels = list(finish_rows.keys())
        finish_vals = list(finish_rows.values())
        fin_bars = ax4.bar(finish_labels, finish_vals, color="#edc948")
        ax4.set_title("Raw Thinking Finish Reasons")
        for bar, value in zip(fin_bars, finish_vals):
            ax4.text(bar.get_x() + bar.get_width() / 2, value + 0.3, str(value), ha="center")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=160, bbox_inches="tight")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze official GLM-5 results.")
    parser.add_argument(
        "--stable-results",
        type=Path,
        default=Path("results/glm_eval_results.json"),
    )
    parser.add_argument(
        "--raw-results",
        type=Path,
        default=Path("results/glm_eval_raw_official_20260328.json"),
    )
    parser.add_argument(
        "--gpt-results",
        type=Path,
        default=Path("results/gpt5_eval_results.json"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
    )
    parser.add_argument(
        "--scored-output",
        type=Path,
        default=Path("results/glm_eval_scored_20260328.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/glm5_eval_analysis_20260328.md"),
    )
    parser.add_argument(
        "--chart-output",
        type=Path,
        default=Path("reports/glm5_eval_analysis_20260328.png"),
    )
    args = parser.parse_args()

    stable_results = load_json(args.stable_results)
    raw_results = load_json(args.raw_results)
    gpt_results = load_json(args.gpt_results) if args.gpt_results.exists() else None
    cases = load_json(args.cases)

    raw_map = {item["case_id"]: item for item in raw_results}
    case_map = {item["id"]: item for item in cases}

    enriched_cases = [
        enrich_case(item, case_map.get(item["case_id"], {}), raw_map.get(item["case_id"]))
        for item in stable_results
    ]
    summary = summarize_cases(enriched_cases)
    comparison = build_comparison_to_gpt(enriched_cases, gpt_results)

    payload = {
        "stable_results_path": str(args.stable_results),
        "raw_results_path": str(args.raw_results),
        "cases_path": str(args.cases),
        "summary": summary,
        "comparison_to_gpt": comparison,
        "cases": enriched_cases,
    }
    args.scored_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_report(args.report_output, summary, comparison)
    draw_chart(args.chart_output, summary, comparison)

    print(f"Saved scored results to {args.scored_output}")
    print(f"Saved report to {args.report_output}")
    print(f"Saved chart to {args.chart_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
