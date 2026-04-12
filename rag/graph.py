"""
Graph-based symbol registry and graph-search logic.

Exports:
    SymbolRegistry
    graph_search
    _entry_file_to_module
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .ast_chunker import CodeChunk
    from .fusion import _tokenize, _extract_symbol_like_strings, _extract_string_literals, _kind_bonus


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


# ── Graph Search ───────────────────────────────────────────────────────


def graph_search(
    graph: dict[str, list[str]],
    chunk_by_id: dict[str, "CodeChunk"],
    symbol_to_ids: dict[str, list[str]],
    module_to_ids: dict[str, list[str]],
    basename_to_ids: dict[str, list[str]],
    parent_to_ids: dict[str, list[str]],
    chunk_tokens: dict[str, list[str]],
    question: str,
    entry_symbol: str,
    entry_file: str,
    top_n: int,
    query_mode: str,
    tokenize_fn,
    extract_symbols_fn,
    extract_literals_fn,
    kind_bonus_fn,
) -> list[str]:
    """
    Graph-based BFS search starting from entry anchors.

    Implements fast dict-based BFS with max depth 2, scoring by distance,
    token overlap, edge type, and string-literal matching.
    """
    seeds: set[str] = set()

    if query_mode == "question_plus_entry":
        if entry_symbol:
            seeds.update(_resolve_target_ids(
                entry_symbol, symbol_to_ids, module_to_ids, basename_to_ids
            ))
            seeds.update(_resolve_target_ids(
                entry_symbol.rsplit(".", 1)[0],
                symbol_to_ids, module_to_ids, basename_to_ids,
            ))
        if entry_file:
            module_from_file = _entry_file_to_module(entry_file)
            if module_from_file:
                seeds.update(module_to_ids.get(module_from_file, []))
    elif query_mode != "question_only":
        raise ValueError(f"Unsupported query mode: {query_mode}")

    for target in extract_symbols_fn(question):
        seeds.update(_resolve_target_ids(
            target, symbol_to_ids, module_to_ids, basename_to_ids
        ))

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
        for neighbor in graph.get(curr, ()):
            if neighbor in visited and visited[neighbor] <= dist + 1:
                continue
            visited[neighbor] = dist + 1
            if curr in edge_rel:
                edge_rel[neighbor] = edge_rel[curr]
            queue.append((neighbor, dist + 1))

    if not visited:
        return []

    query_tokens = set(tokenize_fn(question))
    query_literals = extract_literals_fn(question)
    scored: list[tuple[float, str]] = []

    for chunk_id, distance in visited.items():
        chunk = chunk_by_id.get(chunk_id)
        if chunk is None:
            continue
        overlap = len(query_tokens & set(chunk_tokens.get(chunk_id, [])))
        score = 1.0 / (1 + distance) + overlap * 0.05 + kind_bonus_fn(chunk.kind)
        rel = edge_rel.get(chunk_id, "")
        if rel == "import":
            score += 0.3
        elif rel == "string_target":
            score += 0.25
        elif rel == "reference":
            score += 0.15

        # Type D专项：字符串字面量匹配boost
        chunk_literal_targets = (
            set(chunk.string_targets) if chunk.string_targets else set()
        )
        literal_overlap = len(query_literals & chunk_literal_targets)
        if literal_overlap > 0:
            score += literal_overlap * 0.8
        scored.append((score, chunk_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk_id for _, chunk_id in scored[:top_n]]


def _resolve_target_ids(
    target: str,
    symbol_to_ids: dict[str, list[str]],
    module_to_ids: dict[str, list[str]],
    basename_to_ids: dict[str, list[str]],
) -> list[str]:
    if target in symbol_to_ids:
        return list(symbol_to_ids[target])
    if target in module_to_ids:
        return list(module_to_ids[target])
    base = target.rsplit(".", 1)[-1]
    return list(basename_to_ids.get(base, []))


class SymbolRegistry:
    """
    图搜索的符号注册表。

    维护从符号名/模块名/basename到chunk_id的映射，
    并构建基于导入/字符串目标/引用的依赖图。
    """

    def __init__(
        self,
        chunks: list["CodeChunk"],
    ) -> None:
        self.symbol_to_ids: dict[str, list[str]] = {}
        self.module_to_ids: dict[str, list[str]] = {}
        self.basename_to_ids: dict[str, list[str]] = {}
        self.parent_to_ids: dict[str, list[str]] = {}

        for chunk in chunks:
            if chunk.symbol not in self.symbol_to_ids:
                self.symbol_to_ids[chunk.symbol] = []
            self.symbol_to_ids[chunk.symbol].append(chunk.chunk_id)

            if chunk.module not in self.module_to_ids:
                self.module_to_ids[chunk.module] = []
            self.module_to_ids[chunk.module].append(chunk.chunk_id)

            if chunk.symbol:
                base = chunk.symbol.rsplit(".", 1)[-1]
                if base not in self.basename_to_ids:
                    self.basename_to_ids[base] = []
                self.basename_to_ids[base].append(chunk.chunk_id)

            if chunk.parent_symbol:
                if chunk.parent_symbol not in self.parent_to_ids:
                    self.parent_to_ids[chunk.parent_symbol] = []
                self.parent_to_ids[chunk.parent_symbol].append(chunk.chunk_id)

    def resolve_target_ids(self, target: str) -> list[str]:
        return _resolve_target_ids(
            target,
            self.symbol_to_ids,
            self.module_to_ids,
            self.basename_to_ids,
        )
