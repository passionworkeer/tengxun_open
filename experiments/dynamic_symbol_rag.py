from __future__ import annotations

import ast
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rag.ast_chunker import CodeChunk, normalize_symbol_target
from rag.rrf_retriever import (
    HybridRetriever,
    RetrievalHit,
    RetrievalTrace,
    _estimate_tokens,
    _extract_string_literals,
    _tokenize,
    _truncate_to_token_budget,
    build_retriever,
    rrf_fuse,
    rrf_fuse_weighted,
)


_DICT_ALIAS_PATTERN = re.compile(
    r"['\"](?P<alias>[A-Za-z_][A-Za-z0-9_-]*)['\"]\s*:\s*['\"](?P<target>(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+)['\"]"
)
_CODE_REF_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
_QUOTED_TEXT_PATTERN = re.compile(r"[`'\"]([^`'\"]+)[`'\"]")
_HIGH_SIGNAL_TOKENS = {
    "alias",
    "backend",
    "django",
    "fixup",
    "loader",
    "request",
    "strategy",
    "symbol",
    "task_cls",
}
_CALL_KEYWORDS = {
    "backend",
    "fixups",
    "loader",
    "request",
    "scheduler_cls",
    "strategy",
    "task_cls",
}


@dataclass(frozen=True)
class RawBinding:
    key: str
    raw_target: str
    source_chunk_id: str
    source_symbol: str
    confidence: float
    match_type: str


@dataclass(frozen=True)
class AliasTarget:
    alias: str
    target_symbol: str
    target_chunk_ids: tuple[str, ...]
    source_chunk_id: str
    source_symbol: str
    confidence: float
    match_type: str = "alias"


@dataclass(frozen=True)
class DynamicRetrievalTrace:
    base: RetrievalTrace
    alias_hits: tuple[AliasTarget, ...]
    dynamic: tuple[str, ...]
    fused_ids: tuple[str, ...]
    fused: tuple[RetrievalHit, ...]


