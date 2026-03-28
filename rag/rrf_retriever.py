from __future__ import annotations

import math
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .ast_chunker import (
    CodeChunk,
    chunk_repository,
    module_name_from_path,
    normalize_symbol_target,
)
from .embedding_provider import (
    EmbeddingProviderClient,
    load_embedding_cache,
    resolve_embedding_config,
    save_embedding_cache,
)


_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class RankedResult:
    item_id: str
    score: float
    source: str


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    symbol: str
    repo_path: str
    kind: str
    score: float
    source: tuple[str, ...]
    start_line: int
    end_line: int
    snippet: str


@dataclass(frozen=True)
class RetrievalTrace:
    bm25: tuple[str, ...]
    semantic: tuple[str, ...]
    graph: tuple[str, ...]
    fused_ids: tuple[str, ...]
    fused: tuple[RetrievalHit, ...]


def rrf_fuse(rankings: dict[str, Iterable[str]], k: int = 60) -> list[RankedResult]:
    """
    倒数排名融合（Reciprocal Rank Fusion）

    将多个排序列表融合为一个统一排序。
    公式：score(item) = Σ 1/(k + rank(item))

    Args:
        rankings: 各来源的排序字典，key为来源名，value为排序后的item列表
        k: RRF参数，通常60

    Returns:
        按融合分数排序的结果列表
    """
    fused_scores: dict[str, float] = defaultdict(float)
    provenance: dict[str, set[str]] = defaultdict(set)

    for source_name, items in rankings.items():
        for rank, item_id in enumerate(items, start=1):
            fused_scores[item_id] += 1.0 / (k + rank)
            provenance[item_id].add(source_name)

    ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)

    results: list[RankedResult] = []
    for item_id, score in ranked:
        results.append(
            RankedResult(
                item_id=item_id,
                score=score,
                source=",".join(sorted(provenance[item_id])),
            )
        )
    return results


