#!/usr/bin/env python3
"""
Qwen3.5 Evaluation Results Analyzer
生成评测报告和可视化图表
"""

import json
from collections import Counter, defaultdict
from pathlib import Path


def analyze_results(results_path: str = "results/qwen3_eval_results.json"):
    with open(results_path) as f:
        results = json.load(f)

    # Load original cases for failure_type
    cases = json.load(open("data/eval_cases.json"))
    case_map = {c["id"]: c for c in cases}

    # Add failure_type
    for r in results:
        cid = r["case_id"]
        orig = case_map.get(cid, {})
        r["failure_type"] = orig.get("failure_type", "N/A")

    # Overall metrics
    f1_scores = [r["f1"] for r in results]
    total = len(results)
    avg_f1 = sum(f1_scores) / total

    # By difficulty
    by_difficulty = defaultdict(list)
    for r in results:
        by_difficulty[r["difficulty"]].append(r["f1"])

    # Failed cases
    failed = [r for r in results if r["f1"] == 0]
    ft_counts = Counter(r["failure_type"] for r in failed)

    print("=" * 70)
    print("QWEN3.5 EVALUATION RESULTS")
    print("=" * 70)
    print(f"Total Cases: {total}")
    print(f"Overall Average F1: {avg_f1:.4f}")
    print(f"Failed (F1=0): {len(failed)} cases ({len(failed) / total * 100:.1f}%)")
    print()

    # Difficulty breakdown
    print("--- By Difficulty ---")
    for diff in ["easy", "medium", "hard"]:
        scores = by_difficulty.get(diff, [])
        if scores:
            print(
                f"{diff.upper()}: {len(scores)} cases, Avg F1: {sum(scores) / len(scores):.4f}"
            )

    print()
    print("--- Failure Type Distribution (F1=0 cases) ---")
    for ft, cnt in ft_counts.most_common():
        print(f"  {ft}: {cnt}")

    return results, failed, ft_counts


def generate_report(results_path: str = "results/qwen3_eval_results.json"):
    import matplotlib.pyplot as plt
    import numpy as np

    with open(results_path) as f:
        results = json.load(f)

    cases = json.load(open("data/eval_cases.json"))
    case_map = {c["id"]: c for c in cases}

    for r in results:
        cid = r["case_id"]
        orig = case_map.get(cid, {})
        r["failure_type"] = orig.get("failure_type", "N/A")

    f1_scores = [r["f1"] for r in results]
    failed = [r for r in results if r["f1"] == 0]
    ft_counts = Counter(r["failure_type"] for r in failed)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Qwen3.5 Evaluation Results", fontsize=16, fontweight="bold")

    # 1. F1 Distribution
    ax1 = axes[0, 0]
    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    counts, _, patches = ax1.hist(f1_scores, bins=bins, edgecolor="black", alpha=0.7)
    ax1.set_xlabel("F1 Score")
    ax1.set_ylabel("Number of Cases")
    ax1.set_title("F1 Score Distribution")

    # 2. By Difficulty
    ax2 = axes[0, 1]
    diff_groups = {"easy": [], "medium": [], "hard": []}
    for r in results:
        diff_groups[r["difficulty"]].append(r["f1"])
    diff_means = [np.mean(diff_groups[d]) for d in ["easy", "medium", "hard"]]
    colors = ["#2ecc71", "#f39c12", "#e74c3c"]
    bars = ax2.bar(
        ["Easy", "Medium", "Hard"],
        diff_means,
        color=colors,
        edgecolor="black",
        alpha=0.8,
    )
    ax2.set_ylabel("Average F1 Score")
    ax2.set_title("Performance by Difficulty")
    ax2.set_ylim(0, 0.6)
    for bar, val in zip(bars, diff_means):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() / 2,
            f"{val:.3f}",
            ha="center",
            va="center",
            fontsize=12,
            fontweight="bold",
        )

    # 3. Failure Type Heatmap
    ax3 = axes[1, 0]
    ft_labels = [ft for ft, _ in ft_counts.most_common()]
    ft_values = [cnt for _, cnt in ft_counts.most_common()]
    colors = ["#e74c3c", "#e67e22", "#f39c12", "#27ae60", "#3498db"][: len(ft_labels)]
    bars = ax3.barh(ft_labels, ft_values, color=colors, edgecolor="black", alpha=0.8)
    ax3.set_xlabel("Number of Failed Cases")
    ax3.set_title(f"Failure Type Bottleneck Heatmap ({len(failed)} F1=0 cases)")
    for bar, val in zip(bars, ft_values):
        ax3.text(
            bar.get_width() + 0.1,
            bar.get_y() + bar.get_height() / 2,
            f"{val}",
            va="center",
            fontsize=11,
            fontweight="bold",
        )

    # 4. Summary
    ax4 = axes[1, 1]
    ax4.axis("off")
    total = len(results)
    avg_f1 = np.mean(f1_scores)
    pass_rate = len([r for r in results if r["f1"] > 0]) / total * 100
    summary_text = f"""
    ╔══════════════════════════════════════════╗
    ║       QWEN3.5 EVALUATION SUMMARY        ║
    ╠══════════════════════════════════════════╣
    ║  Total Cases:        {total:<22}║
    ║  Average F1:         {avg_f1:<22.4f}║
    ║  Pass Rate (F1>0):  {pass_rate:<21.1f}%║
    ║  Full Fail (F1=0):  {len(failed):<22}║
    ╚══════════════════════════════════════════╝
    """
    ax4.text(
        0.5,
        0.5,
        summary_text,
        transform=ax4.transAxes,
        fontsize=11,
        verticalalignment="center",
        horizontalalignment="center",
        fontfamily="monospace",
        bbox=dict(boxstyle="round", facecolor="#f8f9fa", alpha=0.8),
    )

    plt.tight_layout()
    output_path = results_path.replace(".json", "_charts.png")
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved charts to {output_path}")


if __name__ == "__main__":
    import sys

    results_path = (
        sys.argv[1] if len(sys.argv) > 1 else "results/qwen3_eval_results.json"
    )
    results, failed, ft_counts = analyze_results(results_path)
    generate_report(results_path)