class DynamicAliasIndex:
    """Standalone dynamic symbol index for Type E style questions.

    This version goes beyond plain alias dicts. It extracts:
    - alias-table entries such as ``LOADER_ALIASES["default"]``
    - class/instance string assignments such as ``Task.Request = "..."``
    - collection-based entry points such as ``BUILTIN_FIXUPS = {...}``
    - literal resolver calls such as ``instantiate("pkg.mod:Cls")``
    - keyword arguments such as ``loader="default"``

    It then performs a short alias-chaining step so that references like
    ``loader -> default -> celery.loaders.default.Loader`` can jump to the
    terminal symbol instead of stopping at the runtime alias value.
    """

    def __init__(self, base: HybridRetriever) -> None:
        self.base = base
        self.bindings_by_key: dict[str, list[RawBinding]] = defaultdict(list)
        self.key_to_targets: dict[str, list[AliasTarget]] = defaultdict(list)
        self.token_to_targets: dict[str, list[AliasTarget]] = defaultdict(list)
        self._build()

    def _build(self) -> None:
        for chunk in self.base.chunks:
            for binding in _extract_dynamic_bindings(chunk):
                self.bindings_by_key[_normalize_key(binding.key)].append(binding)

        for bindings in self.bindings_by_key.values():
            for binding in bindings:
                for target_symbol, target_chunk_ids, depth in self._resolve_terminal_targets(
                    binding.raw_target,
                    seen_keys={_normalize_key(binding.key)},
                ):
                    confidence = max(0.55, binding.confidence - depth * 0.12)
                    record = AliasTarget(
                        alias=binding.key,
                        target_symbol=target_symbol,
                        target_chunk_ids=target_chunk_ids,
                        source_chunk_id=binding.source_chunk_id,
                        source_symbol=binding.source_symbol,
                        confidence=confidence,
                        match_type=binding.match_type,
                    )
                    self.key_to_targets[_normalize_key(binding.key)].append(record)
                    for token in set(_tokenize(binding.key)):
                        if token in _HIGH_SIGNAL_TOKENS:
                            self.token_to_targets[token].append(record)

        for key, values in list(self.key_to_targets.items()):
            self.key_to_targets[key] = _dedupe_alias_targets(values)
        for token, values in list(self.token_to_targets.items()):
            self.token_to_targets[token] = _dedupe_alias_targets(values)

    def _resolve_terminal_targets(
        self,
        raw_target: str,
        *,
        seen_keys: set[str],
        depth: int = 0,
        max_depth: int = 3,
    ) -> list[tuple[str, tuple[str, ...], int]]:
        normalized = normalize_symbol_target(raw_target)
        resolved: list[tuple[str, tuple[str, ...], int]] = []

        target_chunk_ids = tuple(dict.fromkeys(self.base._resolve_target_ids(normalized)))
        if target_chunk_ids and _looks_like_resolvable_symbol(normalized):
            resolved.append((normalized, target_chunk_ids, depth))

        if depth >= max_depth:
            return resolved

        alias_candidates = _alias_candidates(raw_target)
        for alias_key in alias_candidates:
            if alias_key in seen_keys:
                continue
            for binding in self.bindings_by_key.get(alias_key, ()):
                resolved.extend(
                    self._resolve_terminal_targets(
                        binding.raw_target,
                        seen_keys=seen_keys | {alias_key},
                        depth=depth + 1,
                        max_depth=max_depth,
                    )
                )
        return _dedupe_resolved_targets(resolved)

    def resolve_aliases(self, question: str) -> list[AliasTarget]:
        literals = set()
        for literal in _extract_string_literals(question):
            literals.update(_alias_candidates(literal))

        hits: list[AliasTarget] = []
        for literal in literals:
            hits.extend(self.key_to_targets.get(literal, ()))
        return _dedupe_alias_targets(hits)

    def resolve_references(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
    ) -> list[AliasTarget]:
        keys = _extract_reference_keys(question, entry_symbol=entry_symbol, entry_file=entry_file)
        query_tokens = set(_tokenize(" ".join(part for part in (question, entry_symbol, entry_file) if part)))

        hits: list[AliasTarget] = []
        for key in keys:
            normalized = _normalize_key(key)
            hits.extend(self.key_to_targets.get(normalized, ()))
            tail = normalized.rsplit(".", 1)[-1]
            if tail != normalized and normalized.count(".") <= 1:
                hits.extend(self.key_to_targets.get(tail, ()))

        for token in query_tokens:
            if token not in _HIGH_SIGNAL_TOKENS:
                continue
            hits.extend(self.token_to_targets.get(token, ()))
        return _dedupe_alias_targets(hits)

    def rank(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_n: int = 12,
    ) -> tuple[list[str], list[AliasTarget]]:
        query_text = " ".join(part for part in (question, entry_symbol, entry_file) if part)
        query_tokens = set(_tokenize(query_text))
        entry_module = _entry_file_to_module(entry_file)
        alias_hits = self.resolve_aliases(question)
        reference_hits = self.resolve_references(
            question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        )
        dynamic_hits = _dedupe_alias_targets([*alias_hits, *reference_hits])
        scores: dict[str, float] = {}

        for hit in dynamic_hits:
            if (
                hit.match_type == "call_keyword"
                and entry_module
                and not hit.source_symbol.startswith(entry_module)
            ):
                continue
            target_tokens = set(_tokenize(hit.target_symbol))
            alias_tokens = set(_tokenize(hit.alias))
            source_tokens = set(_tokenize(hit.source_symbol))
            target_overlap = len(query_tokens & target_tokens)
            alias_overlap = len(query_tokens & alias_tokens)
            source_overlap = len(query_tokens & source_tokens)
            source_bonus = 1.0 + hit.confidence + alias_overlap * 0.45 + source_overlap * 0.12
            scores[hit.source_chunk_id] = max(scores.get(hit.source_chunk_id, 0.0), source_bonus)
            for rank, chunk_id in enumerate(hit.target_chunk_ids, start=1):
                bonus = (
                    2.1
                    + hit.confidence
                    + target_overlap * 0.30
                    + alias_overlap * 0.55
                    + source_overlap * 0.10
                    + 1.0 / rank
                )
                scores[chunk_id] = max(scores.get(chunk_id, 0.0), bonus)

        ranked = [
            chunk_id
            for chunk_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_n]
        ]
        return ranked, dynamic_hits


