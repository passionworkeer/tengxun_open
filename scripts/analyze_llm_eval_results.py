#!/usr/bin/env python3
"""
对比 GPT / GLM 评测结果，输出 markdown 报告和图表。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_cases(cases_path: Path) -> dict[str, dict[str, Any]]:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    return {case["id"]: case for case in cases}


def load_results(results_path: Path) -> list[dict[str, Any]]:
    return json.loads(results_path.read_text(encoding="utf-8"))


def enrich_results(
    results: list[dict[str, Any]],
    case_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in results:
        case_meta = case_map.get(item["case_id"], {})
        merged = dict(item)
        merged["failure_type"] = case_meta.get("failure_type", "N/A")
        merged["category"] = case_meta.get("category", merged.get("category", "N/A"))
        merged["difficulty"] = case_meta.get(
            "difficulty", merged.get("difficulty", "unknown")
        )
        enriched.append(merged)
    return enriched


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    f1_scores = [float(item["f1"]) for item in results]
    avg_f1 = sum(f1_scores) / total if total else 0.0
    pass_count = sum(1 for score in f1_scores if score > 0)
    zero_count = sum(1 for score in f1_scores if score == 0)

    by_difficulty: dict[str, list[float]] = defaultdict(list)
    by_failure_type_zero: Counter[str] = Counter()
    by_category: dict[str, list[float]] = defaultdict(list)
    for item in results:
        score = float(item["f1"])
        by_difficulty[item["difficulty"]].append(score)
        by_category[item["category"]].append(score)
        if score == 0:
            by_failure_type_zero[item["failure_type"]] += 1

    difficulty_summary = {
        diff: {
            "count": len(scores),
            "avg_f1": sum(scores) / len(scores) if scores else 0.0,
        }
        for diff, scores in by_difficulty.items()
    }

    category_summary = sorted(
        (
            {
                "category": category,
                "count": len(scores),
                "avg_f1": sum(scores) / len(scores) if scores else 0.0,
            }
            for category, scores in by_category.items()
        ),
        key=lambda item: (-item["avg_f1"], item["category"]),
    )

    requested_models = sorted(
        {str(item.get("model")) for item in results if item.get("model")}
    )
    response_models = sorted(
        {str(item.get("response_model")) for item in results if item.get("response_model")}
    )

    return {
        "total": total,
        "avg_f1": avg_f1,
        "pass_rate": pass_count / total if total else 0.0,
        "zero_count": zero_count,
        "difficulty_summary": difficulty_summary,
        "failure_type_zero": by_failure_type_zero,
        "category_summary": category_summary,
        "requested_models": requested_models,
        "response_models": response_models,
    }


def _label_from_summary(summary: dict[str, Any], fallback: str) -> str:
    response_models = summary.get("response_models") or []
    requested_models = summary.get("requested_models") or []
    if len(response_models) == 1:
        return response_models[0]
    if len(requested_models) == 1:
        return requested_models[0]
    return fallback


def build_case_comparison(
    gpt_results: list[dict[str, Any]],
    glm_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gpt_map = {item["case_id"]: item for item in gpt_results}
    glm_map = {item["case_id"]: item for item in glm_results}

    case_ids = sorted(set(gpt_map) & set(glm_map))
    comparison: list[dict[str, Any]] = []
    for case_id in case_ids:
        gpt_item = gpt_map[case_id]
        glm_item = glm_map[case_id]
        comparison.append(
            {
                "case_id": case_id,
                "difficulty": gpt_item["difficulty"],
                "category": gpt_item["category"],
                "failure_type": gpt_item["failure_type"],
                "gpt_f1": float(gpt_item["f1"]),
                "glm_f1": float(glm_item["f1"]),
                "delta": float(glm_item["f1"]) - float(gpt_item["f1"]),
            }
        )
    return comparison


def write_markdown_report(
    *,
    output_path: Path,
    gpt_results: list[dict[str, Any]],
    glm_results: list[dict[str, Any]],
    gpt_summary: dict[str, Any],
    glm_summary: dict[str, Any],
    case_comparison: list[dict[str, Any]],
) -> None:
    gpt_label = _label_from_summary(gpt_summary, "GPT-5.4")
    glm_label = _label_from_summary(glm_summary, "GLM-5")
    glm_better = sum(1 for item in case_comparison if item["delta"] > 0)
    gpt_better = sum(1 for item in case_comparison if item["delta"] < 0)
    tied = sum(1 for item in case_comparison if item["delta"] == 0)

    biggest_glm_wins = sorted(case_comparison, key=lambda item: item["delta"], reverse=True)[:10]
    biggest_gpt_wins = sorted(case_comparison, key=lambda item: item["delta"])[:10]

    def difficulty_row(summary: dict[str, Any], diff: str) -> str:
        item = summary["difficulty_summary"].get(diff, {"count": 0, "avg_f1": 0.0})
        return f"| {diff} | {item['count']} | {item['avg_f1']:.4f} |"

    def failure_table_lines(summary: dict[str, Any]) -> list[str]:
        items = list(summary["failure_type_zero"].most_common())
        if not items:
            return ["| N/A | 0 |"]
        return [f"| {ft} | {count} |" for ft, count in items]

    lines = [
        "# GPT / GLM 正式评测对比报告",
        "",
        "## 总览",
        "",
        f"- GPT 请求模型：`{', '.join(gpt_summary['requested_models']) or 'N/A'}`",
        f"- GPT 响应模型：`{', '.join(gpt_summary['response_models']) or 'N/A'}`",
        f"- GLM 请求模型：`{', '.join(glm_summary['requested_models']) or 'N/A'}`",
        f"- GLM 响应模型：`{', '.join(glm_summary['response_models']) or 'N/A'}`",
        "",
        "| 模型 | 样本数 | 平均F1 | Pass Rate (F1>0) | F1=0 数量 |",
        "|------|--------|--------|------------------|-----------|",
        f"| {gpt_label} | {gpt_summary['total']} | {gpt_summary['avg_f1']:.4f} | {gpt_summary['pass_rate'] * 100:.1f}% | {gpt_summary['zero_count']} |",
        f"| {glm_label} | {glm_summary['total']} | {glm_summary['avg_f1']:.4f} | {glm_summary['pass_rate'] * 100:.1f}% | {glm_summary['zero_count']} |",
        "",
        "## 难度分层",
        "",
        f"### {gpt_label}",
        "",
        "| Difficulty | Cases | Avg F1 |",
        "|------------|-------|--------|",
        difficulty_row(gpt_summary, "easy"),
        difficulty_row(gpt_summary, "medium"),
        difficulty_row(gpt_summary, "hard"),
        "",
        f"### {glm_label}",
        "",
        "| Difficulty | Cases | Avg F1 |",
        "|------------|-------|--------|",
        difficulty_row(glm_summary, "easy"),
        difficulty_row(glm_summary, "medium"),
        difficulty_row(glm_summary, "hard"),
        "",
        "## 头对头",
        "",
        f"- GLM 更好：`{glm_better}`",
        f"- GPT 更好：`{gpt_better}`",
        f"- 持平：`{tied}`",
        "",
        "## F1=0 失败类型分布",
        "",
        f"### {gpt_label}",
        "",
        "| Failure Type | Count |",
        "|--------------|-------|",
        *failure_table_lines(gpt_summary),
        "",
        f"### {glm_label}",
        "",
        "| Failure Type | Count |",
        "|--------------|-------|",
        *failure_table_lines(glm_summary),
        "",
        f"## {glm_label} 相对 {gpt_label} 提升最大的 10 个 case",
        "",
        "| Case | Difficulty | GPT F1 | GLM F1 | Delta |",
        "|------|------------|--------|--------|-------|",
    ]

    for item in biggest_glm_wins:
        lines.append(
            f"| {item['case_id']} | {item['difficulty']} | {item['gpt_f1']:.4f} | {item['glm_f1']:.4f} | {item['delta']:+.4f} |"
        )

    lines.extend(
        [
            "",
            f"## {gpt_label} 相对 {glm_label} 提升最大的 10 个 case",
            "",
            "| Case | Difficulty | GPT F1 | GLM F1 | Delta |",
            "|------|------------|--------|--------|-------|",
        ]
    )
    for item in biggest_gpt_wins:
        lines.append(
            f"| {item['case_id']} | {item['difficulty']} | {item['gpt_f1']:.4f} | {item['glm_f1']:.4f} | {item['delta']:+.4f} |"
        )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_charts(
    *,
    output_path: Path,
    gpt_results: list[dict[str, Any]],
    glm_results: list[dict[str, Any]],
    gpt_summary: dict[str, Any],
    glm_summary: dict[str, Any],
    case_comparison: list[dict[str, Any]],
) -> None:
    import matplotlib.pyplot as plt

    gpt_label = _label_from_summary(gpt_summary, "GPT-5.4")
    glm_label = _label_from_summary(glm_summary, "GLM-5")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(f"{gpt_label} vs {glm_label} Evaluation Comparison", fontsize=16, fontweight="bold")

    ax1 = axes[0, 0]
    overall_labels = [gpt_label, glm_label]
    overall_values = [gpt_summary["avg_f1"], glm_summary["avg_f1"]]
    bars = ax1.bar(overall_labels, overall_values, color=["#1f77b4", "#ff7f0e"])
    ax1.set_ylim(0, 1.0)
    ax1.set_ylabel("Average F1")
    ax1.set_title("Overall Average F1")
    for bar, value in zip(bars, overall_values):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center")

    ax2 = axes[0, 1]
    difficulties = ["easy", "medium", "hard"]
    x = list(range(len(difficulties)))
    width = 0.35
    gpt_vals = [gpt_summary["difficulty_summary"].get(diff, {}).get("avg_f1", 0.0) for diff in difficulties]
    glm_vals = [glm_summary["difficulty_summary"].get(diff, {}).get("avg_f1", 0.0) for diff in difficulties]
    ax2.bar([i - width / 2 for i in x], gpt_vals, width=width, label=gpt_label, color="#1f77b4")
    ax2.bar([i + width / 2 for i in x], glm_vals, width=width, label=glm_label, color="#ff7f0e")
    ax2.set_xticks(x, [diff.capitalize() for diff in difficulties])
    ax2.set_ylim(0, 1.0)
    ax2.set_ylabel("Average F1")
    ax2.set_title("Average F1 by Difficulty")
    ax2.legend()

    ax3 = axes[1, 0]
    ax3.hist(
        [float(item["f1"]) for item in gpt_results],
        bins=10,
        alpha=0.6,
        label=gpt_label,
        color="#1f77b4",
        edgecolor="black",
    )
    ax3.hist(
        [float(item["f1"]) for item in glm_results],
        bins=10,
        alpha=0.6,
        label=glm_label,
        color="#ff7f0e",
        edgecolor="black",
    )
    ax3.set_xlabel("F1")
    ax3.set_ylabel("Cases")
    ax3.set_title("F1 Distribution")
    ax3.legend()

    ax4 = axes[1, 1]
    top_deltas = sorted(case_comparison, key=lambda item: abs(item["delta"]), reverse=True)[:12]
    labels = [item["case_id"] for item in top_deltas]
    deltas = [item["delta"] for item in top_deltas]
    colors = ["#2ca02c" if delta > 0 else "#d62728" for delta in deltas]
    ax4.barh(labels, deltas, color=colors)
    ax4.axvline(0, color="black", linewidth=1)
    ax4.set_xlabel(f"{glm_label} F1 - {gpt_label} F1")
    ax4.set_title("Largest Case-Level Deltas")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=160, bbox_inches="tight")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze GPT/GLM evaluation results.")
    parser.add_argument(
        "--gpt-results",
        type=Path,
        default=Path("results/gpt5_eval_results.json"),
    )
    parser.add_argument(
        "--glm-results",
        type=Path,
        default=Path("results/glm5_cucloud_eval_results.json"),
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/llm_eval_comparison_20260327.md"),
    )
    parser.add_argument(
        "--chart-output",
        type=Path,
        default=Path("reports/llm_eval_comparison_20260327.png"),
    )
    args = parser.parse_args()

    case_map = load_cases(args.cases)
    gpt_results = enrich_results(load_results(args.gpt_results), case_map)
    glm_results = enrich_results(load_results(args.glm_results), case_map)

    gpt_summary = summarize_results(gpt_results)
    glm_summary = summarize_results(glm_results)
    case_comparison = build_case_comparison(gpt_results, glm_results)

    write_markdown_report(
        output_path=args.report_output,
        gpt_results=gpt_results,
        glm_results=glm_results,
        gpt_summary=gpt_summary,
        glm_summary=glm_summary,
        case_comparison=case_comparison,
    )
    draw_charts(
        output_path=args.chart_output,
        gpt_results=gpt_results,
        glm_results=glm_results,
        gpt_summary=gpt_summary,
        glm_summary=glm_summary,
        case_comparison=case_comparison,
    )

    print(f"Saved report to {args.report_output}")
    print(f"Saved chart to {args.chart_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
