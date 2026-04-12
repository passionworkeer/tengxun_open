"""evaluation — RAG retrieval evaluation framework."""

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
