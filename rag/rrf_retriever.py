"""
HybridRetriever main class.

Public API:
    HybridRetriever, build_retriever
    rrf_fuse, rrf_fuse_weighted (re-exported from fusion for backward compat)

Internal submodules:
    fusion    — RRF fusion + shared data structures + helpers
    indexes   — BM25, embedding, TF-IDF index implementations
    graph     — Graph search + symbol registry
"""

from __future__ import annotations

import logging
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from .ast_chunker import (
    CodeChunk,
    chunk_repository,
    normalize_symbol_target,
)
from .fusion import (
    RankedResult,
    RetrievalHit,
    RetrievalTrace,
    rrf_fuse,
    rrf_fuse_weighted,
    _kind_bonus,
    _looks_like_fqn,
    _tokenize,
    _extract_string_literals,
    _extract_symbol_like_strings,
)

# Re-export dataclasses for backward compat
__all__ = [
    "HybridRetriever",
    "build_retriever",
    "RankedResult",
    "RetrievalHit",
    "RetrievalTrace",
    "rrf_fuse",
    "rrf_fuse_weighted",
]
from .graph import _entry_file_to_module, graph_search
from .indexes import _BM25Index, _EmbeddingIndex

_logger = logging.getLogger(__name__)

_APPROX_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / _APPROX_CHARS_PER_TOKEN)) if text else 0


def _truncate_to_token_budget(text: str, remaining_tokens: int) -> str:
    if remaining_tokens <= 0:
        return ""
    remaining_chars = max(0, remaining_tokens * _APPROX_CHARS_PER_TOKEN)
    if len(text) <= remaining_chars:
        return text
    if remaining_chars <= 3:
        return text[:remaining_chars]
    return text[: remaining_chars - 3].rstrip() + "..."


