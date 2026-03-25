from __future__ import annotations

import argparse
import importlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from evaluation.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank
from rag.rrf_retriever import HybridRetriever, build_retriever


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    difficulty: str
    category: str
    question: str
    entry_file: str
    entry_symbol: str
    gold_fqns: tuple[str, ...]
    reasoning_hint: str = ""
    source_note: str = ""


def load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for item in raw:
        cases.append(
            EvalCase(
                case_id=str(item.get("id", "")),
                difficulty=str(item.get("difficulty", "unknown")),
                category=str(item.get("category", "unspecified")),
                question=str(item.get("question", "")),
                entry_file=str(item.get("entry_file", "")),
                entry_symbol=str(item.get("entry_symbol", "")),
                gold_fqns=tuple(str(value) for value in item.get("gold_fqns", [])),
                reasoning_hint=str(item.get("reasoning_hint", "")),
                source_note=str(item.get("source_note", "")),
            )
        )
    return cases


def summarize_cases(cases: list[EvalCase]) -> dict[str, Any]:
    difficulty_counter = Counter(case.difficulty for case in cases)
    category_counter = Counter(case.category for case in cases)
    avg_gold_targets = (
        sum(len(case.gold_fqns) for case in cases) / len(cases) if cases else 0.0
    )
    return {
        "num_cases": len(cases),
        "difficulty_distribution": dict(sorted(difficulty_counter.items())),
        "category_distribution_top10": dict(category_counter.most_common(10)),
        "avg_gold_targets": round(avg_gold_targets, 2),
        "has_minimum_required_cases": len(cases) >= 50,
        "has_first_batch_seed": len(cases) >= 12,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize eval data, preview prompts, and evaluate retrieval quality."
    )
    parser.add_argument(
        "--eval-cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to the curated evaluation dataset.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("external/celery"),
        help="Path to the bound source repository used by RAG retrieval.",
    )
    parser.add_argument(
        "--mode",
        choices=["baseline", "pe", "rag", "all"],
        default="baseline",
        help="baseline=dataset summary, pe=prompt preview metadata, rag=retrieval metrics, all=summary + rag + pe preview metadata.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k used for retrieval preview and Recall@K evaluation.",
    )
    parser.add_argument(
        "--case-id",
        default="",
        help="Optional case id used when previewing a single prompt or retrieval context.",
    )
    parser.add_argument(
        "--preview-prompt",
        action="store_true",
        help="Print the assembled prompt bundle for the selected case.",
    )
    parser.add_argument(
        "--preview-context",
        action="store_true",
        help="Print retrieved context for the selected case.",
    )
    parser.add_argument(
        "--prompt-version",
        choices=["v1", "v2"],
        default="v1",
        help="Prompt template version used for prompt preview metadata.",
    )
    return parser


def load_prompt_module(version: str) -> ModuleType:
    module_name = "pe.prompt_templates_v2" if version == "v2" else "pe.prompt_templates"
    return importlib.import_module(module_name)


def select_case(cases: list[EvalCase], case_id: str) -> EvalCase | None:
    if not cases:
        return None
    if not case_id:
        return cases[0]
    for case in cases:
        if case.case_id == case_id:
            return case
    raise KeyError(f"Unknown case id: {case_id}")


def evaluate_retrieval(
    cases: list[EvalCase],
    retriever: HybridRetriever,
    top_k: int,
) -> dict[str, Any]:
    ranked_lists: list[list[str]] = []
    gold_sets: list[tuple[str, ...]] = []
    per_case: list[dict[str, Any]] = []
    recall_by_difficulty: dict[str, list[float]] = defaultdict(list)
    rr_by_difficulty: dict[str, list[float]] = defaultdict(list)

    for case in cases:
        hits = retriever.retrieve(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
        )
        ranked = retriever.expand_candidate_fqns(
            hits,
            query_text=f"{case.question} {case.entry_symbol}",
            entry_symbol=case.entry_symbol,
        )
        recall_score = recall_at_k(case.gold_fqns, ranked, top_k)
        rr_score = reciprocal_rank(case.gold_fqns, ranked)
        ranked_lists.append(ranked)
        gold_sets.append(case.gold_fqns)
        recall_by_difficulty[case.difficulty].append(recall_score)
        rr_by_difficulty[case.difficulty].append(rr_score)
        per_case.append(
            {
                "id": case.case_id,
                "difficulty": case.difficulty,
                "category": case.category,
                "recall_at_k": round(recall_score, 4),
                "reciprocal_rank": round(rr_score, 4),
                "top_hits": ranked[:top_k],
            }
        )

    difficulty_breakdown = {
        difficulty: {
            "avg_recall_at_k": round(sum(values) / len(values), 4),
            "avg_reciprocal_rank": round(sum(rr_by_difficulty[difficulty]) / len(rr_by_difficulty[difficulty]), 4),
            "num_cases": len(values),
        }
        for difficulty, values in sorted(recall_by_difficulty.items())
    }

    return {
        "num_cases": len(cases),
        "top_k": top_k,
        "avg_recall_at_k": round(sum(recall_at_k(case.gold_fqns, ranked, top_k) for case, ranked in zip(cases, ranked_lists, strict=True)) / len(cases), 4) if cases else 0.0,
        "mrr": round(mean_reciprocal_rank(gold_sets, ranked_lists), 4),
        "difficulty_breakdown": difficulty_breakdown,
        "cases": per_case,
    }


def preview_prompt(
    case: EvalCase,
    retriever: HybridRetriever,
    top_k: int,
    prompt_module: ModuleType,
) -> str:
    context = retriever.build_context(
        question=case.question,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        top_k=top_k,
    )
    bundle = prompt_module.build_prompt_bundle(
        question=case.question,
        context=context,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
    )
    return bundle.as_text()


def main() -> int:
    args = build_parser().parse_args()
    prompt_module = load_prompt_module(args.prompt_version)
    cases = load_eval_cases(args.eval_cases)
    summary = summarize_cases(cases)
    summary["mode"] = args.mode
    summary["prompt_version"] = args.prompt_version
    summary["few_shot_ready"] = {
        "gap_to_target": prompt_module.few_shot_gap(),
        "target": 20,
    }

    retriever: HybridRetriever | None = None
    if args.mode in {"rag", "all", "pe"} or args.preview_context or args.preview_prompt:
        if not args.repo_root.exists():
            raise FileNotFoundError(f"Repository root not found: {args.repo_root}")
        retriever = build_retriever(args.repo_root)
        summary["rag_index"] = {
            "repo_root": str(args.repo_root),
            "num_chunks": len(retriever.chunks),
        }

    if args.mode in {"rag", "all"} and retriever is not None:
        summary["retrieval"] = evaluate_retrieval(
            cases=cases,
            retriever=retriever,
            top_k=args.top_k,
        )

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    selected = None
    if (args.preview_prompt or args.preview_context) and retriever is not None:
        selected = select_case(cases, args.case_id)

    if args.preview_context and selected is not None and retriever is not None:
        print("\n=== Retrieved Context ===")
        print(
            retriever.build_context(
                question=selected.question,
                entry_symbol=selected.entry_symbol,
                entry_file=selected.entry_file,
                top_k=args.top_k,
            )
        )

    if args.preview_prompt and selected is not None and retriever is not None:
        print("\n=== Prompt Preview ===")
        print(
            preview_prompt(
                selected,
                retriever=retriever,
                top_k=args.top_k,
                prompt_module=prompt_module,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
