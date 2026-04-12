"""
基线评测模块

功能：
1. 加载和解析评测数据集（支持新旧两种schema）
2. 生成数据集统计摘要
3. 运行RAG检索评测
4. 预览prompt效果

当前正式任务设置：
- `question_plus_entry` 是默认口径
- 问题文本之外，还会提供人工标注的入口文件 anchor
- `5/54` 条样本额外提供显式 `entry_symbol`

用法示例：
    python -m evaluation.baseline --mode all --eval-cases data/eval_cases.json
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from types import ModuleType

from .evaluator import RETRIEVAL_SOURCES, evaluate_retrieval
from .loader import EvalCase, load_eval_cases
from .preview import preview_prompt
from .summarizer import summarize_cases


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
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
        help="baseline=数据集摘要, pe=prompt预览元数据, rag=检索指标, all=完整评测",
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
        help=(
            "question_only=仅用自然语言检索; "
            "question_plus_entry=正式 entry-guided 口径，同时使用题目中提供的 "
            "entry_symbol 和 entry_file anchor."
        ),
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
        default=30,
        help="RRF reciprocal rank fusion k parameter (default 30).",
    )
    parser.add_argument(
        "--weights",
        default="",
        help="Comma-separated weights for BM25,Semantic,Graph sources, e.g. '0.25,0.05,0.7'. "
        "When empty, uses unweighted RRF. Recommended: '0.25,0.05,0.7' (BM25,Semantic,Graph).",
    )
    return parser


def load_prompt_module(version: str) -> ModuleType:
    """加载提示词模板模块"""
    module_name = "pe.prompt_templates_v2" if version == "v2" else "pe.prompt_templates"
    return importlib.import_module(module_name)


def select_case(cases: list[EvalCase], case_id: str) -> EvalCase | None:
    """
    根据case_id选择案例

    Args:
        cases: 案例列表
        case_id: 要查找的案例ID，为空则返回第一个

    Returns:
        找到的案例或None
    """
    if not cases:
        return None
    if not case_id:
        return cases[0]
    for case in cases:
        if case.case_id == case_id:
            return case
    raise KeyError(f"Unknown case id: {case_id}")


def main() -> int:
    """
    主入口函数

    解析参数、加载数据、执行评测、输出结果。
    """
    from rag.rrf_retriever import HybridRetriever, build_retriever

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

    weights: dict[str, float] | None = None
    if args.weights:
        parts = args.weights.split(",")
        if len(parts) == 3:
            weights = {
                "bm25": float(parts[0]),
                "semantic": float(parts[1]),
                "graph": float(parts[2]),
            }
            summary["rag_index"]["weights"] = weights
        else:
            raise ValueError(
                f"--weights must be 3 comma-separated floats, got: {args.weights}"
            )

    if args.mode in {"rag", "all"} and retriever is not None:
        summary["retrieval"] = evaluate_retrieval(
            cases=cases,
            retriever=retriever,
            top_k=args.top_k,
            per_source=args.per_source,
            query_mode=args.query_mode,
            rrf_k=args.rrf_k,
            weights=weights,
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
                weights=weights,
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
                weights=weights,
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