class HybridRetriever:
    """
    混合检索器

    整合 BM25、语义检索和图检索三种方式，
    使用 RRF 融合各来源的结果。

    索引构建：
    1. 符号到chunk_id的映射
    2. 模块到chunk_id的映射
    3. 基础名到chunk_id的映射（用于短名称匹配）
    4. 父符号到chunk_id的映射（用于类方法）
    5. BM25索引
    6. 语义索引（TF-IDF + 字符n-gram）
    7. 依赖图
    """

    def __init__(self, chunks: Sequence[CodeChunk]) -> None:
        self.chunks = list(chunks)
        self.chunk_by_id = {chunk.chunk_id: chunk for chunk in self.chunks}
        self._chunk_registry: dict[str, CodeChunk] = dict(self.chunk_by_id)
        self.symbol_to_ids: dict[str, list[str]] = defaultdict(list)
        self.module_to_ids: dict[str, list[str]] = defaultdict(list)
        self.basename_to_ids: dict[str, list[str]] = defaultdict(list)
        self.parent_to_ids: dict[str, list[str]] = defaultdict(list)
        self.chunk_tokens: dict[str, list[str]] = {}

        for chunk in self.chunks:
            self.symbol_to_ids[chunk.symbol].append(chunk.chunk_id)
            self.module_to_ids[chunk.module].append(chunk.chunk_id)
            if chunk.symbol:
                self.basename_to_ids[chunk.symbol.rsplit(".", 1)[-1]].append(
                    chunk.chunk_id
                )
            if chunk.parent_symbol:
                self.parent_to_ids[chunk.parent_symbol].append(chunk.chunk_id)
            token_text = " ".join(
                [
                    chunk.symbol,
                    chunk.signature,
                    chunk.content,
                    " ".join(chunk.imports),
                    " ".join(chunk.string_targets),
                    " ".join(chunk.references),
                ]
            )
            self.chunk_tokens[chunk.chunk_id] = _tokenize(token_text)

        self._bm25 = _BM25Index(self.chunk_tokens, self._chunk_registry)
        self._semantic = _EmbeddingIndex(self.chunks)
        self._build_graph()

    @classmethod
    def from_repo(cls, repo_root: Path | str) -> "HybridRetriever":
        """Create a retriever by chunking the entire repository at *repo_root*.

        This is a convenience factory that runs :func:`chunk_repository
        <celestial.ast_chunker.chunk_repository>` on the given root and
        passes the resulting chunk list to :meth:`__init__`.

        Args:
            repo_root: Root directory of the source repository to index.

        Returns:
            A fully-initialised :class:`HybridRetriever` instance with
            BM25, semantic, and graph indexes built.
        """
        return cls(chunk_repository(Path(repo_root)))

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
        """Return the top-*top_k* fused retrieval hits for the given question.

        This is a convenience wrapper around :meth:`retrieve_with_trace` that
        discards per-source rankings and returns only the fused hits.

        Args:
            question: Natural-language question string.
            entry_symbol: Optional fully-qualified symbol name that is the
                entry point of the query (provides context for graph search).
            entry_file: Optional source file path to anchor the query.
            top_k: Maximum number of fused hits to return.
            per_source: Maximum candidates pulled from each individual index
                (BM25, semantic, graph) before fusion.
            query_mode: Controls how *entry_symbol* and *entry_file* are mixed
                into the query text passed to BM25 and semantic index.
                ``"question_only"`` ignores them; ``"question_plus_entry"``
                (default) includes them.
            rrf_k: Reciprocal Rank Fusion constant. Higher values reduce the
                influence of rank position (default 30).
            weights: Optional per-source weight dict for
                :func:`rrf_fuse_weighted`. If ``None``, unweighted RRF is used.

        Returns:
            List of :class:`RetrievalHit` objects ordered by fused score,
            highest first, up to *top_k* items.
        """
        return list(
            self.retrieve_with_trace(
                question=question,
                entry_symbol=entry_symbol,
                entry_file=entry_file,
                top_k=top_k,
                per_source=per_source,
                query_mode=query_mode,
                rrf_k=rrf_k,
                weights=weights,
            ).fused
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
        """Execute retrieval and return a full :class:`RetrievalTrace`.

        Runs all three indexes (BM25, semantic, graph) independently,
        applies RRF fusion, and materialises the top *top_k* hits.

        Args:
            question: Natural-language question string.
            entry_symbol: Optional entry-point symbol name (passed to graph search).
            entry_file: Optional entry file path (passed to graph search).
            top_k: Maximum fused hits in the returned trace.
            per_source: Candidates per index before fusion.
            query_mode: Query construction mode; see :meth:`retrieve`.
            rrf_k: RRF constant; see :meth:`retrieve`.
            weights: Optional per-source weights; see :meth:`retrieve`.

        Returns:
            A :class:`RetrievalTrace` containing per-source ranked IDs,
            fused IDs, and fully-materialised :class:`RetrievalHit` objects.
        """
        query_text = self._build_query_text(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            query_mode=query_mode,
        )
        bm25_ranked = self._bm25.search(query_text, top_n=per_source)
        semantic_ranked = self._semantic.search(query_text, top_n=per_source)
        graph_ranked = self._graph_search(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_n=per_source,
            query_mode=query_mode,
        )
        rankings = {
            "bm25": bm25_ranked,
            "semantic": semantic_ranked,
            "graph": graph_ranked,
        }
        if weights:
            fused = rrf_fuse_weighted(rankings, weights, k=rrf_k)
        else:
            fused = rrf_fuse(rankings, k=rrf_k)
        fused_ids = tuple(result.item_id for result in fused)
        hits: list[RetrievalHit] = []
        for result in fused[:top_k]:
            chunk = self.chunk_by_id[result.item_id]
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    symbol=chunk.symbol,
                    repo_path=chunk.repo_path,
                    kind=chunk.kind,
                    score=result.score,
                    source=tuple(result.source.split(",")) if result.source else (),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=self._render_chunk(chunk, rank=len(hits) + 1),
                )
            )
        return RetrievalTrace(
            bm25=tuple(bm25_ranked),
            semantic=tuple(semantic_ranked),
            graph=tuple(graph_ranked),
            fused_ids=fused_ids,
            fused=tuple(hits),
        )

    def build_context(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 5,
        per_source: int = 12,
        query_mode: str = "question_plus_entry",
        rrf_k: int = 30,
        weights: dict[str, float] | None = None,
        max_context_tokens: int = 4096,
    ) -> str:
        """Build an LLM-ready context string by fusing and truncating retrieval results.

        Executes :meth:`retrieve_with_trace`, then formats each hit into a
        annotated section and concatenates them. Sections are added in rank
        order until the token budget (*max_context_tokens*) is exhausted,
        at which point the last section is truncated or a sentinel message
        is appended.

        Args:
            question: Natural-language question string.
            entry_symbol: Optional entry-point symbol name.
            entry_file: Optional entry file path.
            top_k: Maximum hits to consider.
            per_source: Candidates per index before fusion.
            query_mode: Query construction mode; see :meth:`retrieve`.
            rrf_k: RRF constant; see :meth:`retrieve`.
            weights: Optional per-source weights; see :meth:`retrieve`.
            max_context_tokens: Hard budget for the output string, in
                approximate tokens (chars / 4). Truncation happens at section
                boundaries.

        Returns:
            A formatted multi-section string, each section prefixed with
            ``[Retrieved N] {symbol} ({location}) | source={...}`` and separated
            by blank lines.
        """
        trace = self.retrieve_with_trace(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )
        sections: list[str] = []
        used_tokens = 0
        for rank, hit in enumerate(trace.fused, start=1):
            location = f"{hit.repo_path}:{hit.start_line}-{hit.end_line}"
            source = ", ".join(hit.source) if hit.source else "fused"
            section = (
                f"[Retrieved {rank}] {hit.symbol} ({location}) | source={source}\n"
                f"{hit.snippet}"
            )
            section_tokens = _estimate_tokens(section)
            if used_tokens + section_tokens <= max_context_tokens:
                sections.append(section)
                used_tokens += section_tokens
                continue

            remaining_tokens = max_context_tokens - used_tokens
            if remaining_tokens <= 0:
                sections.append("[Context budget exhausted] Remaining retrieved chunks omitted.")
                break

            suffix = "\n[Truncated to fit context budget]"
            suffix_tokens = _estimate_tokens(suffix)
            body_budget = max(0, remaining_tokens - suffix_tokens)
            truncated = _truncate_to_token_budget(section, body_budget)
            if truncated:
                sections.append(f"{truncated}{suffix}")
            else:
                sections.append("[Context budget exhausted] Remaining retrieved chunks omitted.")
            break

        return "\n\n".join(sections)

    def expand_candidate_fqns(
        self,
        hits: Sequence[RetrievalHit],
        query_text: str = "",
        entry_symbol: str = "",
    ) -> list[str]:
        """Expand a list of retrieval hits into candidate FQN strings.

        This is used by downstream callers that need to resolve which
        fully-qualified names are relevant to a query. Candidates are
        harvested from each hit's symbol, string targets, imports, and
        code references, then scored by overlap with the query tokens and
        position in the hit list.

        Args:
            hits: Retrieval hits to expand. Typically from :meth:`retrieve`.
            query_text: Original query text; used to compute token overlap.
            entry_symbol: Entry symbol; hits whose FQN ends with this tail
                receive a positional bonus.

        Returns:
            Deduplicated, score-ordered list of FQN strings, highest score first.
        """
        query_tokens = set(_tokenize(query_text))
        entry_tail = entry_symbol.rsplit(".", 1)[-1] if entry_symbol else ""
        scored: dict[str, float] = {}
        for index, hit in enumerate(hits, start=1):
            chunk = self.chunk_by_id[hit.chunk_id]
            candidates: list[tuple[str, float]] = [(chunk.symbol, 0.2)]
            candidates.extend((target, 0.35) for target in chunk.string_targets)
            candidates.extend(
                (target, 0.15) for target in chunk.imports if _looks_like_fqn(target)
            )
            for reference in chunk.references:
                for candidate_id in self._resolve_reference_ids(
                    chunk, normalize_symbol_target(reference)
                ):
                    candidates.append((self.chunk_by_id[candidate_id].symbol, 0.25))
            for candidate, bonus in candidates:
                normalized = normalize_symbol_target(candidate)
                if not _looks_like_fqn(normalized):
                    continue
                overlap = len(query_tokens & set(_tokenize(normalized)))
                tail_bonus = (
                    1.2 if entry_tail and normalized.endswith(f".{entry_tail}") else 0.0
                )
                score = hit.score + (1.0 / index) + bonus + overlap * 0.3 + tail_bonus
                scored[normalized] = max(scored.get(normalized, 0.0), score)
        return [
            candidate
            for candidate, _ in sorted(
                scored.items(), key=lambda item: item[1], reverse=True
            )
        ]

    def ranked_symbols(self, chunk_ids: Sequence[str]) -> list[str]:
        """Extract deduplicated symbols from *chunk_ids* in the same order.

        Looks up each chunk ID in the registry and appends its
        :attr:`CodeChunk.symbol` to the result list. Empty symbols,
        duplicates (by exact match), and missing chunk IDs are all skipped.

        Args:
            chunk_ids: Sequence of chunk identifiers, typically from
                :attr:`RetrievalTrace.fused_ids` or :attr:`RetrievalTrace.bm25`.

        Returns:
            List of unique, non-empty symbol strings in the order they
            first appear in *chunk_ids*.
        """
        symbols: list[str] = []
        seen: set[str] = set()
        for chunk_id in chunk_ids:
            chunk = self.chunk_by_id.get(chunk_id)
            if chunk is None or not chunk.symbol or chunk.symbol in seen:
                continue
            seen.add(chunk.symbol)
            symbols.append(chunk.symbol)
        return symbols

    def materialize_hits(
        self,
        chunk_ids: Sequence[str],
        source: str,
        top_k: int | None = None,
    ) -> list[RetrievalHit]:
        """Convert a sequence of chunk IDs into fully-materialised :class:`RetrievalHit` objects.

        Each chunk is looked up, wrapped in a :class:`RetrievalHit` with a
        score of ``1 / rank``, the given *source* tag, and a tiered snippet.

        Args:
            chunk_ids: Chunk IDs to materialise. May contain IDs that are not
                in the registry; those are silently skipped.
            source: String label identifying the source that produced these
                IDs (e.g. ``"graph"``, ``"path_indexer"``).
            top_k: Optional cap on the number of hits returned. If ``None``,
                all *chunk_ids* are processed.

        Returns:
            List of :class:`RetrievalHit` objects in the same order as the
            (possibly truncated) input.
        """
        selected_ids = chunk_ids[:top_k] if top_k is not None else chunk_ids
        hits: list[RetrievalHit] = []
        for rank, chunk_id in enumerate(selected_ids, start=1):
            chunk = self.chunk_by_id[chunk_id]
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    symbol=chunk.symbol,
                    repo_path=chunk.repo_path,
                    kind=chunk.kind,
                    score=1.0 / rank,
                    source=(source,),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=self._render_chunk(chunk, rank=rank),
                )
            )
        return hits

    def expand_candidate_fqns_from_chunk_ids(
        self,
        chunk_ids: Sequence[str],
        source: str,
        query_text: str = "",
        entry_symbol: str = "",
    ) -> list[str]:
        """Convenience composition of :meth:`materialize_hits` and :meth:`expand_candidate_fqns`.

        Materialises *chunk_ids* into hits, then expands them to candidate
        FQN strings. This is the typical entry point when a caller only has
        chunk IDs (e.g. from a raw index result) rather than a
        :class:`RetrievalHit` sequence.

        Args:
            chunk_ids: Chunk IDs to materialise.
            source: Source label passed to :meth:`materialize_hits`.
            query_text: Passed to :meth:`expand_candidate_fqns`.
            entry_symbol: Passed to :meth:`expand_candidate_fqns`.

        Returns:
            Score-ordered list of FQN strings.
        """
        hits = self.materialize_hits(chunk_ids=chunk_ids, source=source)
        return self.expand_candidate_fqns(
            hits,
            query_text=query_text,
            entry_symbol=entry_symbol,
        )

    # ── Fast dict-based graph ────────────────────────────────────────

    def _build_graph(self) -> None:
        self._graph: dict[str, list[str]] = {c.chunk_id: [] for c in self.chunks}

        for chunk in self.chunks:
            # module siblings
            for sibling_id in self.module_to_ids.get(chunk.module, []):
                if sibling_id != chunk.chunk_id:
                    self._graph[chunk.chunk_id].append(sibling_id)
                    self._graph.setdefault(sibling_id, []).append(chunk.chunk_id)
            # import targets
            self._connect_targets(chunk.chunk_id, chunk.imports)
            # string targets
            self._connect_targets(chunk.chunk_id, chunk.string_targets)
            # code references
            self._connect_references(chunk)

    def _connect_targets(self, source_id: str, targets: Iterable[str]) -> None:
        for target in targets:
            normalized = normalize_symbol_target(target)
            for candidate_id in self._resolve_target_ids(normalized):
                if source_id != candidate_id:
                    self._graph.setdefault(source_id, []).append(candidate_id)

    def _connect_references(self, chunk: CodeChunk) -> None:
        for reference in chunk.references:
            normalized = normalize_symbol_target(reference)
            for candidate_id in self._resolve_reference_ids(chunk, normalized):
                if chunk.chunk_id != candidate_id:
                    self._graph.setdefault(chunk.chunk_id, []).append(candidate_id)

    def _resolve_target_ids(self, target: str) -> list[str]:
        if target in self.symbol_to_ids:
            return list(self.symbol_to_ids[target])
        if target in self.module_to_ids:
            return list(self.module_to_ids[target])
        base = target.rsplit(".", 1)[-1]
        return list(self.basename_to_ids.get(base, []))

    def _resolve_reference_ids(self, chunk: CodeChunk, reference: str) -> list[str]:
        if reference in self.symbol_to_ids:
            return list(self.symbol_to_ids[reference])
        if reference in self.module_to_ids:
            return list(self.module_to_ids[reference])

        base = reference.rsplit(".", 1)[-1]
        candidates: list[str] = []

        if chunk.parent_symbol:
            for candidate_id in self.parent_to_ids.get(chunk.parent_symbol, []):
                candidate = self.chunk_by_id[candidate_id]
                if candidate.symbol.endswith(f".{base}"):
                    candidates.append(candidate_id)

        module_candidate = f"{chunk.module}.{base}"
        if module_candidate in self.symbol_to_ids:
            candidates.extend(self.symbol_to_ids[module_candidate])

        if not candidates:
            candidates.extend(self.basename_to_ids.get(base, []))

        return list(dict.fromkeys(candidates))

    def _build_query_text(
        self,
        question: str,
        entry_symbol: str,
        entry_file: str,
        query_mode: str,
    ) -> str:
        if query_mode == "question_only":
            return question.strip()
        if query_mode != "question_plus_entry":
            raise ValueError(f"Unsupported query mode: {query_mode}")
        return " ".join(
            part
            for part in (question.strip(), entry_symbol.strip(), entry_file.strip())
            if part
        )

    def _graph_search(
        self,
        question: str,
        entry_symbol: str,
        entry_file: str,
        top_n: int,
        query_mode: str,
    ) -> list[str]:
        return graph_search(
            graph=self._graph,
            chunk_by_id=self.chunk_by_id,
            symbol_to_ids=self.symbol_to_ids,
            module_to_ids=self.module_to_ids,
            basename_to_ids=self.basename_to_ids,
            parent_to_ids=self.parent_to_ids,
            chunk_tokens=self.chunk_tokens,
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_n=top_n,
            query_mode=query_mode,
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )

    # ── Tiered context rendering ────────────────────────────────────

    def _render_chunk(self, chunk: CodeChunk, rank: int) -> str:
        """Tiered rendering per plan:
        - Top-1: full code content
        - Top-2~5: signature + docstring + imports (compressed)
        - Beyond: summary only
        """
        if rank == 1:
            return chunk.content

        lines = [chunk.signature]
        if chunk.docstring:
            lines.append(f'Docstring: "{chunk.docstring.splitlines()[0]}"')
        if chunk.imports:
            lines.append("Imports: " + ", ".join(chunk.imports[:6]))
        if chunk.string_targets:
            lines.append("String targets: " + ", ".join(chunk.string_targets[:6]))
        if chunk.references:
            lines.append("References: " + ", ".join(chunk.references[:6]))

        if rank <= 5:
            return "\n".join(lines)

        # rank > 5: summary only
        return "\n".join(lines[:2])


def build_retriever(repo_root: Path | str) -> HybridRetriever:
    return HybridRetriever.from_repo(repo_root)
