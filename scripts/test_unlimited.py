#!/usr/bin/env python3
"""Qwen 完整输出收集 - 无 token 限制"""

import json
from pathlib import Path
from openai import OpenAI

# 配置
CASES_FILE = "data/eval_cases.json"
OUTPUT_FILE = "results/qwen3_unlimited_test.json"
MODEL = "Qwen/Qwen3.5-9B"
BASE_URL = "http://localhost:8000/v1"
MAX_CASES = 2  # 测试 2 条

# 加载评测集
with open(CASES_FILE, "r", encoding="utf-8") as f:
    cases = json.load(f)[:MAX_CASES]

print(f"加载 {len(cases)} 条用例")

client = OpenAI(base_url=BASE_URL, api_key="EMPTY")
results = []

for i, case in enumerate(cases):
    case_id = case.get("case_id", f"case_{i}")
    question = case.get("question", "")
    ground_truth = case.get("ground_truth", {})

    print(f"\n[{i + 1}/{len(cases)}] {case_id}")
    print(f"问题: {question[:80]}...")

    try:
        # 不设置 max_tokens，让模型完整输出
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": question}],
            stream=False,
            timeout=600,
        )
        raw_output = (
            response.choices[0].message.content
            if response.choices[0].message.content
            else ""
        )
        print(f"输出长度: {len(raw_output)} 字符")
    except Exception as e:
        raw_output = f"ERROR: {str(e)}"
        print(f"错误: {e}")

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

# 保存
Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n完成！保存到 {OUTPUT_FILE}")
