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

# Hard/Type E: dynamic symbol resolution via ALIASES, symbol_by_name, instantiate.
_TYPE_E_PATTERNS = [
    # "real class does celery.X resolve to" pattern - runtime resolution chain
    re.compile(r"(resolve|real|actual) (class|function) does celery\.[A-Za-z]", re.I),
    re.compile(r"symbol_by_name", re.I),
    re.compile(r"import_object\s*\(|instantiate\s*\(", re.I),
    re.compile(r"config_from_object\s*\(", re.I),
    re.compile(r"load_extension_classes\s*\(", re.I),
    re.compile(r"find_app\s*\(", re.I),
    re.compile(r"LOADER_ALIASES|BACKEND_ALIASES|ALIASES\[", re.I),
    re.compile(r"get_loader_cls\s*\(", re.I),
    re.compile(r"by_name\s*\(|loader_cls", re.I),
    re.compile(r"task\.Request|task\.Strategy", re.I),
    re.compile(r"django.*fixup|django.*task", re.I),
    re.compile(r"current_app\.loader", re.I),
    re.compile(r"result_backend\s*=|CELERY_CUSTOM_WORKER_POOL", re.I),
    re.compile(r"builtin_fixups|_get_backend|_get_current_app", re.I),
    re.compile(r"解析成真实类|解析为真实类", re.I),
    re.compile(r"最终解析到.*真实|真实.*最终解析到", re.I),
    re.compile(r"真实 Celery|真实函数符号", re.I),
    re.compile(r"symbol_by_name.*最终解析|instantiate.*最终解析|解析成真实", re.I),
    re.compile(r"celery\.utils\.(imports|functional|collections)\..*解析", re.I),
    re.compile(r"symbol_by_name.*celery\.utils|celery\.utils.*symbol_by_name", re.I),
    re.compile(r"instantiate.*celery\.utils|celery\.utils.*instantiate", re.I),
    re.compile(r"config_from_object.*无法|无法.*config_from_object|obj.*无法.*模块导入", re.I),
    re.compile(r"find_app.*获取|无法.*find_app|symbol.*find_app", re.I),
    re.compile(r"head_from_fun.*生成|生成.*head_from_fun", re.I),
    re.compile(r"cwd_in_path.*__enter__|__enter__.*cwd_in_path|当前工作目录.*import|import.*当前工作目录", re.I),
    re.compile(r"celery\.utils\..*调用链|调用链.*celery\.utils", re.I),
    re.compile(r"解析.*真实|真实.*解析|哪个真实.*类|真实.*Celery.*类", re.I),
    re.compile(r"最终.*哪个.*函数|最终.*哪个.*类|哪个.*最终.*解析", re.I),
    re.compile(r"importlib.*import_module|importlib_import", re.I),
    re.compile(r"load_extension_classes|entry_points.*package:class", re.I),
    re.compile(r"result_from_tuple|READY_STATES", re.I),
    re.compile(r"kombu.*symbol_by_name|symbol_by_name.*kombu", re.I),
    re.compile(r"builtin_fixups.*fixup|fixup.*真实函数|resolve.*builtin_fixups", re.I),
    re.compile(r"AsyncResult.*backend|self\.app\.backend", re.I),
    re.compile(r"maybe_evaluate.*lazy|lazy.*maybe_evaluate|maybe_evaluate.*proxy", re.I),
    re.compile(r"ensure_chords_allowed|chords_allowed", re.I),
    re.compile(r"current_app.*loader|loader.*current_app", re.I),
    re.compile(r"最终.*哪个函数|最终.*哪个类|which function ultimately", re.I),
]


# Hard/Type C: lazy re-export / __getattr__ delegation in celery top-level API.
# Key: Type C is about knowing the structure, NOT about runtime resolution (resolve/to -> Type E)
_TYPE_C_PATTERNS = [
    re.compile(r"Which real (class|function) does.*shared_task", re.I),
    re.compile(r"Which real (class|function) does [`'](celery\.[a-z_])", re.I),
    re.compile(r"\bre-export\b|\breexport\b|\b__getattr__\b|\b__all__\b", re.I),
    re.compile(r"delegate[s]?|delegat(es|ion)", re.I),
    re.compile(r"from celery\.canvas import|from celery\.app import", re.I),
    re.compile(r"顶层符号.*celery\.[A-Z]|celery\.[A-Z].*顶层符号", re.I),
    re.compile(r"哪个真实类.*celery\.[A-Z]|celery\.[A-Z].*哪个真实类", re.I),
    re.compile(r"真实类定义 FQN|真实类.*FQN|对应.*真实类.*FQN", re.I),
    re.compile(r"重新导出|委托给哪个|完整 FQN|完整.*FQN|哪个外部包", re.I),
    re.compile(r"import_from_cwd", re.I),
]

