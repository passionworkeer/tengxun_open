#!/usr/bin/env python3
"""
从正式训练日志中提取结构化训练证据。
"""

from __future__ import annotations

import argparse
import ast
import json
import statistics
from pathlib import Path


def parse_log(log_path: Path) -> dict:
    train_points: list[dict[str, float]] = []
    final_train_loss = None
    final_eval_loss = None
    train_runtime_seconds = None
    train_runtime_hms = None
    eval_runtime_hms = None

    for raw_line in log_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("{'loss':"):
            payload = ast.literal_eval(line)
            train_points.append(
                {
                    "loss": float(payload["loss"]),
                    "learning_rate": float(payload["learning_rate"]),
                    "epoch": float(payload["epoch"]),
                }
            )
        elif line.startswith("{'train_runtime':"):
            payload = ast.literal_eval(line)
            train_runtime_seconds = float(payload["train_runtime"])
            final_train_loss = float(payload["train_loss"])
        elif line.startswith("train_runtime"):
            train_runtime_hms = line.split("=", 1)[-1].strip()
        elif line.startswith("eval_loss"):
            final_eval_loss = float(line.split("=", 1)[-1].strip())
        elif line.startswith("eval_runtime"):
            eval_runtime_hms = line.split("=", 1)[-1].strip()

    if not train_points:
        raise SystemExit(f"日志中未找到 step-level train loss: {log_path}")

    losses = [point["loss"] for point in train_points]
    decreasing_steps = 0
    for prev, curr in zip(losses, losses[1:]):
        if curr <= prev:
            decreasing_steps += 1

    return {
        "log_path": str(log_path),
        "train_loss_points": len(train_points),
        "first_train_loss": round(losses[0], 4),
        "last_logged_train_loss": round(losses[-1], 4),
        "min_logged_train_loss": round(min(losses), 4),
        "max_logged_train_loss": round(max(losses), 4),
        "median_logged_train_loss": round(statistics.median(losses), 4),
        "mean_logged_train_loss": round(statistics.mean(losses), 4),
        "loss_drop_first_to_last_logged": round(losses[-1] - losses[0], 4),
        "decreasing_adjacent_steps": decreasing_steps,
        "total_adjacent_steps": max(len(losses) - 1, 0),
        "final_train_loss": round(final_train_loss, 4) if final_train_loss is not None else None,
        "final_eval_loss": round(final_eval_loss, 4) if final_eval_loss is not None else None,
        "train_runtime_seconds": train_runtime_seconds,
        "train_runtime_hms": train_runtime_hms,
        "eval_runtime_hms": eval_runtime_hms,
        "step_level_eval_curve_present": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze training log.")
    parser.add_argument(
        "--log",
        type=Path,
        default=Path("logs/train_20260327_143745.log"),
        help="Training log path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/training_log_summary_20260329.json"),
        help="JSON output path.",
    )
    args = parser.parse_args()

    summary = parse_log(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
