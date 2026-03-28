"""
PE+RAG+FT 评测脚本（使用vLLM加速）

用法:
    python run_pe_rag_ft_vllm.py --cases data/eval_cases.json --output results/qwen_pe_rag_ft_google_20260328.json
    python run_pe_rag_ft_vllm.py --max-cases 3  # 调试用
"""

from __future__ import annotations

import json
import re
import time
import argparse
from pathlib import Path
from typing import Any
from datetime import datetime

from vllm import LLM, SamplingParams
from vllm.lora.request import LoRARequest
from transformers import AutoTokenizer

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics
from pe.prompt_templates_v2 import (
    build_prompt_bundle,
    format_few_shot_example,
)
from rag.rrf_retriever import build_retriever


BASE_MODEL = "Qwen/Qwen3.5-9B"
ADAPTER_PATH = "LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745"
DATA_PATH = Path("data/eval_cases.json")
REPO_ROOT = Path("external/celery")
MAX_NEW_TOKENS = 500
RAG_TOP_K = 5


def init_rag(repo_root: Path):
    """初始化RAG检索器"""
    if not repo_root.exists():
        print(f"RAG不可用: 源码目录不存在 {repo_root}")
        return None
    try:
        print(f"构建RAG索引: {repo_root}")
        retriever = build_retriever(repo_root)
        print(f"RAG索引构建完成，共 {len(retriever.chunks)} 个代码块")
        return retriever
    except Exception as e:
        print(f"RAG初始化失败: {e}")
        return None


def retrieve_context(
    retriever,
    question: str,
    entry_symbol: str = "",
    entry_file: str = "",
    top_k: int = RAG_TOP_K,
) -> str:
    """使用RAG检索相关上下文"""
    if retriever is None:
        return ""
    try:
        context = retriever.build_context(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
        )
        return context
    except Exception as e:
        print(f"RAG检索失败: {e}")
        return ""


def build_pe_rag_messages(case: EvalCase, context: str) -> list[dict[str, str]]:
    """使用 prompt_templates_v2 构建 PE+RAG 优化后的 messages"""
    bundle = build_prompt_bundle(
        question=case.question,
        context=context,
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
    for result in results:
        by_diff.setdefault(result["difficulty"], []).append(result["f1"])

    all_f1 = [r["f1"] for r in results]
    stats: dict[str, Any] = {
        "total_cases": len(results),
        "by_difficulty": {},
        "overall": {
            "avg_f1": round(sum(all_f1) / len(all_f1), 4) if all_f1 else 0.0,
            "min_f1": round(min(all_f1), 4) if all_f1 else 0.0,
            "max_f1": round(max(all_f1), 4) if all_f1 else 0.0,
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
    parser = argparse.ArgumentParser(description="Run PE+RAG+FT evaluation with vLLM.")
    parser.add_argument("--cases", type=Path, default=DATA_PATH)
    parser.add_argument("--base-model", type=str, default=BASE_MODEL)
    parser.add_argument("--adapter-path", type=str, default=ADAPTER_PATH)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--resume", action="store_true", help="Resume from existing output file"
    )
    args = parser.parse_args()

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"results/qwen_pe_rag_ft_vllm_{ts}.json")

    # 加载评测用例
    cases = load_eval_cases(args.cases)
    if args.max_cases:
        cases = cases[: args.max_cases]

    # 初始化 RAG
    retriever = init_rag(args.repo_root)

    # 加载tokenizer
    print(f"加载tokenizer: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    # 初始化vLLM引擎
    print(f"初始化vLLM引擎...")
    llm = LLM(
        model=args.base_model,
        trust_remote_code=True,
        dtype="float16",
        max_model_len=2048,
        enable_lora=True,
        gpu_memory_utilization=0.9,
    )

    # 配置LoRA请求
    lora_request = LoRARequest("finetune", 1, args.adapter_path)

    # 配置采样参数
    sampling_params = SamplingParams(
        temperature=0.1,
        top_p=1.0,
        max_tokens=MAX_NEW_TOKENS,
        skip_special_tokens=True,
    )

    print(f"加载 {len(cases)} 条评测用例，模式=pe_rag_ft\n")

    results: list[dict[str, Any]] = []
    processed_case_ids: set[str] = set()

    # 加载已有结果（断点续传）
    if args.resume and args.output.exists():
        try:
            existing_results = json.loads(args.output.read_text(encoding="utf-8"))
            results = existing_results
            processed_case_ids = {r["case_id"] for r in results}
            print(f"断点续传：已加载 {len(results)} 个已有结果")
        except Exception as exc:
            print(f"警告：无法加载已有结果文件：{exc}")

    for i, case in enumerate(cases):
        # 跳过已处理的用例
        if case.case_id in processed_case_ids:
            print(f"[{i + 1}/{len(cases)}] {case.case_id} ... 已跳过（已完成）")
            continue

        print(f"[{i + 1}/{len(cases)}] {case.case_id} ...", end=" ", flush=True)

        # RAG 检索上下文
        context = retrieve_context(
            retriever,
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=RAG_TOP_K,
        )

        # 构建 PE+RAG 优化后的 messages
        messages = build_pe_rag_messages(case, context)

        # 应用聊天模板
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )

        # 使用 vLLM 生成
        raw_output = ""
        prediction = None
        for attempt in range(3):
            try:
                outputs = llm.generate(
                    [text], sampling_params, lora_request=lora_request
                )
                if outputs and outputs[0].outputs:
                    raw_output = outputs[0].outputs[0].text
                prediction = parse_response(raw_output)
                break
            except Exception as exc:
                print(f"retry {attempt + 1}: {exc}", end=" ", flush=True)
                raw_output = str(exc)
                time.sleep(5)

        f1 = compute_f1(prediction, case)
        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "failure_type": case.failure_type,
            "question": case.question,
            "entry_symbol": case.entry_symbol,
            "entry_file": case.entry_file,
            "mode": "pe_rag_ft",
            "ground_truth": {
                "direct_deps": list(case.direct_gold_fqns),
                "indirect_deps": list(case.indirect_gold_fqns),
                "implicit_deps": list(case.implicit_gold_fqns),
            },
            "rag_context_length": len(context),
            "model_output": raw_output,
            "extracted_prediction": prediction,
            "f1": round(f1, 4),
        }
        if context:
            result["context_preview"] = (
                context[:200] + "..." if len(context) > 200 else context
            )
        results.append(result)
        print(f"F1={f1:.4f}", flush=True)

        # 保存中间结果
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # 保存统计结果
    stats = analyze_results(results)
    stats_path = args.output.with_name(args.output.stem + "_stats.json")
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{'=' * 50}")
    print(f"Qwen pe_rag_ft 评测统计")
    print(f"{'=' * 50}")
    print(f"总用例数: {stats['total_cases']}")
    print(f"总体平均F1: {stats['overall']['avg_f1']:.4f}")
    print(
        f"F1范围: [{stats['overall']['min_f1']:.4f}, {stats['overall']['max_f1']:.4f}]"
    )
    print(f"\n按难度统计:")
    for diff, diff_stats in stats["by_difficulty"].items():
        print(
            f"  {diff}: count={diff_stats['count']}  avg_f1={diff_stats['avg_f1']:.4f}  [{diff_stats['min_f1']:.4f}, {diff_stats['max_f1']:.4f}]"
        )
    print(f"\n结果文件: {args.output}")
    print(f"统计文件: {stats_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
