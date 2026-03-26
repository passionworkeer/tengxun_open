#!/usr/bin/env python3
"""
从评测结果生成微调训练数据

用法:
    python scripts/generate_finetune_data.py --input results/gpt5_eval_results.json --output data/finetune_from_gpt5.jsonl
"""

import json
import argparse
from pathlib import Path
from typing import Any


def convert_to_finetune_format(
    results: list[dict[str, Any]],
    include_reasoning: bool = True,
) -> list[dict[str, Any]]:
    """
    将评测结果转换为微调数据格式

    格式: messages格式（用于qwen/lora训练）
    """
    samples = []

    SYSTEM_PROMPT = """\
You are a senior Python static analysis expert working on cross-file dependency resolution.
Resolve the final dependency structure precisely against the provided Celery source context.
Output only a JSON object in this shape:
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
Do not include explanations, markdown, XML tags, or any extra prose.
Always respond in English, regardless of the question language."""

    for r in results:
        # 构建user message
        question = r.get("question", "")
        entry_symbol = ""
        entry_file = ""

        # 构建assistant回复（从raw_output解析）
        raw = r.get("raw_output", "")
        if not raw or r.get("prediction") is None:
            continue  # 跳过失败的case

        try:
            # 尝试解析raw_output
            pred = r.get("prediction", {})
            if not pred:
                continue

            assistant_content = json.dumps({"ground_truth": pred}, ensure_ascii=False)
        except:
            continue

        sample = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
                {"role": "assistant", "content": assistant_content},
            ]
        }
        samples.append(sample)

    return samples


def generate_high_quality_samples(
    results: list[dict[str, Any]],
    min_f1: float = 0.5,
) -> list[dict[str, Any]]:
    """
    只选择高质量样本用于微调（F1 >= min_f1）
    """
    high_quality = [r for r in results if r.get("f1", 0) >= min_f1]
    return convert_to_finetune_format(high_quality)


def generate_all_samples(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    生成所有样本（不区分成功失败）
    """
    return convert_to_finetune_format(results, include_reasoning=False)


def main():
    parser = argparse.ArgumentParser(
        description="Generate fine-tuning data from evaluation results"
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="Input results JSON file"
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL file")
    parser.add_argument(
        "--min-f1", type=float, default=0.5, help="Minimum F1 threshold (default: 0.5)"
    )
    args = parser.parse_args()

    # Load results
    with open(args.input) as f:
        results = json.load(f)

    print(f"Loaded {len(results)} results from {args.input}")

    # Generate samples
    samples = generate_high_quality_samples(results, min_f1=args.min_f1)

    print(f"Generated {len(samples)} high-quality samples (F1 >= {args.min_f1})")

    # Save as JSONL
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"Saved to {args.output}")

    # Also print stats
    f1_scores = [r.get("f1", 0) for r in results]
    print(f"\nSummary:")
    print(f"  Total results: {len(results)}")
    print(f"  Samples with F1 >= {args.min_f1}: {len(samples)}")
    print(f"  Average F1: {sum(f1_scores) / len(f1_scores):.4f}")


if __name__ == "__main__":
    main()