def rrf_fuse_weighted(
    rankings: dict[str, Iterable[str]],
    weights: dict[str, float],
    k: int = 30,
) -> list[RankedResult]:
    """
    加权倒数排名融合（Weighted Reciprocal Rank Fusion）

    在标准 RRF 基础上乘以来源权重。
    公式：score(item) = Σ weight[source] / (k + rank(item))

    Args:
        rankings: 各来源的排序字典，key为来源名，value为排序后的item列表
        weights: 各来源的权重，key为来源名
        k: RRF参数，通常30

    Returns:
        按融合分数排序的结果列表
    """
    fused_scores: dict[str, float] = defaultdict(float)
    provenance: dict[str, set[str]] = defaultdict(set)

    for source_name, items in rankings.items():
        w = weights.get(source_name, 1.0)
        for rank, item_id in enumerate(items, start=1):
            fused_scores[item_id] += w * 1.0 / (k + rank)
            provenance[item_id].add(source_name)

    ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)
    return [
        RankedResult(
            item_id=item_id,
            score=score,
            source=",".join(sorted(provenance[item_id])),
        )
        for item_id, score in ranked
    ]


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
        _GLOBAL_CHUNK_REGISTRY.clear()
        _GLOBAL_CHUNK_REGISTRY.update(self.chunk_by_id)
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

        self._bm25 = _BM25Index(self.chunk_tokens)
        self._semantic = _EmbeddingIndex(self.chunks)
        self._build_graph()

    @classmethod
    def from_repo(cls, repo_root: Path | str) -> "HybridRetriever":
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
    ) -> str:
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
        sections = []
        for rank, hit in enumerate(trace.fused, start=1):
            location = f"{hit.repo_path}:{hit.start_line}-{hit.end_line}"
            source = ", ".join(hit.source) if hit.source else "fused"
            sections.append(
                f"[Retrieved {rank}] {hit.symbol} ({location}) | source={source}\n{hit.snippet}"
            )
        return "\n\n".join(sections)

    def expand_candidate_fqns(
        self,
        hits: Sequence[RetrievalHit],
        query_text: str = "",
        entry_symbol: str = "",
    ) -> list[str]:
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
        seeds: set[str] = set()
        if query_mode == "question_plus_entry":
            if entry_symbol:
                seeds.update(self._resolve_target_ids(entry_symbol))
                seeds.update(self._resolve_target_ids(entry_symbol.rsplit(".", 1)[0]))
            if entry_file:
                module_from_file = _entry_file_to_module(entry_file)
                if module_from_file:
                    seeds.update(self.module_to_ids.get(module_from_file, []))
        elif query_mode != "question_only":
            raise ValueError(f"Unsupported query mode: {query_mode}")
        for target in _extract_symbol_like_strings(question):
            seeds.update(self._resolve_target_ids(target))

        if not seeds:
            return []

        # Fast dict-based BFS, max depth 2
        visited: dict[str, int] = {}
        edge_rel: dict[str, str] = {}  # chunk_id -> best edge rel from nearest seed
        queue: list[tuple[str, int]] = [(s, 0) for s in seeds]
        for s in seeds:
            visited[s] = 0
            edge_rel[s] = "seed"

        while queue:
            curr, dist = queue.pop(0)
            if dist >= 2:
                continue
            for neighbor in self._graph.get(curr, ()):
                if neighbor in visited and visited[neighbor] <= dist + 1:
                    continue
                visited[neighbor] = dist + 1
                # Determine edge rel from seed: inherit from curr or detect
                if curr in edge_rel:
                    edge_rel[neighbor] = edge_rel[curr]
                queue.append((neighbor, dist + 1))

        if not visited:
            return []

        query_tokens = set(_tokenize(question))
        query_literals = _extract_string_literals(question)
        scored: list[tuple[float, str]] = []
        for chunk_id, distance in visited.items():
            chunk = self.chunk_by_id.get(chunk_id)
            if chunk is None:
                continue
            overlap = len(query_tokens & set(self.chunk_tokens.get(chunk_id, [])))
            score = 1.0 / (1 + distance) + overlap * 0.05 + _kind_bonus(chunk.kind)
            rel = edge_rel.get(chunk_id, "")
            if rel == "import":
                score += 0.3
            elif rel == "string_target":
                score += 0.25
            elif rel == "reference":
                score += 0.15
            # Type D专项：字符串字面量匹配boost
            # 当问题中的字符串字面量（如 'processes', 'threads'）
            # 匹配到 chunk 的 string_targets 时，给显著boost
            chunk_literal_targets = (
                set(chunk.string_targets) if chunk.string_targets else set()
            )
            literal_overlap = len(query_literals & chunk_literal_targets)
            if literal_overlap > 0:
                score += literal_overlap * 0.8
            scored.append((score, chunk_id))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk_id for _, chunk_id in scored[:top_n]]

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


# ── Semantic Index: provider-aware embeddings ────────────────────────


_EMBED_BATCH_SIZE = 50


