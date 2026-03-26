from __future__ import annotations

import argparse
import importlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Sequence

from evaluation.metrics import mean_reciprocal_rank, recall_at_k, reciprocal_rank
from rag.rrf_retriever import HybridRetriever, build_retriever


RETRIEVAL_SOURCES = ("bm25", "semantic", "graph", "fused")


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
    source_schema: str = "legacy_v1"
    failure_type: str = ""
    implicit_level: int | None = None
    direct_gold_fqns: tuple[str, ...] = ()
    indirect_gold_fqns: tuple[str, ...] = ()
    implicit_gold_fqns: tuple[str, ...] = ()


def load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise ValueError(f"Eval dataset must be a JSON array: {path}")

    cases: list[EvalCase] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Eval case #{index} must be a JSON object.")
        if "gold_fqns" in item:
            cases.append(_parse_legacy_case(item=item, index=index))
        elif "ground_truth" in item:
            cases.append(_parse_schema_v2_case(item=item, index=index))
        else:
            raise ValueError(
                f"Eval case #{index} does not match a supported schema. "
                "Expected `gold_fqns` or `ground_truth`."
            )
    return cases


def summarize_cases(cases: list[EvalCase]) -> dict[str, Any]:
    difficulty_counter = Counter(case.difficulty for case in cases)
    category_counter = Counter(case.category for case in cases)
    schema_counter = Counter(case.source_schema for case in cases)
    failure_counter = Counter(case.failure_type for case in cases if case.failure_type)
    avg_gold_targets = (
        sum(len(case.gold_fqns) for case in cases) / len(cases) if cases else 0.0
    )
    return {
        "num_cases": len(cases),
        "difficulty_distribution": dict(sorted(difficulty_counter.items())),
        "category_distribution_top10": dict(category_counter.most_common(10)),
        "source_schema_distribution": dict(sorted(schema_counter.items())),
        "failure_type_distribution": dict(sorted(failure_counter.items())),
        "avg_gold_targets": round(avg_gold_targets, 2),
        "has_minimum_required_cases": len(cases) >= 50,
        "has_first_batch_seed": len(cases) >= 12,
        "entry_metadata_coverage": {
            "with_entry_symbol": sum(1 for case in cases if case.entry_symbol),
            "with_entry_file": sum(1 for case in cases if case.entry_file),
        },
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
        "--per-source",
        type=int,
        default=12,
        help="How many chunk ids to keep from each retrieval source before fusion and reporting.",
    )
    parser.add_argument(
        "--query-mode",
        choices=["question_only", "question_plus_entry"],
        default="question_plus_entry",
        help="question_only=retrieve from natural language only; question_plus_entry=also use entry_symbol and entry_file metadata.",
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
        "--report-path",
        type=Path,
        help="Optional path used to persist the JSON report to disk.",
    )
    parser.add_argument(
        "--prompt-version",
        choices=["v1", "v2"],
        default="v1",
        help="Prompt template version used for prompt preview metadata.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF reciprocal rank fusion k parameter (default 60).",
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
    per_source: int,
    query_mode: str,
    rrf_k: int = 60,
) -> dict[str, Any]:
    chunk_rankings: dict[str, list[list[str]]] = {
        source: [] for source in RETRIEVAL_SOURCES
    }
    expanded_rankings: dict[str, list[list[str]]] = {
        source: [] for source in RETRIEVAL_SOURCES
    }
    per_case: list[dict[str, Any]] = []

    for case in cases:
        query_text = _build_query_text(case=case, query_mode=query_mode)
        trace = retriever.retrieve_with_trace(
            question=case.question,
            entry_symbol=case.entry_symbol,
            entry_file=case.entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
        )
        source_chunk_ids = {
            "bm25": list(trace.bm25),
            "semantic": list(trace.semantic),
            "graph": list(trace.graph),
            "fused": list(trace.fused_ids),
        }
        source_details: dict[str, Any] = {}

        for source_name, chunk_ids in source_chunk_ids.items():
            chunk_symbols = retriever.ranked_symbols(chunk_ids)
            expanded_fqns = retriever.expand_candidate_fqns_from_chunk_ids(
                chunk_ids=chunk_ids,
                source=source_name,
                query_text=query_text,
                entry_symbol=case.entry_symbol,
            )
            chunk_rankings[source_name].append(chunk_symbols)
            expanded_rankings[source_name].append(expanded_fqns)
            source_details[source_name] = {
                "chunk_symbol_top_hits": chunk_symbols[:top_k],
                "expanded_fqn_top_hits": expanded_fqns[:top_k],
                "chunk_symbol_recall_at_k": round(
                    recall_at_k(case.gold_fqns, chunk_symbols, top_k), 4
                ),
                "expanded_fqn_recall_at_k": round(
                    recall_at_k(case.gold_fqns, expanded_fqns, top_k), 4
                ),
                "chunk_symbol_reciprocal_rank": round(
                    reciprocal_rank(case.gold_fqns, chunk_symbols), 4
                ),
                "expanded_fqn_reciprocal_rank": round(
                    reciprocal_rank(case.gold_fqns, expanded_fqns), 4
                ),
            }

        per_case.append(
            {
                "id": case.case_id,
                "difficulty": case.difficulty,
                "category": case.category,
                "failure_type": case.failure_type,
                "source_schema": case.source_schema,
                "gold_fqns": list(case.gold_fqns),
                "sources": source_details,
            }
        )

    source_breakdown: dict[str, Any] = {}
    for source_name in RETRIEVAL_SOURCES:
        source_breakdown[source_name] = {
            "chunk_symbols": _summarize_ranked_lists(
                cases=cases,
                ranked_lists=chunk_rankings[source_name],
                top_k=top_k,
            ),
            "expanded_fqns": _summarize_ranked_lists(
                cases=cases,
                ranked_lists=expanded_rankings[source_name],
                top_k=top_k,
            ),
        }

    return {
        "num_cases": len(cases),
        "top_k": top_k,
        "setting": {
            "query_mode": query_mode,
            "rrf_k": rrf_k,
            "query_inputs": (
                ["question"]
                if query_mode == "question_only"
                else ["question", "entry_symbol", "entry_file"]
            ),
            "per_source_depth": per_source,
            "gold_scope": {
                "legacy_v1": "gold_fqns",
                "schema_v2": "union(direct_deps, indirect_deps, implicit_deps)",
            },
            "ranking_views": {
                "chunk_symbols": "Uses retrieved chunk symbols only; no candidate expansion.",
                "expanded_fqns": "Uses retrieved chunks plus heuristic expansion over imports, string targets, and references.",
            },
        },
        "fused_chunk_symbols": source_breakdown["fused"]["chunk_symbols"],
        "fused_expanded_fqns": source_breakdown["fused"]["expanded_fqns"],
        "source_breakdown": source_breakdown,
        "cases": per_case,
    }


