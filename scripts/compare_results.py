#!/usr/bin/env python3
"""
对比评测结果脚本

用法:
    python scripts/compare_results.py \
        --baseline results/gpt5_eval_results.json \
        --finetuned results/finetuned_eval_results.json \
        --output reports/finetune_comparison.md
"""

import json
import argparse
from collections import defaultdict
from pathlib import Path
import numpy as np


def load_results(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def compute_metrics(results: list[dict]) -> dict:
    """计算评测指标"""
    f1_scores = [r["f1"] for r in results]

    by_difficulty = defaultdict(list)
    for r in results:
        by_difficulty[r["difficulty"]].append(r["f1"])

    by_category = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r["f1"])

    return {
        "avg_f1": np.mean(f1_scores),
        "median_f1": np.median(f1_scores),
        "std_f1": np.std(f1_scores),
        "pass_rate": len([f for f in f1_scores if f > 0]) / len(f1_scores),
        "perfect_rate": len([f for f in f1_scores if f >= 1.0]) / len(f1_scores),
        "by_difficulty": {
            diff: np.mean(scores) for diff, scores in by_difficulty.items()
        },
        "by_category": {cat: np.mean(scores) for cat, scores in by_category.items()},
    }


def generate_comparison_report(
    baseline_results: list[dict],
    finetuned_results: list[dict],
    output_path: Path,
):
    baseline_metrics = compute_metrics(baseline_results)
    finetuned_metrics = compute_metrics(finetuned_results)

    # 计算每对 case 的差异
    diffs = []
    for b, f in zip(baseline_results, finetuned_results):
        assert b["case_id"] == f["case_id"]
        diffs.append(
            {
                "case_id": b["case_id"],
                "difficulty": b["difficulty"],
                "baseline_f1": b["f1"],
                "finetuned_f1": f["f1"],
                "improvement": f["f1"] - b["f1"],
            }
        )

    # 排序：改进最大的在前面
    diffs.sort(key=lambda x: -x["improvement"])

    improved = [d for d in diffs if d["improvement"] > 0]
    degraded = [d for d in diffs if d["improvement"] < 0]
    unchanged = [d for d in diffs if d["improvement"] == 0]

    report = f"""# Fine-tuning Comparison Report

## Summary

| Metric | GPT-5.4 (Baseline) | Fine-tuned Qwen | Delta |
|--------|-------------------|------------------|-------|
| Average F1 | {baseline_metrics["avg_f1"]:.4f} | {finetuned_metrics["avg_f1"]:.4f} | {finetuned_metrics["avg_f1"] - baseline_metrics["avg_f1"]:+.4f} |
| Median F1 | {baseline_metrics["median_f1"]:.4f} | {finetuned_metrics["median_f1"]:.4f} | {finetuned_metrics["median_f1"] - baseline_metrics["median_f1"]:+.4f} |
| Pass Rate | {baseline_metrics["pass_rate"] * 100:.1f}% | {finetuned_metrics["pass_rate"] * 100:.1f}% | {(finetuned_metrics["pass_rate"] - baseline_metrics["pass_rate"]) * 100:+.1f}% |
| Perfect Rate | {baseline_metrics["perfect_rate"] * 100:.1f}% | {finetuned_metrics["perfect_rate"] * 100:.1f}% | {(finetuned_metrics["perfect_rate"] - baseline_metrics["perfect_rate"]) * 100:+.1f}% |

## Performance by Difficulty

| Difficulty | Baseline F1 | Fine-tuned F1 | Delta |
|------------|-------------|---------------|-------|
| Easy | {baseline_metrics["by_difficulty"].get("easy", 0):.4f} | {finetuned_metrics["by_difficulty"].get("easy", 0):.4f} | {finetuned_metrics["by_difficulty"].get("easy", 0) - baseline_metrics["by_difficulty"].get("easy", 0):+.4f} |
| Medium | {baseline_metrics["by_difficulty"].get("medium", 0):.4f} | {finetuned_metrics["by_difficulty"].get("medium", 0):.4f} | {finetuned_metrics["by_difficulty"].get("medium", 0) - baseline_metrics["by_difficulty"].get("medium", 0):+.4f} |
| Hard | {baseline_metrics["by_difficulty"].get("hard", 0):.4f} | {finetuned_metrics["by_difficulty"].get("hard", 0):.4f} | {finetuned_metrics["by_difficulty"].get("hard", 0) - baseline_metrics["by_difficulty"].get("hard", 0):+.4f} |

## Case-level Changes

- **Improved**: {len(improved)} cases
- **Degraded**: {len(degraded)} cases  
- **Unchanged**: {len(unchanged)} cases

## Top Improvements

| Case ID | Difficulty | Baseline F1 | Fine-tuned F1 | Improvement |
|---------|------------|-------------|---------------|-------------|
"""

    for d in diffs[:10]:
        if d["improvement"] > 0:
            report += f"| {d['case_id']} | {d['difficulty']} | {d['baseline_f1']:.4f} | {d['finetuned_f1']:.4f} | {d['improvement']:+.4f} |\n"

    report += f"""
## Top Degradations

| Case ID | Difficulty | Baseline F1 | Fine-tuned F1 | Change |
|---------|------------|-------------|---------------|--------|
"""

    for d in diffs[-10:]:
        if d["improvement"] < 0:
            report += f"| {d['case_id']} | {d['difficulty']} | {d['baseline_f1']:.4f} | {d['finetuned_f1']:.4f} | {d['improvement']:+.4f} |\n"

    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Report saved to {output_path}")

    # 打印摘要
    print(f"""
Comparison Summary:
  Baseline Avg F1:  {baseline_metrics["avg_f1"]:.4f}
  Fine-tuned Avg F1: {finetuned_metrics["avg_f1"]:.4f}
  Delta: {finetuned_metrics["avg_f1"] - baseline_metrics["avg_f1"]:+.4f}
  
  Improved: {len(improved)} cases
  Degraded: {len(degraded)} cases
  Unchanged: {len(unchanged)} cases
""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--finetuned", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/finetune_comparison.md")
    )
    args = parser.parse_args()

    baseline = load_results(args.baseline)
    finetuned = load_results(args.finetuned)

    print(f"Baseline: {len(baseline)} cases")
    print(f"Fine-tuned: {len(finetuned)} cases")

    generate_comparison_report(baseline, finetuned, args.output)


if __name__ == "__main__":
    main()
