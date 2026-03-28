"""
Qwen 消融评测统一脚本

支持四种模式：
1. baseline: 纯模型基线
2. pe: Prompt Engineering only
3. rag: RAG only
4. pe_rag: PE + RAG

示例：
    uv run --with openai python run_qwen_ablation_eval.py --mode pe
    uv run --with openai python run_qwen_ablation_eval.py --mode rag --repo-root external/celery
    uv run --with openai python run_qwen_ablation_eval.py --mode pe_rag --output results/qwen_pe_rag_latest.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from evaluation.baseline import EvalCase, load_eval_cases
from evaluation.metrics import compute_set_metrics
from pe.prompt_templates_v2 import build_prompt_bundle, format_few_shot_example
from rag.rrf_retriever import build_retriever


DEFAULT_BASE_URL = "http://localhost:8000/v1"
DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_CASES = Path("data/eval_cases.json")
DEFAULT_REPO_ROOT = Path("external/celery")
DEFAULT_RRF_K = 30
DEFAULT_RAG_TOP_K = 5
DEFAULT_PER_SOURCE = 12
DEFAULT_WEIGHTS = {"bm25": 0.25, "semantic": 0.05, "graph": 0.7}
MAX_NEW_TOKENS = 500


def build_json_prompt(case: EvalCase, context: str = "") -> str:
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


def build_json_only_messages(case: EvalCase, context: str = "") -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a JSON-only response bot. "
                "You must ONLY output valid JSON objects, no explanations, "
                "no markdown, no extra text."
            ),
        },
        {"role": "user", "content": build_json_prompt(case, context=context)},
    ]


def build_pe_messages(case: EvalCase, context: str = "") -> list[dict[str, str]]:
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


def parse_response(text: str) -> dict[str, list[str]] | None:
    try:
        text = text.strip()
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


def parse_weights(raw: str) -> dict[str, float]:
    parts = [float(item.strip()) for item in raw.split(",")]
    if len(parts) != 3:
        raise ValueError("weights must have exactly 3 comma-separated values")
    return {"bm25": parts[0], "semantic": parts[1], "graph": parts[2]}


def output_path_for_mode(mode: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"results/qwen_{mode}_{ts}.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Qwen ablation evaluation.")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("baseline", "pe", "rag", "pe_rag"),
        help="Ablation mode to run.",
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--api-key", type=str, default="EMPTY")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument(
        "--resume", action="store_true", help="Resume from existing output file"
    )
    parser.add_argument("--rag-top-k", type=int, default=DEFAULT_RAG_TOP_K)
    parser.add_argument("--per-source", type=int, default=DEFAULT_PER_SOURCE)
    parser.add_argument("--rrf-k", type=int, default=DEFAULT_RRF_K)
    parser.add_argument(
        "--weights",
        type=str,
        default="0.25,0.05,0.7",
        help="Comma-separated bm25,semantic,graph weights.",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = output_path_for_mode(args.mode)

    weights = parse_weights(args.weights)
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    cases = load_eval_cases(args.cases)
    if args.max_cases:
        cases = cases[: args.max_cases]

    retriever = None
    if args.mode in {"rag", "pe_rag"}:
        print(f"构建 RAG 检索器: {args.repo_root}")
        retriever = build_retriever(args.repo_root)
        print(f"RAG 索引完成，共 {len(retriever.chunks)} 个代码块")

    print(f"加载 {len(cases)} 条评测用例，模式={args.mode}\n")

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

        context = ""
        if retriever is not None:
            context = retriever.build_context(
                question=case.question,
                entry_symbol=case.entry_symbol,
                entry_file=case.entry_file,
                top_k=args.rag_top_k,
                per_source=args.per_source,
                query_mode="question_plus_entry",
                rrf_k=args.rrf_k,
                weights=weights,
            )

        if args.mode == "baseline":
            messages = build_json_only_messages(case, context="")
        elif args.mode == "pe":
            messages = build_pe_messages(case, context="")
        elif args.mode == "rag":
            messages = build_json_only_messages(case, context=context)
        else:
            messages = build_pe_messages(case, context=context)

        raw_output = ""
        prediction = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    stream=False,
                    timeout=300,
                    temperature=0.1,
                    max_tokens=MAX_NEW_TOKENS,
                )
                msg = response.choices[0].message
                raw_output = msg.content if msg and msg.content else ""
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
            "mode": args.mode,
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

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    stats = analyze_results(results)
    stats["strategy"] = args.mode
    stats["model"] = args.model
    stats["base_url"] = args.base_url
    if retriever is not None:
        stats["rag"] = {
            "repo_root": str(args.repo_root),
            "rag_top_k": args.rag_top_k,
            "per_source": args.per_source,
            "rrf_k": args.rrf_k,
            "weights": weights,
        }
    stats_path = args.output.parent / f"{args.output.stem}_stats.json"
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\n" + "=" * 50)
    print(f"Qwen {args.mode} 评测统计")
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
