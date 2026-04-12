"""
HybridRetriever with DependencyPathIndexer integration.

Extends HybridRetriever by layering PathIndexer as a precision pre-filter
for Type E (dynamic symbol resolution) cases. PathIndexer provides exact
alias->FQN mappings that RRF alone cannot reliably find.

Architecture:
  1. Classify question type (Type E → PathIndexer path, else RRF)
  2. PathIndexer: exact alias lookup (precision-first)
  3. RRF: semantic + BM25 + graph (recall-first)
  4. Fusion: PathIndexer hits get RRF score boost OR direct answer context

Exports:
    HybridRetrieverWithPath
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .conditional_retriever import classify_question_type
from .dependency_path_indexer import DependencyPathIndexer, PathInfo
from .fusion import RetrievalHit, RetrievalTraceWithPath
from .rrf_retriever import HybridRetriever

__all__ = ["HybridRetrieverWithPath"]


# Score bonus applied to chunks whose FQN matches a PathIndexer resolved_fqn
_PATH_SCORE_BONUS = 15.0


class HybridRetrieverWithPath(HybridRetriever):
    """
    HybridRetriever augmented with DependencyPathIndexer for Type E questions.

    PathIndexer is used as a precision pre-filter: when it finds paths whose
    resolved FQN matches symbols in the question, those chunks receive a large
    score bonus in the RRF fusion. For direct alias questions
    (e.g. "which backend does by_name('redis') resolve to"), PathIndexer
    materializes hits directly.

    Inherited methods (via HybridRetriever):
        retrieve, build_context, expand_candidate_fqns, materialize_hits
    """

    def __init__(
        self,
        chunks: Sequence,
        *,
        path_indexer: DependencyPathIndexer | None = None,
        path_score_bonus: float = _PATH_SCORE_BONUS,
    ) -> None:
        self._base_chunks = list(chunks)
        super().__init__(chunks)
        self._path_indexer = path_indexer
        self._path_score_bonus = path_score_bonus

    @classmethod
    def from_repo(
        cls,
        repo_root: Path | str,
        *,
        build_path_index: bool = True,
        path_score_bonus: float = _PATH_SCORE_BONUS,
    ) -> "HybridRetrieverWithPath":
        """
        Factory: build from repo root, optionally building the path index.

        Args:
            repo_root: Root of the Celery source repository.
            build_path_index: If True, builds the DependencyPathIndexer
                (may be slow on first call). If False, lazy-built on first
                Type E question.
            path_score_bonus: Score bonus for chunks matching path FQNs.
        """
        from .ast_chunker import chunk_repository as _cr
        chunks = _cr(Path(repo_root))
        path_idx: DependencyPathIndexer | None = None
        if build_path_index:
            path_idx = DependencyPathIndexer(repo_root)
            path_idx.build_index()
        inst = cls(chunks, path_indexer=path_idx, path_score_bonus=path_score_bonus)
        return inst

    # ── Path indexer access ────────────────────────────────────────────────

    @property
    def path_indexer(self) -> DependencyPathIndexer:
        """Lazily build and return the path indexer."""
        if self._path_indexer is None:
            repo_root = (
                Path(self._base_chunks[0].repo_path).anchor
                if self._base_chunks
                else "."
            )
            self._path_indexer = DependencyPathIndexer(repo_root)
            self._path_indexer.build_index()
        return self._path_indexer

    def ensure_path_index(self) -> None:
        """Force early index build (call before critical retrieval)."""
        _ = self.path_indexer

    # ── Override retrieve_with_trace ─────────────────────────────────────

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
    ) -> RetrievalTraceWithPath:
        """
        Retrieve with PathIndexer augmentation for Type E questions.

        Returns RetrievalTraceWithPath with path_indexer_hits and
        path_augmented flag added to the standard RetrievalTrace fields.
        """
        # Step 1: Classify question type
        classification = classify_question_type(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        )

        # Step 2: Run standard RRF (from parent class)
        rrf_trace = HybridRetriever.retrieve_with_trace(
            self,
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )

        # Step 3: If Type E, try PathIndexer
        path_hits: list[PathInfo] = []
        if classification.failure_type == "Type E":
            path_hits = self._retrieve_paths(
                question=question,
                entry_symbol=entry_symbol,
                entry_file=entry_file,
                top_k=top_k,
            )

        # Step 4: Augment RRF results with path information
        (
            augmented_fused,
            augmented_ids,
            path_augmented,
        ) = self._augment_fused_with_paths(
            rrf_fused=list(rrf_trace.fused),
            path_hits=path_hits,
            top_k=top_k,
        )

        return RetrievalTraceWithPath(
            bm25=rrf_trace.bm25,
            semantic=rrf_trace.semantic,
            graph=rrf_trace.graph,
            fused_ids=augmented_ids,
            fused=tuple(augmented_fused),
            path_indexer_hits=tuple(path_hits),
            path_augmented=path_augmented,
            question_classification=classification,
        )

    # ── Path retrieval ───────────────────────────────────────────────────

    def _retrieve_paths(
        self,
        question: str,
        entry_symbol: str,
        entry_file: str,
        top_k: int,
    ) -> list[PathInfo]:
        """Search PathIndexer for relevant symbol resolution paths (best-effort)."""
        try:
            return self.path_indexer.search_paths(
                question=question,
                entry_symbol=entry_symbol,
                entry_file=entry_file,
                top_k=top_k,
            )
        except Exception:
            return []

    def _augment_fused_with_paths(
        self,
        rrf_fused: list[RetrievalHit],
        path_hits: list[PathInfo],
        top_k: int,
    ) -> tuple[list[RetrievalHit], tuple[str, ...], bool]:
        """
        Boost chunks whose symbol matches PathInfo.resolved_fqn.

        Returns (new_fused, new_fused_ids, was_augmented).
        If no path hits or no overlap, returns original fused list unchanged.
        """
        if not path_hits:
            return rrf_fused, tuple(h.chunk_id for h in rrf_fused), False

        resolved_fqns = {p.resolved_fqn.lower() for p in path_hits}

        boosted_ids: set[str] = set()
        for hit in rrf_fused:
            chunk = self.chunk_by_id.get(hit.chunk_id)
            if chunk and chunk.symbol.lower() in resolved_fqns:
                boosted_ids.add(hit.chunk_id)

        if not boosted_ids:
            return rrf_fused, tuple(h.chunk_id for h in rrf_fused), False

        # Re-score: add bonus to matching chunks, re-sort
        new_fused: list[RetrievalHit] = []
        for hit in rrf_fused:
            if hit.chunk_id in boosted_ids:
                new_fused.append(
                    RetrievalHit(
                        chunk_id=hit.chunk_id,
                        symbol=hit.symbol,
                        repo_path=hit.repo_path,
                        kind=hit.kind,
                        score=hit.score + self._path_score_bonus,
                        source=hit.source,
                        start_line=hit.start_line,
                        end_line=hit.end_line,
                        snippet=hit.snippet,
                    )
                )
            else:
                new_fused.append(hit)

        new_fused.sort(key=lambda h: h.score, reverse=True)
        return new_fused, tuple(h.chunk_id for h in new_fused), True

    # ── Convenience helpers ─────────────────────────────────────────────

    def resolve_via_path(
        self,
        question: str,
        entry_symbol: str = "",
    ) -> list[PathInfo]:
        """Direct PathIndexer query without RRF (for debugging)."""
        return self._retrieve_paths(
            question=question,
            entry_symbol=entry_symbol,
            entry_file="",
            top_k=5,
        )

    def path_context(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 5,
    ) -> str:
        """Build a context string from PathIndexer results for Type E questions."""
        paths = self._retrieve_paths(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
        )
        if not paths:
            return ""
        return self.path_indexer.format_paths_for_context(paths)