def preview_prompt(
    case: EvalCase,
    retriever: HybridRetriever,
    top_k: int,
    per_source: int,
    prompt_module: ModuleType,
    query_mode: str,
    rrf_k: int = 60,
) -> str:
    context = retriever.build_context(
        question=case.question,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        top_k=top_k,
        per_source=per_source,
        query_mode=query_mode,
        rrf_k=rrf_k,
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
    summary["query_mode"] = args.query_mode
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
            per_source=args.per_source,
            query_mode=args.query_mode,
            rrf_k=args.rrf_k,
        )

    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
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
                per_source=args.per_source,
                query_mode=args.query_mode,
                rrf_k=args.rrf_k,
            )
        )

    if args.preview_prompt and selected is not None and retriever is not None:
        print("\n=== Prompt Preview ===")
        print(
            preview_prompt(
                case=selected,
                retriever=retriever,
                top_k=args.top_k,
                per_source=args.per_source,
                prompt_module=prompt_module,
                query_mode=args.query_mode,
                rrf_k=args.rrf_k,
            )
        )

    return 0


def _parse_legacy_case(item: dict[str, Any], index: int) -> EvalCase:
    case_id = _require_string(item, "id", index)
    question = _require_string(item, "question", index, case_id=case_id)
    entry_file = _require_string(item, "entry_file", index, case_id=case_id)
    entry_symbol = _require_string(item, "entry_symbol", index, case_id=case_id)
    gold_fqns = _normalize_ranked_items(item.get("gold_fqns", []))
    if not gold_fqns:
        raise ValueError(f"Legacy eval case `{case_id}` has no gold_fqns.")

    return EvalCase(
        case_id=case_id,
        difficulty=_require_string(item, "difficulty", index, case_id=case_id),
        category=str(item.get("category", "unspecified")),
        question=question,
        entry_file=entry_file,
        entry_symbol=entry_symbol,
        gold_fqns=gold_fqns,
        reasoning_hint=str(item.get("reasoning_hint", "")),
        source_note=str(item.get("source_note", "")),
        source_schema="legacy_v1",
        direct_gold_fqns=gold_fqns,
    )


