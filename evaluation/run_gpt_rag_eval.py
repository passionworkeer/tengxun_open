"""
RAG + GPT-5.4 端到端生成评测

对比 GPT-5.4 有/无 RAG 上下文时的生成质量。
衡量 RAG 对最终 F1 的真实提升。
"""

from __future__ import annotations

import json
import argparse
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_set_metrics
from rag.rrf_retriever import build_retriever


def build_prompt_with_rag(case: EvalCase, context: str) -> str:
    """带 RAG 上下文的 prompt"""
    parts = [
        "You are a senior Python static analysis expert working on cross-file dependency resolution.",
        "Use the provided context to find the exact dependency chain.\n",
        f"Question: {case.question.strip()}",
    ]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    if context:
        parts.append(f"\nRetrieved Context:\n{context.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'
    )
    return "\n\n".join(parts)


def build_prompt_no_rag(case: EvalCase) -> str:
    """无 RAG 上下文的 prompt（基线）"""
    parts = [
        "You are a senior Python static analysis expert working on cross-file dependency resolution.\n",
        f"Question: {case.question.strip()}",
    ]
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
    if not all_gt:
        return 0.0
    metrics = compute_set_metrics(list(all_gt), list(all_pred))
    return metrics.f1


def run_gpt_eval_with_rag(
    cases: list[EvalCase],
    retriever,
    weights: dict[str, float],
    rrf_k: int,
    api_key: str,
    base_url: str = "https://ai.td.ee/v1",
    model: str = "gpt-5.4",
    output_path: Path | None = None,
    max_cases: int | None = None,
    run_baseline: bool = True,
) -> list[dict[str, Any]]:
    client = OpenAI(base_url=base_url, api_key=api_key)

    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) if case.direct_gold_fqns else [],
            "indirect_deps": list(case.indirect_gold_fqns)
            if case.indirect_gold_fqns
            else [],
            "implicit_deps": list(case.implicit_gold_fqns)
            if case.implicit_gold_fqns
            else [],
        }

        case_result: dict[str, Any] = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "failure_type": getattr(case, "failure_type", ""),
            "model": model,
            "question": case.question,
            "ground_truth": gt_dict,
        }

        # Without RAG baseline
        if run_baseline:
            prompt_no_rag = build_prompt_no_rag(case)
            pred_no_rag = None
            raw_no_rag = None
            for attempt in range(3):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt_no_rag}],
                        stream=False,
                        timeout=300,
                    )
                    msg = response.choices[0].message
                    raw_no_rag = msg.content if msg and msg.content else ""
                    pred_no_rag = parse_response(raw_no_rag)
                    break
                except Exception as e:
                    print(f"  No-RAG attempt {attempt + 1} ERROR: {e}", flush=True)
                    time.sleep(5)
                    raw_no_rag = str(e)

            f1_no_rag = compute_f1(pred_no_rag or {}, gt_dict) if pred_no_rag else 0.0
            case_result["no_rag"] = {
                "raw_output": raw_no_rag,
                "prediction": pred_no_rag,
                "f1": round(f1_no_rag, 4),
            }
            print(f"  No-RAG F1: {f1_no_rag:.4f}", flush=True)

        # With RAG
        context = retriever.build_context(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=5,
            per_source=12,
            query_mode="question_plus_entry",
            rrf_k=rrf_k,
            weights=weights,
        )

        prompt_with_rag = build_prompt_with_rag(case, context)
        pred_with_rag = None
        raw_with_rag = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt_with_rag}],
                    stream=False,
                    timeout=300,
                )
                msg = response.choices[0].message
                raw_with_rag = msg.content if msg and msg.content else ""
                pred_with_rag = parse_response(raw_with_rag)
                break
            except Exception as e:
                print(f"  With-RAG attempt {attempt + 1} ERROR: {e}", flush=True)
                time.sleep(5)
                raw_with_rag = str(e)

        f1_with_rag = compute_f1(pred_with_rag or {}, gt_dict) if pred_with_rag else 0.0
        case_result["with_rag"] = {
            "raw_output": raw_with_rag,
            "prediction": pred_with_rag,
            "f1": round(f1_with_rag, 4),
            "context_preview": context[:200] + "..." if len(context) > 200 else context,
        }
        print(f"  With-RAG F1: {f1_with_rag:.4f}", flush=True)

        if run_baseline:
            delta = f1_with_rag - f1_no_rag
            case_result["delta"] = round(delta, 4)
            print(f"  Delta: {delta:+.4f}", flush=True)

        results.append(case_result)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    return results


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总结果"""
    summary: dict[str, Any] = {
        "total": len(results),
        "by_difficulty": {},
        "by_failure_type": {},
        "overall": {},
    }

    # Collect all deltas and F1s
    deltas = []
    f1s_no_rag = []
    f1s_with_rag = []

    for r in results:
        diff = r.get("difficulty", "unknown")
        ft = r.get("failure_type", "unknown")

        f1_no_rag = r.get("no_rag", {}).get("f1", None)
        f1_with_rag = r.get("with_rag", {}).get("f1", 0.0)
        delta = r.get("delta", None)

        if f1_no_rag is not None:
            f1s_no_rag.append(f1_no_rag)
        f1s_with_rag.append(f1_with_rag)
        if delta is not None:
            deltas.append(delta)

        # By difficulty
        if diff not in summary["by_difficulty"]:
            summary["by_difficulty"][diff] = {
                "f1_no_rag": [],
                "f1_with_rag": [],
                "deltas": [],
                "count": 0,
            }
        if f1_no_rag is not None:
            summary["by_difficulty"][diff]["f1_no_rag"].append(f1_no_rag)
        summary["by_difficulty"][diff]["f1_with_rag"].append(f1_with_rag)
        if delta is not None:
            summary["by_difficulty"][diff]["deltas"].append(delta)
        summary["by_difficulty"][diff]["count"] += 1

        # By failure type
        if ft not in summary["by_failure_type"]:
            summary["by_failure_type"][ft] = {
                "f1_no_rag": [],
                "f1_with_rag": [],
                "deltas": [],
                "count": 0,
            }
        if f1_no_rag is not None:
            summary["by_failure_type"][ft]["f1_no_rag"].append(f1_no_rag)
        summary["by_failure_type"][ft]["f1_with_rag"].append(f1_with_rag)
        if delta is not None:
            summary["by_failure_type"][ft]["deltas"].append(delta)
        summary["by_failure_type"][ft]["count"] += 1

    # Compute averages
    def avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    summary["overall"] = {
        "avg_f1_no_rag": avg(f1s_no_rag),
        "avg_f1_with_rag": avg(f1s_with_rag),
        "avg_delta": avg(deltas),
    }

    for diff, data in summary["by_difficulty"].items():
        summary["by_difficulty"][diff] = {
            "count": data["count"],
            "avg_f1_no_rag": avg(data["f1_no_rag"]),
            "avg_f1_with_rag": avg(data["f1_with_rag"]),
            "avg_delta": avg(data["deltas"]),
        }

    for ft, data in summary["by_failure_type"].items():
        summary["by_failure_type"][ft] = {
            "count": data["count"],
            "avg_f1_no_rag": avg(data["f1_no_rag"]),
            "avg_f1_with_rag": avg(data["f1_with_rag"]),
            "avg_delta": avg(data["deltas"]),
        }

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG + GPT-5.4 端到端生成评测")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases_migrated_draft_round4.json"),
        help="Path to evaluation dataset.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("external/celery"),
        help="Path to Celery source repository.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        required=True,
        help="API key.",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://ai.td.ee/v1",
        help="API base URL.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.4",
        help="Model name.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/gpt_rag_e2e_results.json"),
        help="Output path for results.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit number of cases (for testing).",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help="Skip no-RAG baseline (only run with RAG).",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=30,
        help="RRF k parameter.",
    )
    parser.add_argument(
        "--weights",
        default="0.25,0.05,0.7",
        help="Comma-separated weights for BM25,Semantic,Graph (default: 0.25,0.05,0.7).",
    )
    args = parser.parse_args()

    # Parse weights
    parts = args.weights.split(",")
    weights = {
        "bm25": float(parts[0]),
        "semantic": float(parts[1]),
        "graph": float(parts[2]),
    }

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    retriever = build_retriever(args.repo_root)
    print(f"Retriever built with {len(retriever.chunks)} chunks.")
    print(f"RAG config: k={args.rrf_k}, weights={weights}")

    results = run_gpt_eval_with_rag(
        cases=cases,
        retriever=retriever,
        weights=weights,
        rrf_k=args.rrf_k,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        output_path=args.output,
        max_cases=args.max_cases,
        run_baseline=not args.no_baseline,
    )

    summary = summarize_results(results)

    # Save summary alongside results
    summary_path = args.output.parent / f"{args.output.stem}_summary.json"
    full_output = {
        "config": {
            "model": args.model,
            "rrf_k": args.rrf_k,
            "weights": weights,
            "num_cases": len(results),
        },
        "summary": summary,
        "results": results,
    }
    summary_path.write_text(
        json.dumps(full_output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n=== Summary ===")
    print(
        f"Overall: No-RAG F1={summary['overall']['avg_f1_no_rag']}, "
        f"With-RAG F1={summary['overall']['avg_f1_with_rag']}, "
        f"Delta={summary['overall']['avg_delta']:+.4f}"
    )
    print(f"\nBy Difficulty:")
    for diff, data in summary["by_difficulty"].items():
        print(
            f"  {diff}: No-RAG={data['avg_f1_no_rag']}, With-RAG={data['avg_f1_with_rag']}, Delta={data['avg_delta']:+.4f}"
        )
    print(f"\nBy Failure Type:")
    for ft, data in summary["by_failure_type"].items():
        print(
            f"  {ft}: No-RAG={data['avg_f1_no_rag']}, With-RAG={data['avg_f1_with_rag']}, Delta={data['avg_delta']:+.4f}"
        )

    print(f"\nResults saved to {args.output}")
    print(f"Full output with summary saved to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