# Hard/Type B: decorator flows, shared_task, proxy, finalize callbacks
_TYPE_B_PATTERNS = [
    re.compile(r"@shared_task|@app\.task", re.I),
    re.compile(r"\bdecorator\b|autofinalize|finalize.*callback", re.I),
    re.compile(r"builtin_finalize|finalize.*builtin", re.I),
    re.compile(r"task.*from.*fun|_task_from_fun", re.I),
    re.compile(r"celery\.app\.shared_task|celery\.app\.Celery.*task", re.I),
    re.compile(r"celery\.current_app(?!\.loader)|celery\.current_task(?!\.loader)", re.I),
]


# Hard/Type A: lifecycle, bootstep, conditional include, signals
_TYPE_A_PATTERNS = [
    re.compile(r"autodiscover|signal|import_modules|import.*modules", re.I),
    re.compile(r"include_if|include|bootstep|step.*lifecycle", re.I),
    re.compile(r"PersistentScheduler|beat\.py|store\.clear", re.I),
    re.compile(r"disable_prefetch|can_consume|qos|channel_qos", re.I),
    re.compile(r"failure.*matrix|acks_late|on_failure|on_timeout", re.I),
    re.compile(r"WorkerLostError|TimeLimitExceeded", re.I),
    re.compile(r"importlib", re.I),
]


# Hard/Type D: parameter shadowing, naming confusion, type mismatches.
_TYPE_D_PATTERNS = [
    re.compile(r"register_type|RegisteredType|Signature\.TYPES", re.I),
    re.compile(r"chain\.__new__", re.I),
    re.compile(r"(chain|chord).*(vs|\bv\.).*(_chain|_chord)", re.I),
    re.compile(r"(internal|private).*(class|function).*(_chain|_chord)", re.I),
    re.compile(r"parameter.*shadow|shadow.*parameter", re.I),
    re.compile(r"type.*mismatch|mismatch.*type", re.I),
    re.compile(r"same.*name.*different.*type|different.*type.*same.*name", re.I),
    re.compile(r"inherits.*wrong|wrong.*base|base.*class.*different", re.I),
    re.compile(r"celery\.[a-z_]+\.(subtask|maybe_subtask)", re.I),
    re.compile(r"subtask.*=.*signature|maybe_subtask.*=.*maybe_signature", re.I),
    re.compile(r"subclass_with_self|Proxy.*type|type.*Proxy", re.I),
    re.compile(r"ConfigurationView.*ChainMap|ChainMap.*ConfigurationView", re.I),
    re.compile(r"哪个映射|层次映射|取哪个映射", re.I),
    re.compile(r"参数.*遮蔽|遮蔽.*参数|同名.*参数|参数.*同名", re.I),
    re.compile(r"内联.*import|inline.*import|函数体内.*import|from.*import.*函数体内", re.I),
    re.compile(r"Signature\.from_dict|Signature\.TYPES|注册到.*TYPES", re.I),
    re.compile(r"继承自.*标准库|inherits.*standard library|是什么类型的对象", re.I),
    re.compile(r"celery\.canvas\.Signature", re.I),
    re.compile(r"expand_router_string", re.I),
    re.compile(r"CELERY_CUSTOM_WORKER_POOL", re.I),
    re.compile(r"cwd_in_path", re.I),
    re.compile(r"get_implementation", re.I),
    re.compile(r"chain.*构造函数|构造函数.*chain|Signature.*合并|合并.*Signature", re.I),
    re.compile(r"from_dict.*分发|分发.*from_dict|from_dict.*子类|from_dict.*哪个类", re.I),
    re.compile(r"ConfigurationView.*__getitem__|NAMESPACES.*查找|查找.*NAMESPACES", re.I),
    re.compile(r"Timer.*Schedule.*Entry|Schedule.*Timer|Entry.*Timer", re.I),
]


# Easy indicators: simple re-export, top-level, delegation (MUST NOT match resolve/real class)
_EASY_PATTERNS = [
    re.compile(r"^Which real class does.*resolve.*\?$"),
    re.compile(r"^Which real function does.*\?$"),
    re.compile(r"^The.*real class.*FQN.*\?$"),
    re.compile(r"^From.*class.*definition.*view.*\?$"),
    re.compile(r"^顶层符号.*\?$"),
    re.compile(r"top.level|re-export|re_export", re.I),
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

    for pattern in _TYPE_A_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeA:{pattern.pattern[:30]}")
    for pattern in _TYPE_B_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeB:{pattern.pattern[:30]}")
    for pattern in _TYPE_C_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeC:{pattern.pattern[:30]}")
    for pattern in _TYPE_D_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeD:{pattern.pattern[:30]}")
    for pattern in _TYPE_E_PATTERNS:
        if pattern.search(combined):
            signals.append(f"TypeE:{pattern.pattern[:30]}")

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
    elif any(s.startswith("TypeC") for s in signals):
        failure_type = "Type C"
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
