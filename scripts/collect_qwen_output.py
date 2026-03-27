#!/usr/bin/env python3
"""Qwen3.5 完整输出收集脚本"""

import json
import argparse
from pathlib import Path
from openai import OpenAI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=Path("data/eval_cases.json"))
    parser.add_argument("--model", type=str, default="Qwen/Qwen3.5-9B")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000/v1")
    parser.add_argument(
        "--output", type=Path, default=Path("results/qwen3_full_output.json")
    )
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    # 加载评测集
    with open(args.cases, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"加载了 {len(cases)} 条评测用例")

    if args.max_cases:
        cases = cases[: args.max_cases]
        print(f"限制为前 {args.max_cases} 条")

    client = OpenAI(base_url=args.base_url, api_key="EMPTY")

    results = []

    for i, case in enumerate(cases):
        case_id = case.get("case_id", f"case_{i}")
        question = case.get("question", "")
        ground_truth = case.get("ground_truth", {})

        print(f"[{i + 1}/{len(cases)}] {case_id}...", end=" ", flush=True)

        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=[{"role": "user", "content": question}],
                stream=False,
                timeout=300,
            )
            raw_output = (
                response.choices[0].message.content
                if response.choices[0].message.content
                else ""
            )
            print("OK")
        except Exception as e:
            raw_output = f"ERROR: {str(e)}"
            print(f"ERROR: {e}")

        results.append(
            {
                "case_id": case_id,
                "difficulty": case.get("difficulty", ""),
                "category": case.get("category", ""),
                "question": question,
                "ground_truth": ground_truth,
                "model_output": raw_output,
            }
        )

        # 每条都保存
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n完成！共 {len(results)} 条，已保存到 {args.output}")


if __name__ == "__main__":
    main()
