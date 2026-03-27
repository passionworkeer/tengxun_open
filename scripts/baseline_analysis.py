"""Agent B: Baseline analysis and visualization"""

import json
import sys
from pathlib import Path
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from evaluation.metrics import compute_set_metrics


def compute_f1(pred, gt):
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
    m = compute_set_metrics(list(all_gt), list(all_pred))
    return m.f1, m.precision, m.recall


def main():
    base = Path("/workspace/tengxun_open")
    results_dir = base / "results"
    data = json.load(open(results_dir / "qwen_baseline.json"))

    records = []
    for item in data:
        pred = item.get("extracted_prediction")
        gt = item["ground_truth"]
        f1 = prec = rec = 0.0
        valid = pred is not None
        if valid:
            f1, prec, rec = compute_f1(pred, gt)
        records.append(
            {
                "case_id": item["case_id"],
                "difficulty": item["difficulty"],
                "category": item.get("category", "unknown"),
                "f1": round(f1, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "valid": valid,
            }
        )

    # --- 1. summary ---
    valid_recs = [r for r in records if r["valid"]]
    n_valid = len(valid_recs)
    all_f1 = [r["f1"] for r in valid_recs]
    overall_f1_mean = round(np.mean(all_f1), 4) if all_f1 else 0.0

    by_difficulty = {}
    for diff in ["easy", "medium", "hard"]:
        diff_recs = [r for r in valid_recs if r["difficulty"] == diff]
        diff_f1 = [r["f1"] for r in diff_recs]
        by_difficulty[diff] = {
            "count": len(diff_recs),
            "total": sum(1 for r in records if r["difficulty"] == diff),
            "f1_mean": round(np.mean(diff_f1), 4) if diff_f1 else 0.0,
            "f1_std": round(np.std(diff_f1), 4) if diff_f1 else 0.0,
            "f1_median": round(np.median(diff_f1), 4) if diff_f1 else 0.0,
        }

    by_category = {}
    cats = set(r["category"] for r in records)
    for cat in sorted(cats):
        cat_recs = [r for r in valid_recs if r["category"] == cat]
        cat_f1 = [r["f1"] for r in cat_recs]
        by_category[cat] = {
            "count": len(cat_recs),
            "f1_mean": round(np.mean(cat_f1), 4) if cat_f1 else 0.0,
        }

    # failure types
    failure_types = Counter()
    for item in data:
        if item.get("extracted_prediction") is None:
            failure_types["parse_failed"] += 1
        else:
            f1 = compute_f1(item["extracted_prediction"], item["ground_truth"])[0]
            if f1 == 0.0:
                failure_types["f1_zero"] += 1
            elif f1 < 0.5:
                failure_types["f1_low"] += 1
            elif f1 < 1.0:
                failure_types["partial_match"] += 1
            else:
                failure_types["perfect_match"] += 1

    summary = {
        "total_cases": len(data),
        "valid_results": n_valid,
        "parse_failures": len(data) - n_valid,
        "overall_f1_mean": overall_f1_mean,
        "overall_f1_std": round(np.std(all_f1), 4) if all_f1 else 0.0,
        "overall_f1_median": round(np.median(all_f1), 4) if all_f1 else 0.0,
        "by_difficulty": by_difficulty,
        "by_category": by_category,
        "failure_distribution": dict(failure_types),
    }

    with open(results_dir / "qwen_baseline_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # --- 2. raw outputs ---
    raw_outputs = [
        {"case_id": item["case_id"], "model_output": item["model_output"]}
        for item in data
    ]
    with open(
        results_dir / "qwen_baseline_raw_outputs.json", "w", encoding="utf-8"
    ) as f:
        json.dump(raw_outputs, f, ensure_ascii=False, indent=2)

    # --- 3. charts ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Qwen Baseline Evaluation Summary", fontsize=16, fontweight="bold")

    # 3a. F1 distribution histogram
    ax = axes[0, 0]
    if all_f1:
        ax.hist(all_f1, bins=20, color="#4C72B0", edgecolor="white", alpha=0.85)
    ax.set_title("F1 Score Distribution")
    ax.set_xlabel("F1")
    ax.set_ylabel("Count")
    ax.axvline(
        overall_f1_mean,
        color="red",
        linestyle="--",
        label=f"Mean={overall_f1_mean:.3f}",
    )
    ax.legend()

    # 3b. F1 by difficulty
    ax = axes[0, 1]
    diffs = ["easy", "medium", "hard"]
    means = [by_difficulty[d]["f1_mean"] for d in diffs]
    colors = ["#55A868", "#4C72B0", "#C44E52"]
    bars = ax.bar(diffs, means, color=colors, edgecolor="white")
    ax.set_title("Mean F1 by Difficulty")
    ax.set_ylabel("Mean F1")
    for bar, val in zip(bars, means):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.01,
            f"{val:.3f}",
            ha="center",
            fontsize=10,
        )

    # 3c. Failure type distribution
    ax = axes[1, 0]
    labels = list(failure_types.keys())
    sizes = list(failure_types.values())
    color_map = {
        "parse_failed": "#C44E52",
        "f1_zero": "#D9A441",
        "f1_low": "#8172B2",
        "partial_match": "#4C72B0",
        "perfect_match": "#55A868",
    }
    pie_colors = [color_map.get(l, "#999999") for l in labels]
    ax.pie(sizes, labels=labels, colors=pie_colors, autopct="%1.0f%%", startangle=140)
    ax.set_title("Result Distribution")

    # 3d. Summary text
    ax = axes[1, 1]
    ax.axis("off")
    txt = (
        f"Total Cases: {len(data)}\n"
        f"Valid Results: {n_valid}  ({n_valid / len(data) * 100:.0f}%)\n"
        f"Parse Failures: {len(data) - n_valid}\n"
        f"\n"
        f"Overall F1: {overall_f1_mean:.4f} (std={summary['overall_f1_std']:.4f})\n"
        f"\n"
        f"Easy:   {by_difficulty['easy']['f1_mean']:.4f}  (n={by_difficulty['easy']['count']}/{by_difficulty['easy']['total']})\n"
        f"Medium: {by_difficulty['medium']['f1_mean']:.4f}  (n={by_difficulty['medium']['count']}/{by_difficulty['medium']['total']})\n"
        f"Hard:   {by_difficulty['hard']['f1_mean']:.4f}  (n={by_difficulty['hard']['count']}/{by_difficulty['hard']['total']})\n"
    )
    ax.text(
        0.1,
        0.9,
        txt,
        transform=ax.transAxes,
        fontsize=12,
        verticalalignment="top",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="#f0f0f0", alpha=0.8),
    )

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out_png = results_dir / "qwen_baseline_charts.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print("Done.")
    print(f"  Summary:  {results_dir / 'qwen_baseline_summary.json'}")
    print(f"  Raw:      {results_dir / 'qwen_baseline_raw_outputs.json'}")
    print(f"  Charts:   {out_png}")


if __name__ == "__main__":
    main()
