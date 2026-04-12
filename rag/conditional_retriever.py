"""
Conditional RAG retriever.

Only enables full RAG retrieval for Hard/Type A/Type E cases.
Easy/Medium cases bypass RAG for speed.

Exports:
    ConditionalRetriever
    classify_question_type
    should_use_rag
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .fusion import (
    RankedResult,
    RetrievalHit,
    RetrievalTrace,
    rrf_fuse,
    rrf_fuse_weighted,
)
from .rrf_retriever import HybridRetriever

# ---------------------------------------------------------------------------
# Question classification patterns
# ---------------------------------------------------------------------------

# Hard/Type E: dynamic symbol resolution, alias chains, string-based targets
_TYPE_E_PATTERNS = [
    re.compile(r"symbol_by_name|by_name\(|import_object|config_from_object", re.I),
    re.compile(r"LOADER_ALIASES|BACKEND_ALIASES|ALIASES\[", re.I),
    re.compile(r"loader.*default|default.*loader", re.I),
    re.compile(r"strategy.*default|default.*strategy", re.I),
    re.compile(r"task\.Request|task\.Strategy", re.I),
    re.compile(r"symbol.*resolution|resolve.*to", re.I),
    re.compile(r"最终|real class|real function|最终解析", re.I),
    re.compile(r"django.*fixup|fixup|django.*task", re.I),
]

# Hard/Type B: decorator flows, shared_task, proxy, finalize callbacks
_TYPE_B_PATTERNS = [
    re.compile(r"@shared_task|@app\.task|shared_task|shared-task", re.I),
    re.compile(r"decorator|register|registration|register.*task", re.I),
    re.compile(r"Proxy|autofinalize|finalize.*callback|finalize.*callback", re.I),
    re.compile(r"builtin_finalize|finalize.*builtin", re.I),
    re.compile(r"task.*from.*fun|_task_from_fun", re.I),
    re.compile(r"celery\.app\.shared_task|celery\.app\.Celery.*task", re.I),
]

# Hard/Type A: lifecycle, bootstep, conditional include, signals
_TYPE_A_PATTERNS = [
    re.compile(r"autodiscover|signal|import_modules|import.*modules", re.I),
    re.compile(r"include_if|include|bootstep|step.*lifecycle", re.I),
    re.compile(r"PersistentScheduler|beat\.py|store\.clear", re.I),
    re.compile(r"disable_prefetch|can_consume|qos|channel_qos", re.I),
    re.compile(r"failure.*matrix|acks_late|on_failure|on_timeout", re.I),
    re.compile(r"WorkerLostError|TimeLimitExceeded", re.I),
]

# Hard/Type D: parameter shadowing, string targets, name confusion
_TYPE_D_PATTERNS = [
    re.compile(r"parameter.*shadow|shadow.*parameter|router.*string", re.I),
    re.compile(r"expand_router|RouterClass|register_type", re.I),
    re.compile(r"_chain|chain.*vs|registered.*class|subclass.*instance", re.I),
    re.compile(r"inline.*import|lazy.*import|import.*inside", re.I),
    re.compile(r"subtask|maybe_subtask|signature", re.I),
    re.compile(r"celery\.canvas\.(subtask|maybe_subtask)", re.I),
]

# Easy indicators: simple re-export, top-level, delegation
_EASY_PATTERNS = [
    re.compile(r"^Which real class does.*resolve.*\?$"),
    re.compile(r"^Which real function does.*\?$"),
    re.compile(r"^The.*real class.*FQN.*\?$"),
    re.compile(r"^.*top-level.*lazy.*API.*\?$"),
    re.compile(r"^From.*class.*definition.*view.*\?$"),
    re.compile(r"^顶层符号.*\?$"),
    re.compile(r"top.level|re-export|re_export|celery\.[A-Z][a-z]+", re.I),
    re.compile(r"re-exports|thin wrapper|delegat", re.I),
]

# Difficulty level keywords
_IMPLICIT_LEVEL_KEYWORDS = {
    4: {
        "autodiscover", "finalize", "shared_task", "symbol_by_name", "Proxy",
        "router_string", "parameter_shadow", "builtin", "signal_chain",
        "django_fixup", "loader_smart",
    },
    5: {
        "autodiscover", "failure_matrix", "acks_late", "disable_prefetch",
        "persistent_scheduler", "config_from_object",
    },
}


@dataclass(frozen=True)
class QuestionClassification:
    """Result of question classification."""

    difficulty: str  # "easy" | "medium" | "hard"
    failure_type: str  # "Type A" | "Type B" | "Type C" | "Type D" | "Type E" | ""
    signals: tuple[str, ...]  # which signal patterns matched
    rag_recommended: bool
    reason: str


def classify_question_type(
    question: str,
    entry_symbol: str = "",
    entry_file: str = "",
    difficulty_hint: str = "",
) -> QuestionClassification:
    """
    Classify a question to determine if RAG is needed.

    Returns a QuestionClassification with:
    - difficulty: estimated difficulty
    - failure_type: estimated failure_type (Type A-E)
    - signals: which patterns matched
    - rag_recommended: whether to use full RAG
    - reason: human-readable reason
    """
    combined = " ".join(part for part in (question, entry_symbol, entry_file) if part)

    signals: list[str] = []

    for pattern in _TYPE_E_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeE:{pattern.pattern[:30]}")
    for pattern in _TYPE_B_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeB:{pattern.pattern[:30]}")
    for pattern in _TYPE_A_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeA:{pattern.pattern[:30]}")
    for pattern in _TYPE_D_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeD:{pattern.pattern[:30]}")

    # Count implicit-level keywords
    level_4_count = sum(1 for kw in _IMPLICIT_LEVEL_KEYWORDS[4] if kw.lower() in combined.lower())
    level_5_count = sum(1 for kw in _IMPLICIT_LEVEL_KEYWORDS[5] if kw.lower() in combined.lower())

    easy_match_count = sum(1 for p in _EASY_PATTERNS if p.search(question))

    # Determine failure type from signals
    failure_type = ""
    if any(s.startswith("TypeA") for s in signals):
        failure_type = "Type A"
    elif any(s.startswith("TypeB") for s in signals):
        failure_type = "Type B"
    elif any(s.startswith("TypeD") for s in signals):
        failure_type = "Type D"
    elif any(s.startswith("TypeE") for s in signals):
        failure_type = "Type E"

    # Determine difficulty
    if difficulty_hint:
        difficulty = difficulty_hint
    elif level_5_count > 0 or len(signals) >= 3:
        difficulty = "hard"
    elif level_4_count > 0 or len(signals) >= 1:
        difficulty = "hard"
    elif easy_match_count >= 1:
        difficulty = "easy"
    else:
        difficulty = "medium"

    # RAG recommendation
    rag_recommended = difficulty in ("hard", "medium")

    # Reason string
    if difficulty == "hard":
        reason = f"Hard case detected ({failure_type or 'untyped'}), multi-hop resolution needed"
    elif difficulty == "medium":
        reason = f"Medium case ({failure_type or 'untyped'}), partial RAG helpful"
    else:
        reason = "Easy case, simple re-export pattern, RAG optional"

    return QuestionClassification(
        difficulty=difficulty,
        failure_type=failure_type,
        signals=tuple(signals),
        rag_recommended=rag_recommended,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# ConditionalRetriever
# ---------------------------------------------------------------------------


class ConditionalRetriever:
    """
    Conditional RAG retriever wrapper.

    Wraps a HybridRetriever and automatically decides whether to enable
    full RAG based on question classification.

    Usage:
        retriever = ConditionalRetriever.from_repo("external/celery")
        if retriever.should_use_rag("Which real class does ... resolve to?"):
            hits = retriever.retrieve(question, ...)
        else:
            # fast path: symbol-only or pre-computed answer
            hits = retriever.fast_path(question, ...)
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        *,
        hard_requires_rag: bool = True,
        medium_requires_rag: bool = False,
    ) -> None:
        self._hybrid = hybrid_retriever
        self.hard_requires_rag = hard_requires_rag
        self.medium_requires_rag = medium_requires_rag

    @classmethod
    def from_repo(
        cls,
        repo_root: Path | str,
        **kwargs,
    ) -> "ConditionalRetriever":
        """Factory: build from repo root."""
        hybrid = HybridRetriever.from_repo(repo_root)
        return cls(hybrid, **kwargs)

    # ------------------------------------------------------------------
    # Classification API
    # ------------------------------------------------------------------

    def classify(self, question: str, **kwargs) -> QuestionClassification:
        """Classify a question (delegates to classify_question_type)."""
        return classify_question_type(question, **kwargs)

    def should_use_rag(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        difficulty_hint: str = "",
    ) -> bool:
        """
        Decide whether to enable full RAG for this question.

        Returns True for Hard/Type A/Type E cases.
        Returns False for Easy cases (fast path).
        """
        classification = classify_question_type(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            difficulty_hint=difficulty_hint,
        )
        return classification.rag_recommended

    # ------------------------------------------------------------------
    # Fast-path (no RAG)
    # ------------------------------------------------------------------

    def fast_path(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 3,
    ) -> list[str]:
        """
        Fast path for easy questions: symbol-only lookup without full RAG.

        Returns up to top_k chunk_ids by direct symbol/module matching.
        This is a quick pre-filter before any full retrieval.
        """
        from .fusion import _extract_symbol_like_strings, _tokenize

        question_tokens = set(_tokenize(question))
        candidates: list[tuple[float, str]] = []

        # Direct symbol match
        for symbol, chunk_ids in self._hybrid.symbol_to_ids.items():
            symbol_tokens = set(_tokenize(symbol))
            overlap = len(question_tokens & symbol_tokens)
            if overlap > 0:
                for chunk_id in chunk_ids:
                    candidates.append((overlap * 2.0, chunk_id))

        # Module match
        module_query = entry_file.replace("/", ".").replace("\\", ".")
        if module_query:
            for chunk_id in self._hybrid.module_to_ids.get(module_query, []):
                candidates.append((1.5, chunk_id))

        # Sort and dedupe
        candidates.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        result: list[str] = []
        for score, chunk_id in candidates:
            if chunk_id not in seen:
                seen.add(chunk_id)
                result.append(chunk_id)
                if len(result) >= top_k:
                    break

        return result

    # ------------------------------------------------------------------
    # Full retrieval (delegates to HybridRetriever)
    # ------------------------------------------------------------------

    def retrieve(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 5,
        per_source: int = 12,
        query_mode: str = "question_plus_entry",
        rrf_k: int = 30,
        weights: dict[str, float] | None = None,
    ) -> list[RetrievalHit]:
        """Full RAG retrieval (always uses HybridRetriever)."""
        return self._hybrid.retrieve(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )

    def retrieve_with_trace(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 5,
        per_source: int = 12,
        query_mode: str = "question_plus_entry",
        rrf_k: int = 30,
        weights: dict[str, float] | None = None,
    ) -> RetrievalTrace:
        """Full RAG retrieval with trace."""
        return self._hybrid.retrieve_with_trace(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )

    def smart_retrieve(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        difficulty_hint: str = "",
        top_k: int = 5,
        per_source: int = 12,
        query_mode: str = "question_plus_entry",
        rrf_k: int = 30,
        weights: dict[str, float] | None = None,
    ) -> tuple[list[RetrievalHit], QuestionClassification]:
        """
        Smart retrieval: automatically chooses fast or full RAG path.

        Returns (hits, classification) tuple.
        """
        classification = classify_question_type(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            difficulty_hint=difficulty_hint,
        )

        if not classification.rag_recommended:
            # Fast path: symbol-only
            fast_ids = self.fast_path(
                question=question,
                entry_symbol=entry_symbol,
                entry_file=entry_file,
                top_k=top_k,
            )
            return self._hybrid.materialize_hits(
                chunk_ids=fast_ids, source="fast_path", top_k=top_k
            ), classification

        # Full RAG path
        hits = self.retrieve(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )
        return hits, classification

    def build_context(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        difficulty_hint: str = "",
        top_k: int = 5,
        per_source: int = 12,
        query_mode: str = "question_plus_entry",
        rrf_k: int = 30,
        weights: dict[str, float] | None = None,
        max_context_tokens: int = 4096,
    ) -> str:
        """Build context using smart retrieval."""
        hits, classification = self.smart_retrieve(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            difficulty_hint=difficulty_hint,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )
        sections: list[str] = []
        if not classification.rag_recommended:
            sections.append("[Fast path: easy case, RAG bypassed]")
        for rank, hit in enumerate(hits, start=1):
            location = f"{hit.repo_path}:{hit.start_line}-{hit.end_line}"
            source = ", ".join(hit.source) if hit.source else "fused"
            sections.append(
                f"[Retrieved {rank}] {hit.symbol} ({location}) | source={source}\n"
                f"{hit.snippet}"
            )
        return "\n\n".join(sections)
