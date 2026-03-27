#!/usr/bin/env python3
"""Qwen 完整输出收集 - 推理模型优化版"""

import json
import re
from pathlib import Path
from openai import OpenAI

# 配置
CASES_FILE = "data/eval_cases.json"
OUTPUT_FILE = "results/qwen3_reasoning_v2.json"
MODEL = "Qwen/Qwen3.5-9B"
BASE_URL = "http://localhost:8000/v1"

# 加载评测集
with open(CASES_FILE, "r", encoding="utf-8") as f:
    cases = json.load(f)

print(f"加载 {len(cases)} 条用例")

# 系统提示 - 针对推理模型优化
SYSTEM_PROMPT = """你是一个代码依赖分析助手。你的任务是分析代码中的依赖关系。

重要规则：
1. 你可以先进行内部思考推理
2. 但你的最终输出必须且只能是一个合法的 JSON 对象
3. 不要包含任何 Markdown 标记（如 ```json）或解释性文字
4. JSON 格式: {"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}
5. 所有依赖项必须是完整的模块路径格式，如 "celery.app.base.Celery"

示例输出:
{"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}"""

client = OpenAI(base_url=BASE_URL, api_key="EMPTY")
results = []

for i, case in enumerate(cases):
    case_id = case.get("case_id", f"case_{i}")
    question = case.get("question", "")
    ground_truth = case.get("ground_truth", {})

    print(f"[{i + 1}/{len(cases)}] {case_id}...", end=" ", flush=True)

    try:
        # 不设置 max_tokens，让模型完整输出
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
            stream=False,
            timeout=600,
            temperature=0.1,
        )
        raw_output = (
            response.choices[0].message.content
            if response.choices[0].message.content
            else ""
        )

        # 尝试从输出中提取 JSON
        extracted_json = None
        # 方法1: 找最后一个 {...} 块
        matches = re.findall(
            r'\{[^{}]*"ground_truth"[^{}]*\{[^}]*\}[^{}]*\}', raw_output, re.DOTALL
        )
        if matches:
            try:
                extracted_json = json.loads(matches[-1])
            except:
                pass

        # 方法2: 如果方法1失败，找任何 {...}
        if not extracted_json:
            matches = re.findall(r"\{.*?\}", raw_output, re.DOTALL)
            for match in reversed(matches):
                try:
                    data = json.loads(match)
                    if "ground_truth" in data or "direct_deps" in data:
                        extracted_json = data
                        break
                except:
                    continue

        print(
            f"OK (输出: {len(raw_output)} 字符, 提取JSON: {'是' if extracted_json else '否'})"
        )

    except Exception as e:
        raw_output = f"ERROR: {str(e)}"
        extracted_json = None
        print(f"ERROR: {e}")

    results.append(
        {
            "case_id": case_id,
            "difficulty": case.get("difficulty", ""),
            "category": case.get("category", ""),
            "question": question,
            "ground_truth": ground_truth,
            "model_output": raw_output,
            "extracted_prediction": extracted_json,
        }
    )

    # 每 10 条保存一次
    if (i + 1) % 10 == 0:
        Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"  已保存中间结果 ({i + 1}/{len(cases)})")

# 最终保存
Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n完成！共 {len(results)} 条，保存到 {OUTPUT_FILE}")