class _EmbeddingIndex:
    """
    Real embedding index using provider-aware embeddings.

    Uses cache-first strategy: load from disk cache if available,
    otherwise fall back to TF-IDF. Pre-computation script can build
    the cache offline when rate limits allow.
    """

    def __init__(self, chunks: list[CodeChunk], *, repo_root: str | Path = "") -> None:
        self.chunk_ids = [c.chunk_id for c in chunks]
        self._chunk_texts: dict[str, str] = {
            c.chunk_id: f"{c.symbol} {c.signature} {c.content}" for c in chunks
        }
        # Always keep a TF-IDF fallback so the query path is consistent even
        # when all chunk embeddings are already cached.
        self._fallback = _SemanticIndexTfidf(chunks)
        self._client = None
        self._config = resolve_embedding_config()
        self._embeddings: dict[str, list[float]] = {}
        self._repo_root = str(repo_root)
        self._quota_exhausted = False

        if self._config.cache_file.exists():
            self._load_cache()

        cached = len(self._embeddings)
        if cached == len(self.chunk_ids):
            print(
                f"[EmbeddingIndex] All {cached} embeddings loaded from cache "
                f"({self._config.provider_label})"
            )
            return

        missing = [cid for cid in self.chunk_ids if cid not in self._embeddings]
        print(
            f"[EmbeddingIndex] Cache loaded: {cached}/{len(self.chunk_ids)} "
            f"from {self._config.cache_file} ({self._config.provider_label})"
        )

    def _truncate(self, text: str, max_chars: int = 2000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:max_chars]

    def _ensure_client(self) -> bool:
        if self._client is not None:
            return not self._quota_exhausted
        if self._quota_exhausted:
            return False
        try:
            self._client = EmbeddingProviderClient(self._config)
            if not self._client.available():
                return False
            return True
        except Exception:
            return False

    def _quota_hit(self) -> None:
        self._quota_exhausted = True
        self._client = None

    def _embed_batch(self, texts: list[str], chunk_ids: list[str]) -> int:
        if not self._ensure_client():
            return 0
        import time

        for attempt in range(3):
            try:
                embeddings = self._client.batch_embed(texts)
                if not embeddings:
                    raise RuntimeError("empty embeddings response")
                for cid, emb in zip(chunk_ids, embeddings):
                    self._embeddings[cid] = emb
                return len(embeddings)
            except Exception as exc:
                if "429" in str(exc) and attempt == 0:
                    print(f"[EmbeddingIndex] API quota exhausted, stopping")
                    self._quota_hit()
                    return 0
                wait = (attempt + 1) * 5
                print(f"[EmbeddingIndex] Batch failed ({exc}), retrying in {wait}s...")
                time.sleep(wait)
        return 0

    def _embed_chunks(self, chunk_ids: list[str]) -> None:
        texts = [self._truncate(self._chunk_texts[cid]) for cid in chunk_ids]
        total = len(chunk_ids)
        done = 0
        batch_size = _EMBED_BATCH_SIZE
        print(f"[EmbeddingIndex] Embedding {total} chunks...")

        for i in range(0, total, batch_size):
            batch_ids = chunk_ids[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            n = self._embed_batch(batch_texts, batch_ids)
            if n == 0:
                print(
                    f"[EmbeddingIndex] Batch embedding failed at {i}/{total}, stopping"
                )
                break
            done += n
            print(f"[EmbeddingIndex]   {done}/{total}")
            import time

            time.sleep(1)

        if done == total:
            self._save_cache()
        elif done > 0:
            print(f"[EmbeddingIndex] Partial embedding: {done}/{total}, saving cache")
            self._save_cache()

    def _load_cache(self) -> None:
        try:
            self._embeddings = load_embedding_cache(
                self._config,
                valid_chunk_ids=set(self.chunk_ids),
            )
            print(
                f"[EmbeddingIndex] Cache loaded: {len(self._embeddings)}/{len(self.chunk_ids)}"
            )
        except Exception:
            self._embeddings = {}

    def _save_cache(self) -> None:
        try:
            save_embedding_cache(self._config, self._embeddings)
            print(f"[EmbeddingIndex] Cache saved: {len(self._embeddings)} chunks")
        except Exception as exc:
            print(f"[EmbeddingIndex] Cache save failed: {exc}")

    def search(self, query: str, top_n: int) -> list[str]:
        if not query.strip():
            return []

        embed_coverage = len(self._embeddings) / len(self.chunk_ids)

        if embed_coverage < 0.5:
            return self._fallback.search(query, top_n)

        if not self._ensure_client():
            return self._fallback.search(query, top_n)

        try:
            q_emb = self._client.embed_query(query)
        except Exception as exc:
            if "429" in str(exc):
                print(f"[EmbeddingIndex] API quota exhausted, using TF-IDF only")
                self._quota_hit()
            return self._fallback.search(query, top_n)

        # Embedding-based scores for chunks that have embeddings
        embed_scores: dict[str, float] = {}
        for cid, emb in self._embeddings.items():
            dot = sum(a * b for a, b in zip(q_emb, emb))
            embed_scores[cid] = (dot + 1.0) / 2.0

        # TF-IDF scores for top candidates (fallback for non-embedded chunks)
        tfidf_ids = self._fallback.search(query, top_n=top_n * 4)
        tfidf_scores_raw = {cid: 0.0 for cid in tfidf_ids}
        for rank, cid in enumerate(tfidf_ids, 1):
            tfidf_scores_raw[cid] = 1.0 / rank

        max_emb = max(embed_scores.values()) if embed_scores else 1.0
        max_tfidf = max(tfidf_scores_raw.values()) if tfidf_scores_raw else 1.0

        # Combine: real-embedded chunks use hybrid score, rest use TF-IDF only
        candidates = set(embed_scores) | set(tfidf_scores_raw)
        hybrid_scores: list[tuple[float, str]] = []
        for cid in candidates:
            emb = embed_scores.get(cid, 0.0) / max_emb
            tfidf = tfidf_scores_raw.get(cid, 0.0) / max_tfidf
            if cid in embed_scores:
                combined = emb * 0.7 + tfidf * 0.3
            else:
                combined = tfidf
            hybrid_scores.append((combined, cid))

        hybrid_scores.sort(key=lambda x: x[0], reverse=True)
        return [cid for _, cid in hybrid_scores[:top_n]]


class _SemanticIndexTfidf:
    """
    TF-IDF回退索引

    当嵌入API不可用时的回退方案。
    结合词级TF-IDF和字符n-gram进行检索。
    """

    def __init__(self, chunks: list[CodeChunk]) -> None:
        self.chunk_ids = [c.chunk_id for c in chunks]
        word_map: dict[str, list[str]] = {}
        for chunk in chunks:
            text = " ".join([chunk.symbol, chunk.signature, chunk.content])
            word_map[chunk.chunk_id] = _tokenize(text)
        self._word_index = _MiniTfidfIndex(word_map)
        char_map: dict[str, list[str]] = {}
        for chunk in chunks:
            text = chunk.symbol + " " + chunk.signature
            char_map[chunk.chunk_id] = _char_ngrams(text, n_min=3, n_max=5)
        self._char_index = _MiniTfidfIndex(char_map)

    def search(self, query: str, top_n: int) -> list[str]:
        if not query.strip():
            return []
        word_results = self._word_index.search(query, top_n=top_n)
        char_results = self._char_index.search(query, top_n=top_n)
        scores: dict[str, float] = {}
        for rank, cid in enumerate(word_results, 1):
            scores[cid] = scores.get(cid, 0.0) + (1.0 / rank) * 0.6
        for rank, cid in enumerate(char_results, 1):
            scores[cid] = scores.get(cid, 0.0) + (1.0 / rank) * 0.4
        return [
            cid
            for cid, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)[
                :top_n
            ]
        ]