class DynamicSymbolEnhancedRetriever:
    """Standalone wrapper around the production retriever."""

    def __init__(self, base: HybridRetriever) -> None:
        self.base = base
        self.alias_index = DynamicAliasIndex(base)

    @classmethod
    def from_repo(cls, repo_root: Path | str) -> "DynamicSymbolEnhancedRetriever":
        return cls(build_retriever(repo_root))

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
    ) -> DynamicRetrievalTrace:
        base_trace = self.base.retrieve_with_trace(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_k=top_k,
            per_source=per_source,
            query_mode=query_mode,
            rrf_k=rrf_k,
            weights=weights,
        )
        dynamic_ranked, alias_hits = self.alias_index.rank(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            top_n=per_source,
        )

        rankings = {
            "bm25": base_trace.bm25,
            "semantic": base_trace.semantic,
            "graph": base_trace.graph,
            "dynamic": dynamic_ranked,
        }
        if weights:
            local_weights = dict(weights)
            local_weights.setdefault("dynamic", 1.20)
            fused_ranked = rrf_fuse_weighted(rankings, local_weights, k=rrf_k)
        else:
            fused_ranked = rrf_fuse(rankings, k=rrf_k)

        fused_ids = tuple(item.item_id for item in fused_ranked)
        fused_hits: list[RetrievalHit] = []
        for result in fused_ranked[:top_k]:
            chunk = self.base.chunk_by_id[result.item_id]
            fused_hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    symbol=chunk.symbol,
                    repo_path=chunk.repo_path,
                    kind=chunk.kind,
                    score=result.score,
                    source=tuple(result.source.split(",")) if result.source else (),
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    snippet=self.base._render_chunk(chunk, rank=len(fused_hits) + 1),
                )
            )

        return DynamicRetrievalTrace(
            base=base_trace,
            alias_hits=tuple(alias_hits),
            dynamic=tuple(dynamic_ranked),
            fused_ids=fused_ids,
            fused=tuple(fused_hits),
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

        alias_section = _format_alias_hits(trace.alias_hits)
        if alias_section:
            alias_tokens = _estimate_tokens(alias_section)
            if alias_tokens <= max_context_tokens:
                sections.append(alias_section)
                used_tokens += alias_tokens

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
            truncated = _truncate_to_token_budget(section, max(0, remaining_tokens - suffix_tokens))
            if truncated:
                sections.append(f"{truncated}{suffix}")
            else:
                sections.append("[Context budget exhausted] Remaining retrieved chunks omitted.")
            break
        return "\n\n".join(sections)

    def should_expand_rag(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        threshold: int = 1,
    ) -> bool:
        alias_hits = self.alias_index.resolve_aliases(question)
        reference_hits = self.alias_index.resolve_references(
            question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        )
        return len(_dedupe_alias_targets([*alias_hits, *reference_hits])) >= threshold


class _DynamicBindingCollector(ast.NodeVisitor):
    def __init__(self, source_symbol: str) -> None:
        self.source_symbol = source_symbol
        self.scope: list[str] = []
        self._records: list[RawBinding] = []
        self._seen: set[tuple[str, str, str]] = set()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        assignment_keys = []
        for target in node.targets:
            assignment_keys.extend(self._key_variants_for_target(target))

        dict_pairs = _extract_dict_pairs(node.value)
        if dict_pairs:
            for alias, target in dict_pairs:
                self._add_record(alias, target, match_type="dict_alias", confidence=1.18)

        string_targets = _extract_string_candidates(node.value)
        if string_targets and assignment_keys:
            for key in assignment_keys:
                for target in string_targets:
                    self._add_record(key, target, match_type="assignment", confidence=0.96)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        assignment_keys = self._key_variants_for_target(node.target)
        string_targets = _extract_string_candidates(node.value) if node.value else []
        if string_targets and assignment_keys:
            for key in assignment_keys:
                for target in string_targets:
                    self._add_record(key, target, match_type="assignment", confidence=0.96)
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is not None:
            string_targets = _extract_string_candidates(node.value)
            for target in string_targets:
                for key in self._current_scope_keys():
                    self._add_record(key, target, match_type="return_literal", confidence=0.92)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _call_name(node.func)
        if call_name in {"symbol_by_name", "instantiate"} and node.args:
            for literal in _extract_string_candidates(node.args[0]):
                self._add_record(
                    literal,
                    literal,
                    match_type=f"{call_name}_literal",
                    confidence=1.05,
                )

        for keyword in node.keywords:
            if not keyword.arg or keyword.arg not in _CALL_KEYWORDS:
                continue
            for target in _extract_string_candidates(keyword.value):
                self._add_record(keyword.arg, target, match_type="call_keyword", confidence=0.86)
                for scope_key in self._current_scope_keys():
                    self._add_record(
                        f"{scope_key}.{keyword.arg}",
                        target,
                        match_type="call_keyword",
                        confidence=0.82,
                    )
        self.generic_visit(node)

    @property
    def records(self) -> list[RawBinding]:
        return list(self._records)

    def _current_scope_keys(self) -> list[str]:
        if not self.scope:
            return []
        dotted = ".".join(self.scope)
        keys = {dotted, self.scope[-1]}
        if self.source_symbol:
            keys.add(f"{self.source_symbol}.{dotted}")
        return sorted(keys)

    def _key_variants_for_target(self, target: ast.AST) -> list[str]:
        rendered = _render_target_name(target)
        if not rendered:
            return []
        keys = {rendered, rendered.rsplit(".", 1)[-1]}
        if self.scope and "." not in rendered:
            scope_name = ".".join(self.scope)
            keys.add(f"{scope_name}.{rendered}")
            if self.source_symbol:
                keys.add(f"{self.source_symbol}.{rendered}")
                keys.add(f"{self.source_symbol}.{scope_name}.{rendered}")
        elif self.scope and "." in rendered:
            keys.add(rendered.split(".", 1)[-1])
            keys.add(rendered.rsplit(".", 1)[-1])
        return sorted(keys)

    def _add_record(
        self,
        key: str,
        raw_target: str,
        *,
        match_type: str,
        confidence: float,
    ) -> None:
        normalized_key = key.strip()
        normalized_target = raw_target.strip()
        if not normalized_key or not normalized_target:
            return
        if not _should_keep_dynamic_binding(
            key=normalized_key,
            raw_target=normalized_target,
            match_type=match_type,
        ):
            return
        dedupe_key = (
            normalized_key.lower(),
            normalized_target,
            match_type,
        )
        if dedupe_key in self._seen:
            return
        self._seen.add(dedupe_key)
        self._records.append(
            RawBinding(
                key=normalized_key,
                raw_target=normalized_target,
                source_chunk_id="",
                source_symbol=self.source_symbol,
                confidence=confidence,
                match_type=match_type,
            )
        )


def _extract_dynamic_bindings(chunk: CodeChunk) -> list[RawBinding]:
    if not chunk.repo_path.startswith("celery/"):
        return []
    records: list[RawBinding] = []
    tree = _parse_chunk_ast(chunk.content)
    if tree is not None:
        collector = _DynamicBindingCollector(source_symbol=chunk.symbol)
        collector.visit(tree)
        for record in collector.records:
            records.append(
                RawBinding(
                    key=record.key,
                    raw_target=record.raw_target,
                    source_chunk_id=chunk.chunk_id,
                    source_symbol=chunk.symbol,
                    confidence=record.confidence + _confidence_bonus(chunk.content),
                    match_type=record.match_type,
                )
            )

    if not records:
        for alias, target in _extract_alias_pairs_fallback(chunk.content):
            records.append(
                RawBinding(
                    key=alias,
                    raw_target=target,
                    source_chunk_id=chunk.chunk_id,
                    source_symbol=chunk.symbol,
                    confidence=1.02 + _confidence_bonus(chunk.content),
                    match_type="dict_regex",
                )
            )
    return records


def _parse_chunk_ast(content: str) -> ast.AST | None:
    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def _extract_string_candidates(node: ast.AST | None) -> list[str]:
    if node is None:
        return []
    values: list[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = node.value.strip()
        if _is_dynamic_string_candidate(text):
            values.append(text)
    elif isinstance(node, ast.BoolOp):
        for value in node.values:
            values.extend(_extract_string_candidates(value))
    elif isinstance(node, ast.IfExp):
        values.extend(_extract_string_candidates(node.body))
        values.extend(_extract_string_candidates(node.orelse))
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for item in node.elts:
            values.extend(_extract_string_candidates(item))
    return list(dict.fromkeys(values))


def _is_dynamic_string_candidate(text: str) -> bool:
    if not text or len(text) > 160:
        return False
    if any(char in text for char in ("\n", "\r", "\t")):
        return False
    if text.startswith(("http://", "https://")):
        return False
    if " " in text:
        return False
    if "://" in text:
        return True
    if ":" in text and "." in text:
        return True
    if "." in text:
        return _looks_like_resolvable_symbol(normalize_symbol_target(text))
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", text))


def _extract_dict_pairs(node: ast.AST | None) -> list[tuple[str, str]]:
    if not isinstance(node, ast.Dict):
        return []
    pairs: list[tuple[str, str]] = []
    for key_node, value_node in zip(node.keys, node.values):
        if not (
            isinstance(key_node, ast.Constant)
            and isinstance(key_node.value, str)
        ):
            continue
        for target in _extract_string_candidates(value_node):
            pairs.append((key_node.value.strip(), target))
    return list(dict.fromkeys(pairs))


def _render_target_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _render_target_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _normalize_key(value: str) -> str:
    return value.strip().lower()


def _entry_file_to_module(entry_file: str) -> str:
    if not entry_file:
        return ""
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


def _extract_reference_keys(
    question: str,
    *,
    entry_symbol: str = "",
    entry_file: str = "",
) -> set[str]:
    keys: set[str] = set()
    for text in (question, entry_symbol):
        for match in _CODE_REF_PATTERN.findall(text):
            keys.add(_normalize_key(match))
            if match.count(".") <= 1:
                keys.add(_normalize_key(match.rsplit(".", 1)[-1]))
        for quoted in _QUOTED_TEXT_PATTERN.findall(text):
            if "." in quoted and "://" not in quoted:
                keys.add(_normalize_key(quoted))
                if quoted.count(".") <= 1:
                    keys.add(_normalize_key(quoted.rsplit(".", 1)[-1]))
    for token in _tokenize(question):
        if token in _HIGH_SIGNAL_TOKENS:
            keys.add(token)
    for token in _tokenize(entry_symbol):
        keys.add(token)
    for token in _tokenize(entry_file.replace("/", ".")):
        if token in _HIGH_SIGNAL_TOKENS:
            keys.add(token)
    return keys


def _should_keep_dynamic_binding(
    *,
    key: str,
    raw_target: str,
    match_type: str,
) -> bool:
    if match_type in {"dict_alias", "dict_regex", "symbol_by_name_literal"}:
        return True

    key_tokens = set(_tokenize(_normalize_key(key)))
    target_tokens = set(_tokenize(normalize_symbol_target(raw_target)))

    if key_tokens & _HIGH_SIGNAL_TOKENS:
        return True
    if match_type in {"assignment", "return_literal"} and target_tokens & _HIGH_SIGNAL_TOKENS:
        return True
    return False


def _dedupe_alias_targets(values: Sequence[AliasTarget]) -> list[AliasTarget]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[AliasTarget] = []
    for value in sorted(
        values,
        key=lambda item: (
            -item.confidence,
            item.alias.lower(),
            item.target_symbol,
            item.match_type,
        ),
    ):
        key = (
            value.alias.lower(),
            value.target_symbol,
            value.source_symbol,
            value.match_type,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _dedupe_resolved_targets(
    values: Sequence[tuple[str, tuple[str, ...], int]]
) -> list[tuple[str, tuple[str, ...], int]]:
    seen: set[str] = set()
    deduped: list[tuple[str, tuple[str, ...], int]] = []
    for target_symbol, target_chunk_ids, depth in sorted(values, key=lambda item: (item[2], item[0])):
        if target_symbol in seen:
            continue
        seen.add(target_symbol)
        deduped.append((target_symbol, target_chunk_ids, depth))
    return deduped


def _alias_candidates(value: str) -> set[str]:
    candidates = {_normalize_key(value)}
    text = value.strip()
    if "://" in text:
        scheme = text.split("://", 1)[0]
        if "+" in scheme:
            scheme = scheme.split("+", 1)[0]
        if scheme:
            candidates.add(_normalize_key(scheme))
    if ":" in text and "." in text:
        candidates.add(_normalize_key(normalize_symbol_target(text)))
    return {candidate for candidate in candidates if candidate}


def _looks_like_resolvable_symbol(value: str) -> bool:
    if "." not in value:
        return False
    parts = value.split(".")
    return all(part and (part[0].isalpha() or part[0] == "_") for part in parts)


def _confidence_bonus(content: str) -> float:
    lowered = content.lower()
    bonus = 0.0
    if "symbol_by_name" in lowered or "instantiate(" in lowered:
        bonus += 0.12
    if "alias" in lowered or "loader" in lowered or "backend" in lowered:
        bonus += 0.08
    return bonus


def _extract_alias_pairs_fallback(content: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for match in _DICT_ALIAS_PATTERN.finditer(content):
        alias = match.group("alias")
        target = match.group("target")
        if alias and target:
            pairs.append((alias, target))
    return pairs


def _format_alias_hits(alias_hits: Sequence[AliasTarget]) -> str:
    if not alias_hits:
        return ""
    lines = ["[Dynamic Alias Map]"]
    for hit in alias_hits[:8]:
        lines.append(
            f"{hit.alias!r} -> {hit.target_symbol} "
            f"(type={hit.match_type}, source={hit.source_symbol})"
        )
    return "\n".join(lines)


def build_dynamic_symbol_retriever(
    repo_root: Path | str,
) -> DynamicSymbolEnhancedRetriever:
    return DynamicSymbolEnhancedRetriever.from_repo(repo_root)