def _parse_schema_v2_case(item: dict[str, Any], index: int) -> EvalCase:
    case_id = _require_string(item, "id", index)
    question = _require_string(item, "question", index, case_id=case_id)
    source_file = _require_string(item, "source_file", index, case_id=case_id)
    ground_truth = item.get("ground_truth")
    if not isinstance(ground_truth, dict):
        raise ValueError(f"Schema-v2 eval case `{case_id}` has invalid ground_truth.")

    direct = _normalize_ranked_items(ground_truth.get("direct_deps", []))
    indirect = _normalize_ranked_items(ground_truth.get("indirect_deps", []))
    implicit = _normalize_ranked_items(ground_truth.get("implicit_deps", []))
    gold_fqns = _normalize_ranked_items([*direct, *indirect, *implicit])
    if not gold_fqns:
        raise ValueError(f"Schema-v2 eval case `{case_id}` has no gold dependencies.")

    implicit_level_raw = item.get("implicit_level")
    implicit_level = int(implicit_level_raw) if implicit_level_raw is not None else None

    return EvalCase(
        case_id=case_id,
        difficulty=_require_string(item, "difficulty", index, case_id=case_id),
        category=str(item.get("category", "unspecified")),
        question=question,
        entry_file=source_file,
        entry_symbol=str(item.get("entry_symbol", "")),
        gold_fqns=gold_fqns,
        reasoning_hint=str(item.get("reasoning_hint", "")),
        source_note=str(item.get("source_note", "")),
        source_schema="schema_v2",
        failure_type=str(item.get("failure_type", "")),
        implicit_level=implicit_level,
        direct_gold_fqns=direct,
        indirect_gold_fqns=indirect,
        implicit_gold_fqns=implicit,
    )


def _summarize_ranked_lists(
    cases: Sequence[EvalCase],
    ranked_lists: Sequence[Sequence[str]],
    top_k: int,
) -> dict[str, Any]:
    if len(cases) != len(ranked_lists):
        raise ValueError("Cases and ranked_lists must be aligned.")

    gold_sets = [case.gold_fqns for case in cases]
    recall_by_difficulty: dict[str, list[float]] = defaultdict(list)
    rr_by_difficulty: dict[str, list[float]] = defaultdict(list)
    recall_by_failure_type: dict[str, list[float]] = defaultdict(list)
    rr_by_failure_type: dict[str, list[float]] = defaultdict(list)
    for case, ranked in zip(cases, ranked_lists):
        recall_score = recall_at_k(case.gold_fqns, ranked, top_k)
        rr_score = reciprocal_rank(case.gold_fqns, ranked)
        recall_by_difficulty[case.difficulty].append(recall_score)
        rr_by_difficulty[case.difficulty].append(rr_score)
        if case.failure_type:
            recall_by_failure_type[case.failure_type].append(recall_score)
            rr_by_failure_type[case.failure_type].append(rr_score)

    return {
        "avg_recall_at_k": round(
            sum(
                recall_at_k(case.gold_fqns, ranked, top_k)
                for case, ranked in zip(cases, ranked_lists)
            )
            / len(cases),
            4,
        )
        if cases
        else 0.0,
        "mrr": round(mean_reciprocal_rank(gold_sets, ranked_lists), 4),
        "difficulty_breakdown": _aggregate_bucket_metrics(
            recall_by_difficulty,
            rr_by_difficulty,
        ),
        "failure_type_breakdown": _aggregate_bucket_metrics(
            recall_by_failure_type,
            rr_by_failure_type,
        ),
    }


def _aggregate_bucket_metrics(
    recall_buckets: dict[str, list[float]],
    rr_buckets: dict[str, list[float]],
) -> dict[str, Any]:
    return {
        bucket: {
            "avg_recall_at_k": round(sum(recall_values) / len(recall_values), 4),
            "avg_reciprocal_rank": round(
                sum(rr_buckets[bucket]) / len(rr_buckets[bucket]),
                4,
            ),
            "num_cases": len(recall_values),
        }
        for bucket, recall_values in sorted(recall_buckets.items())
        if recall_values
    }


def _build_query_text(case: EvalCase, query_mode: str) -> str:
    if query_mode == "question_only":
        return case.question.strip()
    if query_mode != "question_plus_entry":
        raise ValueError(f"Unsupported query mode: {query_mode}")
    return " ".join(
        part
        for part in (
            case.question.strip(),
            case.entry_symbol.strip(),
            case.entry_file.strip(),
        )
        if part
    )


def _normalize_ranked_items(values: Iterable[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return tuple(normalized)


def _require_string(
    item: dict[str, Any],
    key: str,
    index: int,
    case_id: str = "",
) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        label = case_id or f"#{index}"
        raise ValueError(f"Eval case {label} is missing required string field `{key}`.")
    return value.strip()


if __name__ == "__main__":
    raise SystemExit(main())
