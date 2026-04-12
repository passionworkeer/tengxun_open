"""Tests for rag.ast_chunker module."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag.ast_chunker import (
    CodeChunk,
    chunk_python_source,
    chunk_python_file,
    module_name_from_path,
    normalize_symbol_target,
)


# Fixture file paths relative to tests directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# Tests for chunk_python_source()
# =============================================================================

class TestChunkPythonSource:
    """Tests for the main chunk_python_source function."""

    def test_chunk_simple_function(self):
        """Test chunking a file with simple function definitions."""
        source = '''"""Simple Celery task example."""


def build_tracer(app, name, loader=None):
    """Build a tracer for a task."""
    return app.trace


async def async_build_tracer(app, name):
    """Async tracer builder."""
    return app.trace
'''
        chunks = chunk_python_source("simple_celery", source, "simple_celery.py")

        # Should have module chunk + 2 function chunks
        assert len(chunks) == 3

        # Check module chunk
        module_chunk = chunks[0]
        assert module_chunk.kind == "module"
        assert module_chunk.module == "simple_celery"
        assert "celery" in module_chunk.docstring.lower()

        # Check function chunks
        func_chunks = [c for c in chunks if c.kind == "function"]
        assert len(func_chunks) == 1
        assert func_chunks[0].symbol == "simple_celery.build_tracer"
        assert "tracer" in func_chunks[0].signature.lower()

        async_chunks = [c for c in chunks if c.kind == "async_function"]
        assert len(async_chunks) == 1
        assert async_chunks[0].symbol == "simple_celery.async_build_tracer"

    def test_chunk_class_definition(self):
        """Test chunking a file with class definition."""
        source = '''"""Celery app trace module."""


class TraceBuilder:
    """Trace builder for celery tasks."""

    def __init__(self, app):
        self.app = app

    def build_tracer(self, task):
        """Build tracer method."""
        return self.app.trace
'''
        chunks = chunk_python_source("trace_builder", source, "trace_builder.py")

        # Should have module chunk + class chunk + 2 method chunks
        assert len(chunks) == 4

        # Check class chunk
        class_chunk = [c for c in chunks if c.kind == "class"][0]
        assert class_chunk.symbol == "trace_builder.TraceBuilder"
        assert "Trace builder" in class_chunk.docstring
        assert class_chunk.parent_symbol is None

        # Check method chunks
        method_chunks = [c for c in chunks if c.kind == "method"]
        assert len(method_chunks) == 2
        method_symbols = {m.symbol for m in method_chunks}
        assert "trace_builder.TraceBuilder.__init__" in method_symbols
        assert "trace_builder.TraceBuilder.build_tracer" in method_symbols

    def test_chunk_with_decorators(self):
        """Test chunking functions with decorators."""
        source = '''"""Decorated functions."""


def my_decorator(func):
    """A simple decorator."""
    return func


@my_decorator
def decorated_function(x):
    """Function with decorator."""
    return x * 2
'''
        chunks = chunk_python_source("decorated", source, "decorated.py")

        func_chunks = [c for c in chunks if c.kind == "function"]
        assert len(func_chunks) == 2

        # Decorated function should have correct start line
        decorated = next(c for c in func_chunks if "decorated_function" in c.symbol)
        assert decorated.start_line > 1  # Decorator adds lines
        assert decorated.signature.startswith("def decorated_function")


# =============================================================================
# Tests for _collect_definition_chunks() via public API
# =============================================================================

class TestCollectDefinitionChunks:
    """Tests for definition collection (tested via public API)."""

    def test_collect_class_with_methods(self):
        """Test that class methods are properly collected."""
        source = '''"""Test module."""


class MyClass:
    """A test class."""

    def method_one(self):
        pass

    def method_two(self):
        pass
'''
        chunks = chunk_python_source("my_class", source, "my_class.py")

        class_chunk = [c for c in chunks if c.kind == "class"][0]
        method_chunks = [c for c in chunks if c.kind == "method"]

        assert class_chunk.symbol == "my_class.MyClass"
        assert len(method_chunks) == 2

        # All methods should have correct parent
        for method in method_chunks:
            assert method.parent_symbol == "my_class.MyClass"

    def test_collect_nested_class(self):
        """Test that nested classes are properly collected."""
        source = '''"""Nested classes."""


class Outer:
    """Outer class."""

    class Inner:
        """Inner class."""

        def inner_method(self):
            pass
'''
        chunks = chunk_python_source("nested", source, "nested.py")

        outer = next(c for c in chunks if c.symbol == "nested.Outer")
        inner = next(c for c in chunks if c.symbol == "nested.Outer.Inner")
        method = next(c for c in chunks if "inner_method" in c.symbol)

        assert outer.kind == "class"
        assert inner.kind == "class"
        assert inner.parent_symbol == "nested.Outer"
        assert method.parent_symbol == "nested.Outer.Inner"

    def test_async_function_detection(self):
        """Test that async functions are properly detected."""
        source = '''"""Async test."""


async def async_task():
    """An async task."""
    pass
'''
        chunks = chunk_python_source("async_test", source, "async_test.py")

        async_chunks = [c for c in chunks if c.kind == "async_function"]
        assert len(async_chunks) == 1
        assert "async_task" in async_chunks[0].symbol


# =============================================================================
# Tests for _collect_string_targets() via public API
# =============================================================================

class TestCollectStringTargets:
    """Tests for string target collection (tested via public API)."""

    def test_collect_string_import_paths(self):
        """Test collecting string literal import paths."""
        source = '''"""Module with string targets."""


TRACE_TARGET = "celery.app.trace.build_tracer"
ASYNC_TARGET = "celery.decorators.async_task"
'''
        chunks = chunk_python_source("string_targets", source, "string_targets.py")

        # Get all string_targets across chunks
        all_targets = set()
        for chunk in chunks:
            all_targets.update(chunk.string_targets)

        assert "celery.app.trace.build_tracer" in all_targets
        assert "celery.decorators.async_task" in all_targets

    def test_collect_colon_separated_paths(self):
        """Test that colon-separated paths are normalized."""
        source = '''"""Module with colon paths."""


TASK_PATH = "celery.app.base:task_from_fun"
'''
        chunks = chunk_python_source("colon_paths", source, "colon_paths.py")

        all_targets = set()
        for chunk in chunks:
            all_targets.update(chunk.string_targets)

        # Colons should be converted to dots
        assert "celery.app.base.task_from_fun" in all_targets


# =============================================================================
# Tests for boundary conditions
# =============================================================================

class TestBoundaryConditions:
    """Tests for edge cases and boundary conditions."""

    def test_empty_file(self):
        """Test chunking an empty file."""
        source = ""
        chunks = chunk_python_source("empty", source, "empty.py")

        assert len(chunks) == 1
        assert chunks[0].kind == "module"
        assert chunks[0].symbol == "empty"

    def test_comments_only_file(self):
        """Test chunking a file with only comments."""
        source = '''# Comment line 1
# Comment line 2
# Comment line 3
'''
        chunks = chunk_python_source("comments", source, "comments.py")

        assert len(chunks) == 1
        assert chunks[0].kind == "module"

    def test_imports_only_file(self):
        """Test chunking a file with only imports."""
        source = '''"""Imports only."""


from celery import Celery
from celery.app import trace
import os
'''
        chunks = chunk_python_source("imports", source, "imports.py")

        module_chunk = chunks[0]
        assert module_chunk.kind == "module"
        # Imports include: celery, celery.Celery, celery.app, celery.app.trace, os
        assert len(module_chunk.imports) == 5
        assert "celery" in module_chunk.imports
        assert "celery.app.trace" in module_chunk.imports

    def test_no_imports_no_code(self):
        """Test module with neither imports nor definitions."""
        source = '"""Just a docstring."""'
        chunks = chunk_python_source("just_docstring", source, "just_docstring.py")

        assert len(chunks) == 1
        assert chunks[0].kind == "module"
        assert "docstring" in chunks[0].docstring.lower()


# =============================================================================
# Tests for normalize_symbol_target()
# =============================================================================

class TestNormalizeSymbolTarget:
    """Tests for symbol target normalization."""

    def test_normalize_single_quotes(self):
        """Test normalizing single-quoted strings."""
        result = normalize_symbol_target("'celery.app.trace'")
        assert result == "celery.app.trace"

    def test_normalize_double_quotes(self):
        """Test normalizing double-quoted strings."""
        result = normalize_symbol_target('"celery.app.trace"')
        assert result == "celery.app.trace"

    def test_normalize_colon_separator(self):
        """Test normalizing colon-separated paths."""
        result = normalize_symbol_target("'celery:app:trace'")
        assert result == "celery.app.trace"

    def test_normalize_whitespace(self):
        """Test normalizing strings with whitespace."""
        result = normalize_symbol_target("  'celery.app.trace'  ")
        assert result == "celery.app.trace"


# =============================================================================
# Tests for module_name_from_path()
# =============================================================================

class TestModuleNameFromPath:
    """Tests for module name derivation from paths."""

    def test_regular_module(self, tmp_path):
        """Test regular module path."""
        repo_root = tmp_path / "myrepo"
        repo_root.mkdir(parents=True)
        file_path = repo_root / "celery" / "app" / "base.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        module = module_name_from_path(file_path, repo_root)
        assert module == "celery.app.base"

    def test_init_module(self, tmp_path):
        """Test __init__.py path becomes package name."""
        repo_root = tmp_path / "myrepo"
        repo_root.mkdir(parents=True)
        file_path = repo_root / "celery" / "app" / "__init__.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        module = module_name_from_path(file_path, repo_root)
        assert module == "celery.app"


# =============================================================================
# Tests for chunk_python_file()
# =============================================================================

class TestChunkPythonFile:
    """Tests for file-based chunking."""

    def test_chunk_file_from_disk(self):
        """Test chunking actual file from disk."""
        fixture_path = FIXTURES_DIR / "simple_function.py"
        repo_root = FIXTURES_DIR.parent

        chunks = chunk_python_file(fixture_path, repo_root)

        assert len(chunks) > 0
        assert all(isinstance(c, CodeChunk) for c in chunks)

    def test_chunk_imports_only_file(self):
        """Test chunking file with only imports."""
        fixture_path = FIXTURES_DIR / "imports_only.py"
        repo_root = FIXTURES_DIR.parent

        chunks = chunk_python_file(fixture_path, repo_root)

        module_chunk = chunks[0]
        assert "celery" in module_chunk.imports
        assert "os" in module_chunk.imports


# =============================================================================
# Tests for CodeChunk structure
# =============================================================================

class TestCodeChunkStructure:
    """Tests for CodeChunk dataclass structure."""

    def test_chunk_has_required_fields(self):
        """Test that chunks have all required fields."""
        chunks = chunk_python_source("test", "def foo(): pass", "test.py")

        chunk = chunks[0]
        assert hasattr(chunk, "chunk_id")
        assert hasattr(chunk, "repo_path")
        assert hasattr(chunk, "module")
        assert hasattr(chunk, "symbol")
        assert hasattr(chunk, "kind")
        assert hasattr(chunk, "start_line")
        assert hasattr(chunk, "end_line")
        assert hasattr(chunk, "signature")
        assert hasattr(chunk, "docstring")
        assert hasattr(chunk, "content")
        assert hasattr(chunk, "imports")
        assert hasattr(chunk, "string_targets")
        assert hasattr(chunk, "references")

    def test_chunk_id_format(self):
        """Test that chunk_id follows expected format."""
        source = 'def foo(): pass'
        chunks = chunk_python_source("mymodule", source, "mymodule.py")

        func_chunk = [c for c in chunks if c.kind == "function"][0]
        assert "::" in func_chunk.chunk_id
        assert "mymodule.foo" in func_chunk.chunk_id

    def test_function_chunk_immutability(self):
        """Test that CodeChunk is immutable (frozen dataclass)."""
        chunks = chunk_python_source("test", "def foo(): pass", "test.py")
        chunk = chunks[0]

        with pytest.raises(AttributeError):
            chunk.symbol = "new_symbol"  # type: ignore
