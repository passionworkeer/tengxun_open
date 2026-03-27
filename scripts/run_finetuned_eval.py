#!/usr/bin/env python3
"""
使用微调后的模型跑评测

用法:
    python scripts/run_finetuned_eval.py \
        --base-model Qwen/Qwen2.5-7B-Instruct \
        --lora-path artifacts/lora/qwen3-finetuned/lora_adapter \
        --output results/finetuned_eval_results.json
"""

import json
import argparse
from pathlib import Path
from typing import Any
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics


def build_prompt_v2(case: EvalCase) -> str:
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'
    )
    return "\n\n".join(parts)


def parse_response(text: str) -> dict[str, list[str]] | None:
    try:
        text = text.strip()
        import re

        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
        else:
            data = json.loads(text.strip())
        gt = data.get("ground_truth", {})
        return {
            "direct_deps": gt.get("direct_deps", []),
            "indirect_deps": gt.get("indirect_deps", []),
            "implicit_deps": gt.get("implicit_deps", []),
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


def load_model_and_tokenizer(base_model: str, lora_path: str | None = None):
    """加载基础模型和LoRA权重"""
    print(f"Loading base model: {base_model}")

    # 量化配置
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        base_model, trust_remote_code=True, padding_side="right"
    )
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        trust_remote_code=True,
        quantization_config=bnb_config,
        device_map="auto",
    )

    if lora_path:
        print(f"Loading LoRA adapter: {lora_path}")
        model = PeftModel.from_pretrained(model, lora_path)
        model = model.merge_and_unload()

    return model, tokenizer


def run_inference(
    model,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 512,
) -> str:
    """运行推理"""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
        )

    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # 提取assistant回复
    if "<|im_start|>assistant" in response:
        response = response.split("<|im_start|>assistant")[-1]
    if "<|im_end|>" in response:
        response = response.split("<|im_end|>")[0]

    return response.strip()


def run_finetuned_eval(
    cases: list[EvalCase],
    model,
    tokenizer,
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case)
        raw_output = None
        prediction = None

        for attempt in range(3):
            try:
                raw_output = run_inference(model, tokenizer, prompt)
                prediction = parse_response(raw_output)
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                import time

                time.sleep(5)

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
            "model": "finetuned-qwen",
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
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


def main():
    parser = argparse.ArgumentParser(description="Run evaluation with fine-tuned model")
    parser.add_argument(
        "--cases", type=Path, default=Path("data/eval_cases.json")
    )
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--lora-path", type=str, default=None, help="Path to LoRA adapter (optional)"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/finetuned_eval_results.json")
    )
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    model, tokenizer = load_model_and_tokenizer(args.base_model, args.lora_path)

    run_finetuned_eval(
        cases=cases,
        model=model,
        tokenizer=tokenizer,
        output_path=args.output,
        max_cases=args.max_cases,
    )


if __name__ == "__main__":
    main()
