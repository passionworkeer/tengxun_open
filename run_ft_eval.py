"""
Qwen 微调模型评测脚本（FT / PE+FT / PE+RAG+FT）

支持三种评测策略，通过 --strategy 参数切换：
  ft        : 纯微调模型（baseline prompt）
  pe_ft     : PE + 微调模型（few-shot + CoT）
  pe_rag_ft : PE + RAG + 微调模型（完整策略）

用法：
    python run_ft_eval.py --strategy ft
    python run_ft_eval.py --strategy pe_ft
    python run_ft_eval.py --strategy pe_rag_ft --repo-root external/celery
    python run_ft_eval.py --strategy pe_rag_ft --max-cases 3  # 调试用

结果自动保存到 results/，同时生成 *_stats.json 统计摘要。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics
from pe.prompt_templates_v2 import (
    SYSTEM_PROMPT,
    COT_TEMPLATE,
    build_prompt_bundle,
    format_few_shot_example,
)
from rag.rrf_retriever import HybridRetriever, build_retriever
from rag.embedding_provider import resolve_embedding_config


BASE_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_STRICT_ADAPTER_DIR = Path("artifacts/lora/qwen3.5-9b/strict_clean_20260329")
DEFAULT_STRICT_ADAPTER_TARBALL = Path("artifacts/handoff/strict_clean_20260329_minimal.tar.gz")
DEFAULT_ADAPTER_PATH = os.environ.get(
    "QWEN_LORA_ADAPTER_PATH",
    str(DEFAULT_STRICT_ADAPTER_DIR),
)
DATA_PATH = Path("data/eval_cases.json")
REPO_ROOT = Path("external/celery")
MAX_NEW_TOKENS = 500
RAG_TOP_K = 5
PER_SOURCE = 12
RRF_K = 30
QUERY_MODE = "question_plus_entry"
MAX_CONTEXT_TOKENS = 4096
VALID_STRATEGIES = ("ft", "pe_ft", "pe_rag_ft")


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _has_adapter_weights(adapter_path: Path) -> bool:
    required = ("adapter_config.json", "adapter_model.safetensors")
    return all((adapter_path / filename).exists() for filename in required)


def ensure_adapter_path(adapter_path: str) -> Path:
    path = Path(adapter_path)
    if _has_adapter_weights(path):
        return path

    if path == DEFAULT_STRICT_ADAPTER_DIR and DEFAULT_STRICT_ADAPTER_TARBALL.exists():
        path.mkdir(parents=True, exist_ok=True)
        with tarfile.open(DEFAULT_STRICT_ADAPTER_TARBALL, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                filename = Path(member.name).name
                if not filename:
                    continue
                target = path / filename
                if target.exists():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                target.write_bytes(extracted.read())

    if not _has_adapter_weights(path):
        raise FileNotFoundError(
            "LoRA adapter not found. "
            f"Expected adapter weights under {path}. "
            "You can run `make materialize-strict-adapter`, pass `--adapter-path`, "
            "or set `QWEN_LORA_ADAPTER_PATH`."
        )
    return path


def load_model(base_model_path: str, adapter_path: str):
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "缺少微调评测依赖。请先安装 `requirements-finetune.txt`，"
            "或在已有训练环境中执行 `run_ft_eval.py`。"
        ) from exc

    resolved_adapter_path = ensure_adapter_path(adapter_path)
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
    print(f"加载LoRA adapter: {resolved_adapter_path}")
    model = PeftModel.from_pretrained(model, str(resolved_adapter_path))
    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------

def init_rag(repo_root: Path) -> HybridRetriever | None:
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
    retriever: HybridRetriever | None,
    question: str,
    entry_symbol: str = "",
    entry_file: str = "",
    top_k: int = RAG_TOP_K,
    per_source: int = PER_SOURCE,
    query_mode: str = QUERY_MODE,
    rrf_k: int = RRF_K,
    weights: dict[str, float] | None = None,
    max_context_tokens: int = MAX_CONTEXT_TOKENS,
) -> str:
    if retriever is None:
        return ""
    try:
        return retriever.build_context(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
            max_context_tokens=max_context_tokens,
        )
    except Exception as e:
        print(f"RAG检索失败: {e}")
        return ""


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_ft_prompt(case: EvalCase) -> list[dict[str, str]]:
    """裸 prompt，仅用于 FT-only 模式"""
    system_prompt = (
        "You are a JSON-only response bot. You must ONLY output valid JSON objects, "
        "no explanations, no markdown, no extra text."
    )
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Provided Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Provided Entry File: {case.entry_file.strip()}")
    parts.append(
        '\nFormat: {"ground_truth": {"direct_deps": ["module.path"], '
        '"indirect_deps": [], "implicit_deps": []}}'
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def build_pe_prompt(case: EvalCase, context: str = "") -> list[dict[str, str]]:
    """PE prompt：System + CoT + Few-shot"""
    bundle = build_prompt_bundle(
        question=case.question,
        context=context,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        max_examples=6,
    )
    combined_system = bundle.system_prompt.strip()
    if bundle.cot_template.strip():
        combined_system += "\n\n" + bundle.cot_template.strip()
    messages: list[dict[str, str]] = [{"role": "system", "content": combined_system}]
    for example in bundle.few_shot_examples:
        messages.append({"role": "user", "content": format_few_shot_example(example)})
    messages.append({"role": "user", "content": bundle.user_prompt.strip()})
    return messages


# ---------------------------------------------------------------------------
# Generation & parsing
# ---------------------------------------------------------------------------

def generate_response(
    model, tokenizer, messages: list[dict[str, str]], max_new_tokens: int = MAX_NEW_TOKENS
) -> str:
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
    generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True)


def parse_response(raw: str) -> dict[str, list[str]] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        data = json.loads(match.group(0)) if match else json.loads(text)
        gt = data.get("ground_truth", {})

        def normalize(items: Any) -> list[str]:
            if not isinstance(items, list):
                return []
            return [i.strip() for i in items if isinstance(i, str) and i.strip()]

        return {
            "direct_deps": normalize(gt.get("direct_deps", [])),
            "indirect_deps": normalize(gt.get("indirect_deps", [])),
            "implicit_deps": normalize(gt.get("implicit_deps", [])),
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
    return compute_set_metrics(list(gt_all), list(pred_all)).f1


# ---------------------------------------------------------------------------
# Result analysis
# ---------------------------------------------------------------------------

def analyze_results(results: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    by_diff: dict[str, list[float]] = {}
    for r in results:
        by_diff.setdefault(r["difficulty"], []).append(r["f1"])

    all_f1 = [r["f1"] for r in results]
    return {
        "total_cases": len(results),
        "strategy": strategy,
        "by_difficulty": {
            diff: {
                "count": len(scores),
                "avg_f1": round(sum(scores) / len(scores), 4),
                "min_f1": round(min(scores), 4),
                "max_f1": round(max(scores), 4),
            }
            for diff, scores in sorted(by_diff.items())
        },
        "overall": {
            "avg_f1": round(sum(all_f1) / len(all_f1), 4),
            "min_f1": round(min(all_f1), 4),
            "max_f1": round(max(all_f1), 4),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Qwen FT evaluation (FT / PE+FT / PE+RAG+FT)")
    parser.add_argument(
        "--strategy",
        type=str,
        choices=VALID_STRATEGIES,
        default="ft",
        help="评测策略: ft | pe_ft | pe_rag_ft",
    )
    parser.add_argument("--base-model", type=str, default=BASE_MODEL)
    parser.add_argument("--adapter-path", type=str, default=DEFAULT_ADAPTER_PATH)
    parser.add_argument("--cases", type=Path, default=DATA_PATH)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--rag-top-k", type=int, default=RAG_TOP_K)
    parser.add_argument("--per-source", type=int, default=PER_SOURCE)
    parser.add_argument("--query-mode", type=str, default=QUERY_MODE)
    parser.add_argument("--rrf-k", type=int, default=RRF_K)
    parser.add_argument(
        "--weights",
        type=str,
        default=None,
        help="Comma-separated bm25,semantic,graph weights. Default: 0.25,0.05,0.7",
    )
    parser.add_argument("--max-context-tokens", type=int, default=MAX_CONTEXT_TOKENS)
    parser.add_argument(
        "--resume", action="store_true", help="Resume from existing output file"
    )
    args = parser.parse_args()

    strategy = args.strategy

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = Path(f"results/qwen_{strategy}_{ts}.json")

    # weights
    weights = None
    if args.weights:
        parts = [float(x.strip()) for x in args.weights.split(",")]
        if len(parts) != 3:
            raise ValueError("--weights must have exactly 3 comma-separated values")
        weights = {"bm25": parts[0], "semantic": parts[1], "graph": parts[2]}

    # RAG
    retriever: HybridRetriever | None = None
    rag_available = False
    if strategy == "pe_rag_ft":
        embedding_config = resolve_embedding_config()
        retriever = init_rag(args.repo_root)
        rag_available = retriever is not None
        if not rag_available:
            print("警告: RAG不可用，将使用 PE+FT 模式")

    # Model
    model, tokenizer = load_model(args.base_model, args.adapter_path)

    cases = load_eval_cases(args.cases)
    if args.max_cases:
        cases = cases[: args.max_cases]
    print(f"加载 {len(cases)} 条评测用例，策略={strategy}\n")

    results: list[dict[str, Any]] = []
    processed_case_ids: set[str] = set()

    if args.resume and args.output.exists():
        try:
            existing = json.loads(args.output.read_text(encoding="utf-8"))
            results = existing
            processed_case_ids = {r["case_id"] for r in existing}
            print(f"断点续传：已加载 {len(existing)} 条已有结果")
        except Exception as exc:
            print(f"警告：无法加载已有结果文件：{exc}")

    for i, case in enumerate(cases):
        if case.case_id in processed_case_ids:
            print(f"[{i + 1}/{len(cases)}] {case.case_id} ... 已跳过（已完成）")
            continue

        print(f"[{i + 1}/{len(cases)}] {case.case_id} ...", end=" ", flush=True)

        # Build context
        context = ""
        if strategy == "pe_rag_ft" and retriever is not None:
            context = retrieve_context(
                retriever,
                question=case.question,
                entry_symbol=case.entry_symbol,
                entry_file=case.entry_file,
                top_k=args.rag_top_k,
                per_source=args.per_source,
                query_mode=args.query_mode,
                rrf_k=args.rrf_k,
                weights=weights,
                max_context_tokens=args.max_context_tokens,
            )

        # Build messages
        if strategy == "ft":
            messages = build_ft_prompt(case)
        else:  # pe_ft or pe_rag_ft
            messages = build_pe_prompt(case, context)

        # Generate
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

        result: dict[str, Any] = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "failure_type": getattr(case, "failure_type", None),
            "question": case.question,
            "entry_symbol": case.entry_symbol,
            "entry_file": case.entry_file,
            "ground_truth": {
                "direct_deps": list(case.direct_gold_fqns),
                "indirect_deps": list(case.indirect_gold_fqns),
                "implicit_deps": list(case.implicit_gold_fqns),
            },
            "model_output": raw_output,
            "extracted_prediction": prediction,
            "f1": round(f1, 4),
        }

        if strategy == "pe_rag_ft":
            result["rag_context_length"] = len(context)
            result["rag_available"] = rag_available

        results.append(result)
        print(f"F1={f1:.4f}", flush=True)

        # Live save
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # Stats
    stats = analyze_results(results, strategy)
    if strategy == "pe_rag_ft":
        stats["rag_available"] = rag_available
        stats["model"] = args.base_model
        stats["adapter_path"] = args.adapter_path
        if rag_available:
            embedding_config = resolve_embedding_config()
            stats["embedding"] = {
                "provider": embedding_config.provider,
                "model": embedding_config.model,
                "dimension": embedding_config.dimension,
            }
            stats["rag"] = {
                "repo_root": str(args.repo_root),
                "rag_top_k": args.rag_top_k,
                "per_source": args.per_source,
                "query_mode": args.query_mode,
                "rrf_k": args.rrf_k,
                "weights": weights,
                "max_context_tokens": args.max_context_tokens,
            }

    stats_path = args.output.parent / f"{args.output.stem}_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Print
    label = f"PE+RAG+FT" if rag_available else f"PE+FT" if strategy == "pe_rag_ft" else "FT"
    print(f"\n{'=' * 50}")
    print(f"{label} 评测统计")
    print(f"{'=' * 50}")
    print(f"总用例数: {stats['total_cases']}")
    print(f"总体平均F1: {stats['overall']['avg_f1']:.4f}")
    print(f"F1范围: [{stats['overall']['min_f1']:.4f}, {stats['overall']['max_f1']:.4f}]")
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
