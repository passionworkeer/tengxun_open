"""
PE+FT 评测脚本（提示词优化 + 微调后模型）

用法:
    python run_pe_ft_eval.py
    python run_pe_ft_eval.py --max-cases 3  # 调试用
"""

from __future__ import annotations

import json
import re
import time
import argparse
from pathlib import Path
from typing import Any
from datetime import datetime

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics
from pe.prompt_templates_v2 import (
    SYSTEM_PROMPT,
    COT_TEMPLATE,
    build_prompt_bundle,
    format_few_shot_example,
)


BASE_MODEL = "Qwen/Qwen3.5-9B"
ADAPTER_PATH = "LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745"
DATA_PATH = Path("data/eval_cases.json")
MAX_NEW_TOKENS = 500


def load_model(base_model_path: str, adapter_path: str):
    print(f"加载基础模型: {base_model_path}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("加载基础模型权重 (fp16)...")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"加载LoRA adapter: {adapter_path}")
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, tokenizer


def build_pe_messages(case: EvalCase) -> list[dict[str, str]]:
    """使用 prompt_templates_v2 构建 PE 优化后的 messages
    合并 System Prompt + CoT 为单条 system 消息（Qwen 不支持连续 system 消息）
    然后添加动态选择的 few-shot 示例
    """
    bundle = build_prompt_bundle(
        question=case.question,
        context="",
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        max_examples=6,
    )
    # 合并 system prompt 和 CoT 为一条 system 消息
    combined_system = bundle.system_prompt.strip()
    if bundle.cot_template.strip():
        combined_system += "\n\n" + bundle.cot_template.strip()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": combined_system},
    ]
    # 添加 few-shot 示例
    for example in bundle.few_shot_examples:
        messages.append({"role": "user", "content": format_few_shot_example(example)})
    # 添加实际问题
    messages.append({"role": "user", "content": bundle.user_prompt.strip()})
    return messages


def generate_response(model, tokenizer, messages: list[dict[str, str]]) -> str:
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True)


def parse_response(raw: str) -> dict[str, list[str]] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            data = json.loads(text)
        gt = data.get("ground_truth", {})

        def normalize_items(items: Any) -> list[str]:
            if not isinstance(items, list):
                return []
            result: list[str] = []
            for item in items:
                if isinstance(item, str):
                    value = item.strip()
                    if value:
                        result.append(value)
            return result

        return {
            "direct_deps": normalize_items(gt.get("direct_deps", [])),
            "indirect_deps": normalize_items(gt.get("indirect_deps", [])),
            "implicit_deps": normalize_items(gt.get("implicit_deps", [])),
        }
    except (json.JSONDecodeError, AttributeError, KeyError):
        return None


def compute_f1(pred: dict[str, list[str]] | None, case: EvalCase) -> float:
    gt_all = set(
        list(case.direct_gold_fqns)
        + list(case.indirect_gold_fqns)
        + list(case.implicit_gold_fqns)
    )
    if not pred:
        return 0.0
    pred_all = set(
        pred.get("direct_deps", [])
        + pred.get("indirect_deps", [])
        + pred.get("implicit_deps", [])
    )
    metrics = compute_set_metrics(list(gt_all), list(pred_all))
    return metrics.f1


def analyze_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_diff: dict[str, list[float]] = {}
    for r in results:
        by_diff.setdefault(r["difficulty"], []).append(r["f1"])

    all_f1 = [r["f1"] for r in results]
    stats: dict[str, Any] = {
        "total_cases": len(results),
        "by_difficulty": {},
        "overall": {
            "avg_f1": round(sum(all_f1) / len(all_f1), 4),
            "min_f1": round(min(all_f1), 4),
            "max_f1": round(max(all_f1), 4),
        },
    }
    for diff, scores in sorted(by_diff.items()):
        stats["by_difficulty"][diff] = {
            "count": len(scores),
            "avg_f1": round(sum(scores) / len(scores), 4),
            "min_f1": round(min(scores), 4),
            "max_f1": round(max(scores), 4),
        }
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="PE+FT evaluation")
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--adapter-path", default=ADAPTER_PATH)
    parser.add_argument("--cases", type=Path, default=DATA_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"results/qwen_pe_ft_{ts}.json")

    model, tokenizer = load_model(args.base_model, args.adapter_path)

    cases = load_eval_cases(args.cases)
    if args.max_cases:
        cases = cases[: args.max_cases]
    print(f"加载 {len(cases)} 条评测用例\n")

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] {case.case_id} ...", end=" ", flush=True)

        messages = build_pe_messages(case)
        raw_output = ""
        prediction = None

        for attempt in range(3):
            try:
                raw_output = generate_response(model, tokenizer, messages)
                prediction = parse_response(raw_output)
                break
            except Exception as e:
                print(f"  retry {attempt + 1}: {e}", end=" ", flush=True)
                time.sleep(5)
                raw_output = str(e)

        f1 = compute_f1(prediction, case)

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "failure_type": case.failure_type,
            "question": case.question,
            "ground_truth": {
                "direct_deps": list(case.direct_gold_fqns),
                "indirect_deps": list(case.indirect_gold_fqns),
                "implicit_deps": list(case.implicit_gold_fqns),
            },
            "model_output": raw_output,
            "extracted_prediction": prediction,
            "f1": round(f1, 4),
        }
        results.append(result)
        print(f"F1={f1:.4f}", flush=True)

        # 实时保存
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # 统计
    stats = analyze_results(results)
    stats_path = args.output.parent / f"{args.output.stem}_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 打印结果
    print("\n" + "=" * 50)
    print("PE+FT 评测统计")
    print("=" * 50)
    print(f"总用例数: {stats['total_cases']}")
    print(f"总体平均F1: {stats['overall']['avg_f1']:.4f}")
    print(
        f"F1范围: [{stats['overall']['min_f1']:.4f}, {stats['overall']['max_f1']:.4f}]"
    )
    print("\n按难度统计:")
    for diff, ds in stats["by_difficulty"].items():
        print(
            f"  {diff}: count={ds['count']}  avg_f1={ds['avg_f1']:.4f}  "
            f"[{ds['min_f1']:.4f}, {ds['max_f1']:.4f}]"
        )
    print(f"\n结果文件: {args.output}")
    print(f"统计文件: {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
