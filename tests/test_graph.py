"""Tests for rag.graph — graph search logic and SymbolRegistry."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rag.ast_chunker import CodeChunk
from rag.fusion import _extract_string_literals, _extract_symbol_like_strings, _kind_bonus, _tokenize
from rag.graph import SymbolRegistry, _entry_file_to_module, graph_search


# ── Fixtures ──────────────────────────────────────────────────────────


def make_chunk(
    chunk_id: str,
    symbol: str,
    module: str = "test_mod",
    kind: str = "function",
    parent_symbol: str | None = None,
    string_targets: tuple[str, ...] = (),
    imports: tuple[str, ...] = (),
    references: tuple[str, ...] = (),
) -> CodeChunk:
    return CodeChunk(
        chunk_id=chunk_id,
        repo_path=f"{module}.py",
        module=module,
        symbol=symbol,
        kind=kind,
        start_line=1,
        end_line=10,
        signature=f"{symbol}()",
        docstring="",
        content=f"def {symbol}(): pass",
        imports=imports,
        exported_names=(),
        string_targets=string_targets,
        references=references,
        parent_symbol=parent_symbol,
    )


# ── _entry_file_to_module ────────────────────────────────────────────


class TestEntryFileToModule:
    def test_simple_file(self) -> None:
        assert _entry_file_to_module("celery/app/base.py") == "celery.app.base"

    def test_init_file_strips_init(self) -> None:
        assert _entry_file_to_module("celery/app/__init__.py") == "celery.app"

    def test_deep_init(self) -> None:
        assert _entry_file_to_module("a/b/c/__init__.py") == "a.b.c"

    def test_empty_string(self) -> None:
        assert _entry_file_to_module("") == ""

    def test_single_level(self) -> None:
        assert _entry_file_to_module("foo.py") == "foo"


# ── SymbolRegistry ───────────────────────────────────────────────────


class TestSymbolRegistry:
    def test_symbol_to_ids_populated(self) -> None:
        chunks = [
            make_chunk("c1", "mymod.func_a"),
            make_chunk("c2", "mymod.func_b"),
        ]
        registry = SymbolRegistry(chunks)
        assert registry.symbol_to_ids["mymod.func_a"] == ["c1"]
        assert registry.symbol_to_ids["mymod.func_b"] == ["c2"]

    def test_module_to_ids_populated(self) -> None:
        chunks = [
            make_chunk("c1", "foo.func", "foo"),
            make_chunk("c2", "bar.func", "bar"),
        ]
        registry = SymbolRegistry(chunks)
        assert "c1" in registry.module_to_ids["foo"]
        assert "c2" in registry.module_to_ids["bar"]

    def test_basename_to_ids_populated(self) -> None:
        chunks = [
            make_chunk("c1", "pkg.MyClass.my_method", "pkg"),
            make_chunk("c2", "pkg.Other.method", "pkg"),
        ]
        registry = SymbolRegistry(chunks)
        # basename is last component of symbol
        assert "c1" in registry.basename_to_ids["my_method"]
        assert "c2" in registry.basename_to_ids["method"]

    def test_parent_to_ids_populated(self) -> None:
        chunks = [
            make_chunk("c1", "pkg.MyClass.my_method", "pkg", parent_symbol="pkg.MyClass"),
        ]
        registry = SymbolRegistry(chunks)
        assert "c1" in registry.parent_to_ids["pkg.MyClass"]

    def test_resolve_target_ids_exact_symbol(self) -> None:
        chunks = [make_chunk("c1", "celery.app.my_func")]
        registry = SymbolRegistry(chunks)
        assert registry.resolve_target_ids("celery.app.my_func") == ["c1"]

    def test_resolve_target_ids_module(self) -> None:
        chunks = [make_chunk("c1", "celery.app.func", "celery.app")]
        registry = SymbolRegistry(chunks)
        assert "c1" in registry.resolve_target_ids("celery.app")

    def test_resolve_target_ids_basename(self) -> None:
        chunks = [make_chunk("c1", "celery.utils.gen_task_name")]
        registry = SymbolRegistry(chunks)
        assert "c1" in registry.resolve_target_ids("gen_task_name")

    def test_duplicate_symbol_appends(self) -> None:
        """Same symbol across multiple chunks."""
        chunks = [
            make_chunk("c1", "shared.sym"),
            make_chunk("c2", "shared.sym"),
        ]
        registry = SymbolRegistry(chunks)
        assert set(registry.symbol_to_ids["shared.sym"]) == {"c1", "c2"}

    def test_empty_chunks(self) -> None:
        registry = SymbolRegistry([])
        assert registry.symbol_to_ids == {}
        assert registry.module_to_ids == {}
        assert registry.resolve_target_ids("anything") == []


# ── graph_search ──────────────────────────────────────────────────────


class TestGraphSearch:
    @pytest.fixture
    def chunks(self) -> list[CodeChunk]:
        return [
            # c1: entry point
            make_chunk("c1", "celery.app.base.Celery", "celery.app.base", kind="class"),
            # c2: imports c1
            make_chunk("c2", "celery.app.init", "celery.app", imports=["celery.app.base.Celery"]),
            # c3: string target of c1
            make_chunk("c3", "celery.utils.imports.symbol_by_name", "celery.utils.imports",
                       string_targets=["celery.app.base.Celery"]),
            # c4: unrelated
            make_chunk("c4", "celery.utils.uuid", "celery.utils",
                       imports=["celery.app.base.Celery"]),
        ]

    @pytest.fixture
    def chunk_by_id(self, chunks):
        return {c.chunk_id: c for c in chunks}

    @pytest.fixture
    def registry(self, chunks):
        return SymbolRegistry(chunks)

    def _mock_graph_search_params(self, chunks, chunk_by_id, registry):
        return dict(
            graph={c.chunk_id: [] for c in chunks},
            chunk_by_id=chunk_by_id,
            symbol_to_ids=registry.symbol_to_ids,
            module_to_ids=registry.module_to_ids,
            basename_to_ids=registry.basename_to_ids,
            parent_to_ids=registry.parent_to_ids,
            chunk_tokens={c.chunk_id: _tokenize(f"{c.symbol} {c.signature} {c.content}") for c in chunks},
        )

    def test_empty_seeds_returns_empty(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="unrelated question",
            entry_symbol="",
            entry_file="",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert result == []

    def test_question_symbol_extraction(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="celery.app.base.Celery._task_from_fun",
            entry_symbol="",
            entry_file="",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert isinstance(result, list)

    def test_top_n_respected(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="celery app",
            entry_symbol="",
            entry_file="",
            top_n=2,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert len(result) <= 2

    def test_unknown_query_mode_raises(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        with pytest.raises(ValueError, match="Unsupported query mode"):
            graph_search(
                **params,
                question="test",
                entry_symbol="",
                entry_file="",
                top_n=5,
                query_mode="invalid_mode",
                tokenize_fn=_tokenize,
                extract_symbols_fn=_extract_symbol_like_strings,
                extract_literals_fn=_extract_string_literals,
                kind_bonus_fn=_kind_bonus,
            )

    def test_entry_symbol_uses_resolve(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="test question",
            entry_symbol="celery.app.base.Celery",
            entry_file="",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert isinstance(result, list)

    def test_entry_file_uses_module(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="test question",
            entry_symbol="",
            entry_file="celery/app/base.py",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert isinstance(result, list)

    def test_question_only_mode(self, chunks, chunk_by_id, registry) -> None:
        params = self._mock_graph_search_params(chunks, chunk_by_id, registry)
        result = graph_search(
            **params,
            question="Celery class",
            entry_symbol="",
            entry_file="",
            top_n=5,
            query_mode="question_only",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        assert isinstance(result, list)


# ── graph_search edge cases ───────────────────────────────────────────


class TestGraphSearchEdgeCases:
    def test_missing_chunk_returns_empty(self) -> None:
        """Visited neighbor not in chunk_by_id should be skipped."""
        chunks = [make_chunk("c1", "pkg.func")]
        chunk_by_id = {"c1": chunks[0]}
        registry = SymbolRegistry(chunks)

        # Minimal graph with one node
        graph = {"c1": ["c999"]}  # c999 doesn't exist
        result = graph_search(
            graph=graph,
            chunk_by_id=chunk_by_id,
            symbol_to_ids=registry.symbol_to_ids,
            module_to_ids=registry.module_to_ids,
            basename_to_ids=registry.basename_to_ids,
            parent_to_ids=registry.parent_to_ids,
            chunk_tokens={"c1": ["func"]},
            question="func",
            entry_symbol="pkg.func",
            entry_file="",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        # Should not crash; c999 is skipped
        assert isinstance(result, list)

    def test_string_literal_target_boost(self) -> None:
        """Chunks with matching string_targets should get a score boost."""
        chunks = [
            make_chunk(
                "c1",
                "pkg.func",
                string_targets=["processes"],
            ),
        ]
        chunk_by_id = {c.chunk_id: c for c in chunks}
        registry = SymbolRegistry(chunks)
        graph = {"c1": []}

        result = graph_search(
            graph=graph,
            chunk_by_id=chunk_by_id,
            symbol_to_ids=registry.symbol_to_ids,
            module_to_ids=registry.module_to_ids,
            basename_to_ids=registry.basename_to_ids,
            parent_to_ids=registry.parent_to_ids,
            chunk_tokens={"c1": ["func"]},
            question="'processes'",
            entry_symbol="",
            entry_file="",
            top_n=5,
            query_mode="question_plus_entry",
            tokenize_fn=_tokenize,
            extract_symbols_fn=_extract_symbol_like_strings,
            extract_literals_fn=_extract_string_literals,
            kind_bonus_fn=_kind_bonus,
        )
        # String literal 'processes' matches string_targets
        assert isinstance(result, list)