class _MiniTfidfIndex:
    """Lightweight TF-IDF using raw term frequencies + IDF approximation."""

    def __init__(self, token_map: dict[str, list[str]]) -> None:
        self.token_map = token_map
        self.doc_freqs: Counter[str] = Counter()
        for tokens in token_map.values():
            self.doc_freqs.update(set(tokens))
        self.num_docs = len(token_map)

    def search(self, query: str, top_n: int) -> list[str]:
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        tf_freq = Counter(q_tokens)
        scores: list[tuple[float, str]] = []
        for cid, tokens in self.token_map.items():
            doc_tf = Counter(tokens)
            score = 0.0
            for tok in q_tokens:
                df = self.doc_freqs.get(tok, 0)
                if df == 0:
                    continue
                idf = math.log((self.num_docs + 1) / (df + 1)) + 1.0
                score += idf * doc_tf.get(tok, 0)
            if score:
                scores.append((score, cid))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [cid for _, cid in scores[:top_n]]


def _char_ngrams(text: str, n_min: int, n_max: int) -> list[str]:
    text = text.lower()
    result: list[str] = []
    for n in range(n_min, n_max + 1):
        for i in range(len(text) - n + 1):
            result.append(text[i : i + n])
    return result


# ── BM25 Index ───────────────────────────────────────────────────────


