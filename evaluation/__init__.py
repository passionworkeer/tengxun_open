"""RAG retrieval evaluation framework for cross-file Python dependency analysis.

This package provides end-to-end evaluation tooling for measuring how well
RAG-augmented language models resolve Celery source-code dependency chains.

Main exports
------------
main                : CLI entry point (baseline / rag / pe / all modes)
evaluate_retrieval  : Compute Recall@K / MRR for a given retriever on the eval set
RETRIEVAL_SOURCES   : Tuple of supported retrieval source names
EvalCase           : Frozen dataclass representing one evaluation case
load_eval_cases    : Load evaluation dataset from JSON (legacy_v1 or schema_v2)
load_fewshot_cases : Load few-shot examples (same loader, semantic distinction)
preview_prompt     : Render the fully assembled prompt for a single case
summarize_cases    : Produce a statistical summary of the loaded eval set

Evaluation workflow
-------------------
1. Load cases with ``load_eval_cases`` or ``load_fewshot_cases``.
2. (Optional) Preview prompts via ``preview_prompt``.
3. Evaluate retrieval quality with ``evaluate_retrieval``.
4. Run end-to-end model evaluation using the model-specific scripts:
   ``run_glm_eval.py``, ``run_gpt_eval.py``, ``run_qwen_eval.py``,
   or ``run_gpt_rag_eval.py`` for RAG vs. no-RAG comparison.
"""

from .baseline import main
from .evaluator import evaluate_retrieval, RETRIEVAL_SOURCES
from .loader import EvalCase, load_eval_cases, load_fewshot_cases
from .preview import preview_prompt
from .summarizer import summarize_cases

__all__ = [
    "main",
    "evaluate_retrieval",
    "RETRIEVAL_SOURCES",
    "EvalCase",
    "load_eval_cases",
    "load_fewshot_cases",
    "preview_prompt",
    "summarize_cases",
]
