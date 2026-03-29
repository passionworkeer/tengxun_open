"""
微调后模型评测脚本
用法: python run_ft_eval.py --cases data/eval_cases.json --output results/qwen_ft_$(date +%Y%m%d_%H%M%S).json

参数:
    --cases: 评测数据集路径（默认: data/eval_cases.json）
    --adapter-path: LoRA adapter路径（默认读取 QWEN_LORA_ADAPTER_PATH，否则回退到历史正式路径）
    --base-model: 基础模型路径（默认: Qwen/Qwen3.5-9B）
    --output: 输出结果路径（默认: results/qwen_ft_TIMESTAMP.json）
    --max-cases: 限制评测案例数量（用于测试）
"""

from __future__ import annotations

import json
import argparse
import os
import re
import time
from pathlib import Path
from typing import Any
from datetime import datetime

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics


DEFAULT_ADAPTER_PATH = os.environ.get(
    "QWEN_LORA_ADAPTER_PATH",
    "LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745",
)


def build_prompt_v2(case: EvalCase, context: str = "") -> str:
    """
    构建发送给模型的提示词
    包含问题、入口符号、文件和可选的上下文信息
    """
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    if context:
        parts.append(f"Context:\n{context.strip()}")
    parts.append(
        "\nIMPORTANT: Return ONLY a valid JSON object, no other text.\n"
        'Format: {"ground_truth": {"direct_deps": ["module.path"], "indirect_deps": [], "implicit_deps": []}}\n'
        'Example: {"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}'
    )
    return "\n\n".join(parts)


def parse_response(text: str) -> dict[str, list[str]] | None:
    """
    解析模型输出的JSON响应
    尝试从模型输出中提取ground_truth字段
    包含错误处理和正则匹配
    """
    try:
        text = text.strip()

        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
        else:
            data = json.loads(text.strip())
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


def compute_f1(pred: dict[str, list[str]], gt: dict[str, list[str]]) -> float:
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
    metrics = compute_set_metrics(list(all_gt), list(all_pred))
    return metrics.f1


def load_model(base_model_path: str, adapter_path: str):
    """加载基础模型和LoRA adapter"""
    print(f"加载基础模型: {base_model_path}")
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)

    # 设置pad_token
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("加载基础模型权重...")
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


def generate_response(model, tokenizer, prompt: str, max_new_tokens: int = 500) -> str:
    """使用模型生成响应"""
    system_prompt = "You are a JSON-only response bot. You must ONLY output valid JSON objects, no explanations, no markdown, no extra text. Your response must be parseable by json.loads()."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    # 应用聊天模板，禁用思考模式
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )

    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.0,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    # 只获取生成的新token
    generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
    response = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    return response


def run_ft_eval(
    cases: list[EvalCase],
    base_model_path: str = "Qwen/Qwen3.5-9B",
    adapter_path: str = DEFAULT_ADAPTER_PATH,
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    """运行微调模型评测"""

    # 加载模型
    model, tokenizer = load_model(base_model_path, adapter_path)

    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case, context="")
        prediction = None
        raw_output = None

        for attempt in range(3):
            try:
                raw_output = generate_response(model, tokenizer, prompt)
                prediction = parse_response(raw_output)
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                time.sleep(5)
                raw_output = str(e)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) if case.direct_gold_fqns else [],
            "indirect_deps": list(case.indirect_gold_fqns)
            if case.indirect_gold_fqns
            else [],
            "implicit_deps": list(case.implicit_gold_fqns)
            if case.implicit_gold_fqns
            else [],
        }

        f1 = compute_f1(prediction or {}, gt_dict) if prediction else 0.0

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "question": case.question,
            "ground_truth": gt_dict,
            "model_output": raw_output,
            "extracted_prediction": prediction,
            "f1": round(f1, 4),
        }
        results.append(result)
        print(f"  F1: {f1:.4f}", flush=True)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nAll {len(results)} cases completed. Results saved to {output_path}")
    return results


def analyze_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """分析评测结果，计算按难度的F1均值"""
    stats = {
        "total_cases": len(results),
        "by_difficulty": {},
        "overall": {
            "avg_f1": 0.0,
            "min_f1": 1.0,
            "max_f1": 0.0,
        },
    }

    # 按难度分组
    by_difficulty = {}
    for result in results:
        difficulty = result["difficulty"]
        if difficulty not in by_difficulty:
            by_difficulty[difficulty] = []
        by_difficulty[difficulty].append(result["f1"])

    # 计算每个难度的统计
    for difficulty, f1_scores in by_difficulty.items():
        avg_f1 = sum(f1_scores) / len(f1_scores)
        stats["by_difficulty"][difficulty] = {
            "count": len(f1_scores),
            "avg_f1": round(avg_f1, 4),
            "min_f1": round(min(f1_scores), 4),
            "max_f1": round(max(f1_scores), 4),
        }

    # 计算总体统计
    all_f1 = [r["f1"] for r in results]
    stats["overall"]["avg_f1"] = round(sum(all_f1) / len(all_f1), 4)
    stats["overall"]["min_f1"] = round(min(all_f1), 4)
    stats["overall"]["max_f1"] = round(max(all_f1), 4)

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run fine-tuned Qwen3.5 evaluation on Celery dependency analysis."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to evaluation dataset.",
    )
    parser.add_argument(
        "--adapter-path",
        type=str,
        default=DEFAULT_ADAPTER_PATH,
        help="Path to LoRA adapter.",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="Qwen/Qwen3.5-9B",
        help="Base model path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for results.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit number of cases (for testing).",
    )
    args = parser.parse_args()

    # 如果没有指定输出路径，生成带时间戳的路径
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"results/qwen_ft_{timestamp}.json")

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    results = run_ft_eval(
        cases=cases,
        base_model_path=args.base_model,
        adapter_path=args.adapter_path,
        output_path=args.output,
        max_cases=args.max_cases,
    )

    # 分析结果
    stats = analyze_results(results)

    # 保存统计结果
    stats_path = args.output.parent / f"{args.output.stem}_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 打印统计结果
    print("\n" + "=" * 50)
    print("评测统计结果")
    print("=" * 50)
    print(f"总用例数: {stats['total_cases']}")
    print(f"总体平均F1: {stats['overall']['avg_f1']:.4f}")
    print(
        f"F1范围: [{stats['overall']['min_f1']:.4f}, {stats['overall']['max_f1']:.4f}]"
    )

    print("\n按难度统计:")
    for difficulty, diff_stats in stats["by_difficulty"].items():
        print(f"  {difficulty}:")
        print(f"    用例数: {diff_stats['count']}")
        print(f"    平均F1: {diff_stats['avg_f1']:.4f}")
        print(f"    F1范围: [{diff_stats['min_f1']:.4f}, {diff_stats['max_f1']:.4f}]")

    print(f"\n结果已保存到: {args.output}")
    print(f"统计已保存到: {stats_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