class _BM25Index:
    """
    BM25检索索引

    BM25是一种基于词频的经典检索算法。
    参数：
    - k1: 词频饱和参数（默认1.5）
    - b: 文档长度归一化参数（默认0.75）
    """

    def __init__(
        self, token_map: dict[str, list[str]], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self.k1 = k1
        self.b = b
        self.token_map = token_map
        self.doc_lengths = {
            chunk_id: len(tokens) for chunk_id, tokens in token_map.items()
        }
        self.avg_doc_length = (
            sum(self.doc_lengths.values()) / len(self.doc_lengths)
            if self.doc_lengths
            else 0.0
        )
        self.term_freqs = {
            chunk_id: Counter(tokens) for chunk_id, tokens in token_map.items()
        }
        self.doc_freqs: Counter[str] = Counter()
        for tokens in token_map.values():
            self.doc_freqs.update(set(tokens))
        self.num_docs = len(token_map)

    def search(self, query: str, top_n: int) -> list[str]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores: list[tuple[float, str]] = []
        for chunk_id, frequencies in self.term_freqs.items():
            doc_length = self.doc_lengths[chunk_id]
            score = 0.0
            for token in query_tokens:
                tf = frequencies.get(token, 0)
                if tf == 0:
                    continue
                doc_freq = self.doc_freqs.get(token, 0)
                idf = math.log(1 + (self.num_docs - doc_freq + 0.5) / (doc_freq + 0.5))
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_length / (self.avg_doc_length or 1.0)
                )
                score += idf * (tf * (self.k1 + 1)) / denominator
            if score:
                chunk = self._safe_chunk(chunk_id)
                score += _kind_bonus(chunk.kind)
                scores.append((score, chunk_id))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [chunk_id for _, chunk_id in scores[:top_n]]

    def _safe_chunk(self, chunk_id: str) -> CodeChunk:
        return _GLOBAL_CHUNK_REGISTRY[chunk_id]


# ── Helpers ──────────────────────────────────────────────────────────


def _kind_bonus(kind: str) -> float:
    """
    根据代码块类型给予额外加分

    - method: 0.18 (类方法权重最高)
    - function/async_function: 0.12
    - class: 0.08
    - 其他: 0.0
    """
    if kind == "method":
        return 0.18
    if kind in {"function", "async_function"}:
        return 0.12
    if kind == "class":
        return 0.08
    return 0.0


def _tokenize(text: str) -> list[str]:
    """
    分词函数

    处理：
    1. 特殊字符替换（: -> .，/ -> . 等）
    2. 标识符提取
    3. 驼峰分词
    """
    normalized = (
        text.replace(":", ".").replace("/", ".").replace("`", " ").replace("-", " ")
    )
    tokens: list[str] = []
    for raw_token in _TOKEN_PATTERN.findall(normalized):
        lower = raw_token.lower()
        tokens.append(lower)
        split_token = re.sub(r"(?<!^)(?=[A-Z])", " ", raw_token).lower()
        tokens.extend(piece for piece in split_token.split() if piece)
    return tokens


def _extract_symbol_like_strings(text: str) -> list[str]:
    matches = re.findall(
        r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+", text
    )
    return [normalize_symbol_target(match) for match in matches]


def _extract_string_literals(text: str) -> set[str]:
    """Extract quoted string literals from text for Type D disambiguation.

    Matches single-quoted and double-quoted strings like 'processes', "threads".
    These are often alias/argument values that determine which symbol to resolve to.
    """
    quoted = re.findall(r"['\"]([a-zA-Z_][a-zA-Z0-9_]*)['\"]", text)
    return set(quoted)


def _looks_like_fqn(value: str) -> bool:
    """
    检查字符串是否像FQN（完全限定名）

    必须包含至少一个点，且每个部分都是有效的Python标识符。

    Examples:
        "celery.app.trace" -> True
        "foo" -> False (没有点)
        "123.foo" -> False (部分以数字开头)
    """
    if "." not in value:
        return False
    for part in value.split("."):
        if not part:
            return False
        if not (part[0].isalpha() or part[0] == "_"):
            return False
    return True


_GLOBAL_CHUNK_REGISTRY: dict[str, CodeChunk] = {}


def _entry_file_to_module(entry_file: str) -> str:
    path = Path(entry_file)
    parts = list(path.parts)
    if not parts:
        return ""
    stem = Path(parts[-1]).stem
    if stem == "__init__":
        parts = parts[:-1]
    else:
        parts[-1] = stem
    return ".".join(part for part in parts if part)


def build_retriever(repo_root: Path | str) -> HybridRetriever:
    return HybridRetriever.from_repo(repo_root)
