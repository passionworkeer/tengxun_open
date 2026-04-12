"""
Prompt预览模块。

Exports:
    preview_prompt()
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from .loader import EvalCase


def preview_prompt(
    case: EvalCase,
    retriever,  # HybridRetriever
    top_k: int,
    per_source: int,
    prompt_module: ModuleType,
    query_mode: str,
    rrf_k: int = 30,
    weights: dict[str, float] | None = None,
) -> str:
    """
    预览组装后的prompt

    包含 system prompt、CoT模板、few-shot示例和用户问题。
    """
    context = retriever.build_context(
        question=case.question,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        top_k=top_k,
        per_source=per_source,
        query_mode=query_mode,
        rrf_k=rrf_k,
        weights=weights,
    )
    bundle = prompt_module.build_prompt_bundle(
        question=case.question,
        context=context,
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
    )
    return bundle.as_text()
