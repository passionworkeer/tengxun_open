#!/usr/bin/env python3
"""
生成最终交付版图表与指标快照。

输入：
- 正式评测结果
- 正式 PE 结果
- 正式 RAG 检索结果
- 完整 Qwen 消融结果
- 训练日志

输出：
- img/final_delivery/*.png
- reports/final_metrics_snapshot_20260328.json
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "img" / "final_delivery"
SNAPSHOT_PATH = ROOT / "reports" / "final_metrics_snapshot_20260328.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def round4(value: float) -> float:
    return round(float(value), 4)


def summarize_baseline_results(
    results: list[dict[str, Any]],
    case_map: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    by_difficulty: dict[str, list[float]] = defaultdict(list)
    by_failure_type: dict[str, list[float]] = defaultdict(list)
    zero_by_failure_type: Counter[str] = Counter()
    zero_heatmap: dict[str, Counter[str]] = defaultdict(Counter)

    for item in results:
        case_id = item["case_id"]
        meta = case_map.get(case_id, {}) if case_map else {}
        difficulty = item.get("difficulty") or meta.get("difficulty", "unknown")
        failure_type = item.get("failure_type") or meta.get("failure_type", "N/A")
        f1 = float(item.get("f1", 0.0))
        by_difficulty[difficulty].append(f1)
        by_failure_type[failure_type].append(f1)
        if f1 == 0.0:
            zero_by_failure_type[failure_type] += 1
            zero_heatmap[difficulty][failure_type] += 1

    return {
        "total_cases": len(results),
        "avg_f1": round4(avg([float(item.get("f1", 0.0)) for item in results])),
        "by_difficulty": {
            key: {"count": len(vals), "avg_f1": round4(avg(vals))}
            for key, vals in sorted(by_difficulty.items())
        },
        "by_failure_type": {
            key: {"count": len(vals), "avg_f1": round4(avg(vals)), "zero_count": zero_by_failure_type[key]}
            for key, vals in sorted(by_failure_type.items())
        },
        "zero_by_failure_type": dict(zero_by_failure_type),
        "zero_heatmap": {
            difficulty: dict(counter) for difficulty, counter in zero_heatmap.items()
        },
    }


def summarize_qwen_recovered(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "avg_f1": float(data["overall_avg_f1"]),
        "recovered_cases": int(data["recovered_cases"]),
        "parse_failures": int(data["parse_failures"]),
        "by_difficulty": {
            key: {"count": int(val["count"]), "avg_f1": float(val["avg_f1"])}
            for key, val in data["by_difficulty"].items()
        },
    }


def load_qwen_stats(path: Path) -> dict[str, Any]:
    data = load_json(path)
    by_difficulty = data["by_difficulty"]
    return {
        "avg_f1": float(data["overall"]["avg_f1"]),
        "easy": float(by_difficulty["easy"]["avg_f1"]),
        "medium": float(by_difficulty["medium"]["avg_f1"]),
        "hard": float(by_difficulty["hard"]["avg_f1"]),
    }


def parse_training_log(log_path: Path) -> dict[str, Any]:
    pattern = re.compile(r"^\{'loss':")
    points: list[tuple[float, float]] = []
    eval_loss = None
    train_loss = None
    train_runtime = None

    for raw_line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if pattern.match(line):
            try:
                payload = ast.literal_eval(line)
                points.append((float(payload["epoch"]), float(payload["loss"])))
            except Exception:
                continue
        elif "train_runtime" in line and "train_loss" in line:
            try:
                payload = ast.literal_eval(line)
                train_loss = float(payload["train_loss"])
                train_runtime = str(payload["train_runtime"])
            except Exception:
                pass
        elif "eval_loss" in line and "=" in line:
            try:
                eval_loss = float(line.split("=")[-1].strip())
            except ValueError:
                pass

    return {
        "points": points,
        "eval_loss": eval_loss,
        "train_loss": train_loss,
        "train_runtime": train_runtime,
    }


def make_model_baselines_chart(
    *,
    output_path: Path,
    gpt_summary: dict[str, Any],
    glm_summary: dict[str, Any],
    qwen_summary: dict[str, Any],
) -> None:
    labels = ["Easy", "Medium", "Hard", "Avg"]
    gpt_vals = [
        gpt_summary["by_difficulty"]["easy"]["avg_f1"],
        gpt_summary["by_difficulty"]["medium"]["avg_f1"],
        gpt_summary["by_difficulty"]["hard"]["avg_f1"],
        gpt_summary["avg_f1"],
    ]
    glm_vals = [0.1048, 0.0681, 0.0367, 0.0666]
    qwen_vals = [
        qwen_summary["by_difficulty"]["easy"]["avg_f1"],
        qwen_summary["by_difficulty"]["medium"]["avg_f1"],
        qwen_summary["by_difficulty"]["hard"]["avg_f1"],
        qwen_summary["avg_f1"],
    ]

    x = np.arange(len(labels))
    width = 0.25
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(x - width, gpt_vals, width, label="GPT-5.4", color="#2E86AB")
    ax.bar(x, glm_vals, width, label="GLM-5", color="#E07A5F")
    ax.bar(x + width, qwen_vals, width, label="Qwen3.5-9B", color="#7A9E7E")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, 0.75)
    ax.set_ylabel("F1")
    ax.set_title("Formal 54-case Baseline Comparison")
    ax.legend()
    for bars in ax.containers:
        ax.bar_label(bars, fmt="%.3f", fontsize=9, padding=3)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_pe_progression_chart(
    *,
    output_path: Path,
    pe_summary: list[dict[str, Any]],
) -> None:
    variants = [item["variant"] for item in pe_summary]
    labels = ["baseline", "system", "cot", "fewshot", "postprocess"]
    avg_vals = [item["avg_f1"] for item in pe_summary]
    easy_vals = [item["easy_f1"] for item in pe_summary]
    medium_vals = [item["medium_f1"] for item in pe_summary]
    hard_vals = [item["hard_f1"] for item in pe_summary]

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(labels, avg_vals, marker="o", linewidth=2.5, label="Avg", color="#2E86AB")
    ax.plot(labels, easy_vals, marker="o", linewidth=1.8, label="Easy", color="#55A868")
    ax.plot(labels, medium_vals, marker="o", linewidth=1.8, label="Medium", color="#C44E52")
    ax.plot(labels, hard_vals, marker="o", linewidth=1.8, label="Hard", color="#8172B2")
    ax.set_ylim(0, 0.75)
    ax.set_ylabel("F1")
    ax.set_title("GPT-5.4 Prompt Engineering Progression (54-case)")
    ax.grid(alpha=0.2)
    ax.legend()
    for label, value in zip(labels, avg_vals):
        ax.text(label, value + 0.015, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_bottleneck_heatmap(
    *,
    output_path: Path,
    eval_cases: list[dict[str, Any]],
    gpt_zero_heatmap: dict[str, dict[str, int]],
) -> None:
    difficulties = ["easy", "medium", "hard"]
    failure_types = ["Type A", "Type B", "Type C", "Type D", "Type E"]

    dataset_counts = defaultdict(Counter)
    for case in eval_cases:
        dataset_counts[case["difficulty"]][case["failure_type"]] += 1

    matrix_dataset = np.array(
        [[dataset_counts[diff][ft] for ft in failure_types] for diff in difficulties]
    )
    matrix_zero = np.array(
        [[gpt_zero_heatmap.get(diff, {}).get(ft, 0) for ft in failure_types] for diff in difficulties]
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, matrix, title in [
        (axes[0], matrix_dataset, "Eval Set Distribution"),
        (axes[1], matrix_zero, "GPT-5.4 Zero-F1 Distribution"),
    ]:
        im = ax.imshow(matrix, cmap="YlOrRd")
        ax.set_xticks(np.arange(len(failure_types)), failure_types)
        ax.set_yticks(np.arange(len(difficulties)), [d.title() for d in difficulties])
        ax.set_title(title)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, int(matrix[i, j]), ha="center", va="center", color="black")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    fig.suptitle("Failure Type Coverage vs Actual GPT Failures", fontsize=14, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_rag_retrieval_chart(
    *,
    output_path: Path,
    rag_report: dict[str, Any],
) -> None:
    source_breakdown = rag_report["retrieval"]["source_breakdown"]
    sources = ["bm25", "semantic", "graph", "fused"]
    chunk_vals = [source_breakdown[source]["chunk_symbols"]["avg_recall_at_k"] for source in sources]
    expanded_vals = [source_breakdown[source]["expanded_fqns"]["avg_recall_at_k"] for source in sources]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(sources))
    width = 0.35
    axes[0].bar(x - width / 2, chunk_vals, width, color="#6BAED6", label="Chunk Symbols")
    axes[0].bar(x + width / 2, expanded_vals, width, color="#FD8D3C", label="Expanded FQNs")
    axes[0].set_xticks(x, [s.upper() for s in sources])
    axes[0].set_ylim(0, 0.6)
    axes[0].set_ylabel("Recall@5")
    axes[0].set_title("Retrieval Recall@5 by Source")
    axes[0].legend()
    for bars in axes[0].containers:
        axes[0].bar_label(bars, fmt="%.3f", fontsize=8, padding=3)

    fused_chunk = rag_report["retrieval"]["fused_chunk_symbols"]["difficulty_breakdown"]
    fused_expanded = rag_report["retrieval"]["fused_expanded_fqns"]["difficulty_breakdown"]
    difficulties = ["easy", "medium", "hard"]
    chunk_diff = [fused_chunk[d]["avg_recall_at_k"] for d in difficulties]
    expanded_diff = [fused_expanded[d]["avg_recall_at_k"] for d in difficulties]
    x2 = np.arange(len(difficulties))
    axes[1].bar(x2 - width / 2, chunk_diff, width, color="#74C476", label="Chunk Symbols")
    axes[1].bar(x2 + width / 2, expanded_diff, width, color="#9ECAE1", label="Expanded FQNs")
    axes[1].set_xticks(x2, [d.title() for d in difficulties])
    axes[1].set_ylim(0, 0.75)
    axes[1].set_ylabel("Recall@5")
    axes[1].set_title("Fused Recall@5 by Difficulty")
    axes[1].legend()
    for bars in axes[1].containers:
        axes[1].bar_label(bars, fmt="%.3f", fontsize=8, padding=3)

    fig.suptitle("Google Embedding RAG Retrieval Snapshot", fontsize=14, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_rag_end_to_end_chart(
    *,
    output_path: Path,
    rag_e2e: dict[str, Any],
) -> None:
    summary = rag_e2e["summary"]
    diffs = ["easy", "medium", "hard"]
    no_rag = [summary["by_difficulty"][d]["avg_f1_no_rag"] for d in diffs]
    with_rag = [summary["by_difficulty"][d]["avg_f1_with_rag"] for d in diffs]
    failure_types = ["Type A", "Type B", "Type C", "Type D", "Type E"]
    deltas = [summary["by_failure_type"][ft]["avg_delta"] for ft in failure_types]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    x = np.arange(len(diffs))
    width = 0.35
    axes[0].bar(x - width / 2, no_rag, width, color="#BDBDBD", label="No RAG")
    axes[0].bar(x + width / 2, with_rag, width, color="#2E86AB", label="With RAG")
    axes[0].set_xticks(x, [d.title() for d in diffs])
    axes[0].set_ylim(0, 0.5)
    axes[0].set_ylabel("F1")
    axes[0].set_title("GPT-5.4 End-to-End F1 by Difficulty")
    axes[0].legend()
    for bars in axes[0].containers:
        axes[0].bar_label(bars, fmt="%.3f", fontsize=8, padding=3)

    colors = ["#55A868" if delta >= 0 else "#C44E52" for delta in deltas]
    bars = axes[1].bar(failure_types, deltas, color=colors)
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_ylabel("Avg F1 Delta")
    axes[1].set_title("RAG Gain by Failure Type")
    axes[1].tick_params(axis="x", rotation=15)
    for bar, delta in zip(bars, deltas):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            delta + (0.01 if delta >= 0 else -0.03),
            f"{delta:+.3f}",
            ha="center",
            fontsize=8,
        )

    fig.suptitle("Weighted RAG Helps Hard Cases, Not All Cases", fontsize=14, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_qwen_strategy_chart(
    *,
    output_path: Path,
    qwen_baseline: dict[str, Any],
    qwen_pe: dict[str, Any],
    qwen_rag: dict[str, Any],
    qwen_pe_rag: dict[str, Any],
    qwen_ft: dict[str, Any],
    qwen_pe_ft: dict[str, Any],
    qwen_pe_rag_ft: dict[str, Any],
) -> None:
    labels = ["Baseline", "PE", "RAG", "PE+RAG", "FT", "PE+FT", "All"]
    avg_vals = [
        qwen_baseline["avg_f1"],
        qwen_pe["avg_f1"],
        qwen_rag["avg_f1"],
        qwen_pe_rag["avg_f1"],
        qwen_ft["avg_f1"],
        qwen_pe_ft["avg_f1"],
        qwen_pe_rag_ft["avg_f1"],
    ]
    easy_vals = [
        qwen_baseline["by_difficulty"]["easy"]["avg_f1"],
        qwen_pe["easy"],
        qwen_rag["easy"],
        qwen_pe_rag["easy"],
        qwen_ft["easy"],
        qwen_pe_ft["easy"],
        qwen_pe_rag_ft["easy"],
    ]
    medium_vals = [
        qwen_baseline["by_difficulty"]["medium"]["avg_f1"],
        qwen_pe["medium"],
        qwen_rag["medium"],
        qwen_pe_rag["medium"],
        qwen_ft["medium"],
        qwen_pe_ft["medium"],
        qwen_pe_rag_ft["medium"],
    ]
    hard_vals = [
        qwen_baseline["by_difficulty"]["hard"]["avg_f1"],
        qwen_pe["hard"],
        qwen_rag["hard"],
        qwen_pe_rag["hard"],
        qwen_ft["hard"],
        qwen_pe_ft["hard"],
        qwen_pe_rag_ft["hard"],
    ]

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.8))
    bars = axes[0].bar(
        labels,
        avg_vals,
        color=["#BDBDBD", "#9ECAE1", "#FDD0A2", "#FDAE6B", "#A1D99B", "#74C476", "#31A354"],
    )
    axes[0].set_ylim(0, 0.55)
    axes[0].set_ylabel("Avg F1")
    axes[0].set_title("Qwen Full Ablation Matrix")
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].bar_label(bars, fmt="%.3f", fontsize=8, padding=3)

    x = np.arange(len(labels))
    width = 0.22
    axes[1].bar(x - width, easy_vals, width, label="Easy", color="#4C78A8")
    axes[1].bar(x, medium_vals, width, label="Medium", color="#F58518")
    axes[1].bar(x + width, hard_vals, width, label="Hard", color="#54A24B")
    axes[1].set_xticks(x, labels, rotation=15)
    axes[1].set_ylim(0, 0.65)
    axes[1].set_ylabel("F1")
    axes[1].set_title("Difficulty Breakdown")
    axes[1].legend()

    fig.suptitle("Qwen Family: All Wins, RAG-only Fails", fontsize=14, fontweight="bold")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def make_training_curve_chart(
    *,
    output_path: Path,
    training: dict[str, Any],
) -> None:
    points = training["points"]
    if not points:
        return

    epochs = [epoch for epoch, _ in points]
    losses = [loss for _, loss in points]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(epochs, losses, marker="o", markersize=3, linewidth=1.8, color="#2E86AB")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Training Loss")
    ax.set_title("Qwen LoRA Training Loss Curve")
    ax.grid(alpha=0.2)
    if training["eval_loss"] is not None:
        ax.axhline(training["eval_loss"], color="#C44E52", linestyle="--", label=f"Final eval_loss={training['eval_loss']:.4f}")
        ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate final delivery charts.")
    parser.add_argument("--output-dir", type=Path, default=IMG_DIR)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    args = parser.parse_args()

    eval_cases = load_json(ROOT / "data/eval_cases.json")
    case_map = {case["id"]: case for case in eval_cases}
    fewshot_count = len(load_json(ROOT / "data/fewshot_examples_20.json"))
    finetune_count = load_jsonl_count(ROOT / "data/finetune_dataset_500.jsonl")

    gpt_results = load_json(ROOT / "results/gpt5_eval_results.json")
    glm_scored = load_json(ROOT / "results/glm_eval_scored_20260328.json")
    qwen_recovered = summarize_qwen_recovered(ROOT / "results/qwen_baseline_recovered_summary_20260328.json")
    pe_summary = load_json(ROOT / "results/pe_eval_54_20260328/pe_summary.json")
    rag_google = load_json(ROOT / "results/rag_google_eval_54cases_20260328.json")
    rag_e2e = load_json(ROOT / "results/gpt_rag_e2e_54cases_20260328_summary.json")
    qwen_pe = load_qwen_stats(ROOT / "results/qwen_pe_only_20260328_stats.json")
    qwen_rag = load_qwen_stats(ROOT / "results/qwen_rag_only_google_20260328_stats.json")
    qwen_pe_rag = load_qwen_stats(ROOT / "results/qwen_pe_rag_google_20260328_stats.json")
    qwen_ft = load_qwen_stats(ROOT / "results/qwen_ft_20260327_160136_stats.json")
    qwen_pe_ft = load_qwen_stats(ROOT / "results/qwen_pe_ft_20260327_162308_stats.json")
    qwen_pe_rag_ft = load_qwen_stats(ROOT / "results/qwen_pe_rag_ft_google_20260328_stats.json")
    training = parse_training_log(ROOT / "logs/train_20260327_143745.log")

    gpt_summary = summarize_baseline_results(gpt_results, case_map=case_map)
    snapshot = {
        "dataset": {
            "eval_cases": len(eval_cases),
            "fewshot_examples": fewshot_count,
            "finetune_records": finetune_count,
            "difficulty_distribution": dict(Counter(case["difficulty"] for case in eval_cases)),
            "failure_type_distribution": dict(Counter(case["failure_type"] for case in eval_cases)),
        },
        "baseline_models": {
            "gpt5": gpt_summary,
            "glm5": glm_scored["summary"],
            "qwen_recovered": qwen_recovered,
        },
        "pe_summary": pe_summary,
        "rag_retrieval": rag_google["retrieval"],
        "rag_end_to_end": rag_e2e["summary"],
        "qwen_strategies": {
            "pe_only": qwen_pe,
            "rag_only": qwen_rag,
            "pe_rag": qwen_pe_rag,
            "ft_only": qwen_ft,
            "pe_ft": qwen_pe_ft,
            "pe_rag_ft": qwen_pe_rag_ft,
        },
        "training": {
            "point_count": len(training["points"]),
            "final_train_loss": training["train_loss"],
            "final_eval_loss": training["eval_loss"],
            "train_runtime": training["train_runtime"],
        },
    }
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    make_model_baselines_chart(
        output_path=args.output_dir / "01_model_baselines_20260328.png",
        gpt_summary=gpt_summary,
        glm_summary=glm_scored["summary"],
        qwen_summary=qwen_recovered,
    )
    make_pe_progression_chart(
        output_path=args.output_dir / "02_pe_progression_20260328.png",
        pe_summary=pe_summary,
    )
    make_bottleneck_heatmap(
        output_path=args.output_dir / "03_bottleneck_heatmap_20260328.png",
        eval_cases=eval_cases,
        gpt_zero_heatmap=gpt_summary["zero_heatmap"],
    )
    make_rag_retrieval_chart(
        output_path=args.output_dir / "04_rag_retrieval_20260328.png",
        rag_report=rag_google,
    )
    make_rag_end_to_end_chart(
        output_path=args.output_dir / "05_rag_end_to_end_20260328.png",
        rag_e2e=rag_e2e,
    )
    make_qwen_strategy_chart(
        output_path=args.output_dir / "06_qwen_strategies_20260328.png",
        qwen_baseline=qwen_recovered,
        qwen_pe=qwen_pe,
        qwen_rag=qwen_rag,
        qwen_pe_rag=qwen_pe_rag,
        qwen_ft=qwen_ft,
        qwen_pe_ft=qwen_pe_ft,
        qwen_pe_rag_ft=qwen_pe_rag_ft,
    )
    make_training_curve_chart(
        output_path=args.output_dir / "07_training_curve_20260328.png",
        training=training,
    )

    print(f"Saved charts to {args.output_dir}")
    print(f"Saved metrics snapshot to {args.snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
