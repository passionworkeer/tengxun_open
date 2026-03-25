from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_STRING_TARGET_PATTERN = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+$"
)


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    repo_path: str
    module: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    signature: str
    docstring: str
    content: str
    imports: tuple[str, ...] = ()
    exported_names: tuple[str, ...] = ()
    string_targets: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    parent_symbol: str | None = None


def normalize_symbol_target(value: str) -> str:
    return value.strip().strip("'").strip('"').replace(":", ".")


def module_name_from_path(path: Path, repo_root: Path) -> str:
    relative = path.resolve().relative_to(repo_root.resolve())
    parts = list(relative.parts)
    if not parts:
        return ""
    parts[-1] = Path(parts[-1]).stem
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(part for part in parts if part)


def discover_python_files(repo_root: Path) -> list[Path]:
    return sorted(path for path in repo_root.rglob("*.py") if path.is_file())


def chunk_python_file(path: Path, repo_root: Path) -> list[CodeChunk]:
    repo_root = repo_root.resolve()
    module_name = module_name_from_path(path, repo_root)
    repo_path = path.resolve().relative_to(repo_root).as_posix()
    source = path.read_text(encoding="utf-8")
    return chunk_python_source(module_name=module_name, source=source, repo_path=repo_path)


def chunk_repository(repo_root: Path | str) -> list[CodeChunk]:
    root = Path(repo_root).resolve()
    chunks: list[CodeChunk] = []
    for path in discover_python_files(root):
        chunks.extend(chunk_python_file(path=path, repo_root=root))
    return chunks


def chunk_python_source(
    module_name: str,
    source: str,
    repo_path: str = "<memory>",
) -> list[CodeChunk]:
    tree = ast.parse(source)
    lines = source.splitlines()
    module_chunk = _build_module_chunk(
        module_name=module_name,
        repo_path=repo_path,
        source=source,
        lines=lines,
        tree=tree,
    )
    chunks = [module_chunk]
    for node in tree.body:
        chunks.extend(
            _collect_definition_chunks(
                node=node,
                module_name=module_name,
                repo_path=repo_path,
                source=source,
                lines=lines,
                parent_symbol=None,
            )
        )
    return chunks


def _build_module_chunk(
    module_name: str,
    repo_path: str,
    source: str,
    lines: list[str],
    tree: ast.Module,
) -> CodeChunk:
    excluded_lines: set[int] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start_line = _node_start_line(node)
            end_line = getattr(node, "end_lineno", start_line)
            excluded_lines.update(range(start_line, end_line + 1))

    module_lines = [
        line
        for line_number, line in enumerate(lines, start=1)
        if line_number not in excluded_lines
    ]
    module_content = "\n".join(module_lines).strip() or source.strip()
    imports = tuple(_collect_import_targets(tree, module_name))
    string_targets = tuple(_collect_string_targets(tree))
    references = tuple(_collect_references(tree))
    exported_names = tuple(_collect_exported_names(tree))
    return CodeChunk(
        chunk_id=f"{repo_path}::{module_name or '<module>'}:1-{len(lines) or 1}",
        repo_path=repo_path,
        module=module_name,
        symbol=module_name,
        kind="module",
        start_line=1,
        end_line=max(len(lines), 1),
        signature=f"module {module_name}" if module_name else "module",
        docstring=ast.get_docstring(tree) or "",
        content=module_content,
        imports=imports,
        exported_names=exported_names,
        string_targets=string_targets,
        references=references,
        parent_symbol=None,
    )


def _collect_definition_chunks(
    node: ast.AST,
    module_name: str,
    repo_path: str,
    source: str,
    lines: list[str],
    parent_symbol: str | None,
) -> list[CodeChunk]:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []

    symbol = f"{parent_symbol}.{node.name}" if parent_symbol else f"{module_name}.{node.name}"
    start_line = _node_start_line(node)
    end_line = getattr(node, "end_lineno", start_line)
    content = "\n".join(lines[start_line - 1 : end_line])
    signature = _extract_signature(node=node, lines=lines)
    kind = _chunk_kind(node=node, parent_symbol=parent_symbol)

    chunk = CodeChunk(
        chunk_id=f"{repo_path}::{symbol}:{start_line}-{end_line}",
        repo_path=repo_path,
        module=module_name,
        symbol=symbol,
        kind=kind,
        start_line=start_line,
        end_line=end_line,
        signature=signature,
        docstring=ast.get_docstring(node) or "",
        content=content,
        imports=tuple(_collect_import_targets(node, module_name)),
        exported_names=(),
        string_targets=tuple(_collect_string_targets(node)),
        references=tuple(_collect_references(node)),
        parent_symbol=parent_symbol,
    )

    descendants = [chunk]
    if isinstance(node, ast.ClassDef):
        for child in node.body:
            descendants.extend(
                _collect_definition_chunks(
                    node=child,
                    module_name=module_name,
                    repo_path=repo_path,
                    source=source,
                    lines=lines,
                    parent_symbol=symbol,
                )
            )
    return descendants


def _node_start_line(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", None) or []
    if decorators:
        return min(getattr(item, "lineno", getattr(node, "lineno", 1)) for item in decorators)
    return getattr(node, "lineno", 1)


def _chunk_kind(node: ast.AST, parent_symbol: str | None) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if parent_symbol:
        return "method"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    return "function"


def _extract_signature(node: ast.AST, lines: list[str]) -> str:
    candidate_prefixes = ("def ", "async def ", "class ")
    for line_number in range(_node_start_line(node), getattr(node, "end_lineno", _node_start_line(node)) + 1):
        line = lines[line_number - 1].strip()
        if line.startswith(candidate_prefixes):
            return line
    return lines[getattr(node, "lineno", 1) - 1].strip()


def _collect_import_targets(tree: ast.AST, module_name: str) -> list[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                targets.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            resolved_module = _resolve_import_from(module_name, node.module, node.level)
            if resolved_module:
                targets.add(resolved_module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if resolved_module:
                    targets.add(f"{resolved_module}.{alias.name}")
    return sorted(targets)


def _collect_exported_names(tree: ast.AST) -> list[str]:
    exported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = []
        if isinstance(node, ast.Assign):
            targets = [target for target in node.targets if isinstance(target, ast.Name)]
            value = node.value
        else:
            if isinstance(node.target, ast.Name):
                targets = [node.target]
            value = node.value
        if not any(target.id == "__all__" for target in targets) or value is None:
            continue
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
            for item in value.elts:
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    exported.add(item.value)
    return sorted(exported)


def _collect_string_targets(tree: ast.AST) -> list[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip()
            if _STRING_TARGET_PATTERN.match(value):
                targets.add(normalize_symbol_target(value))
    return sorted(targets)


def _collect_references(tree: ast.AST) -> list[str]:
    collector = _ReferenceCollector()
    collector.visit(tree)
    return sorted(collector.references)


def _resolve_import_from(module_name: str, imported_module: str | None, level: int) -> str:
    if level <= 0:
        return imported_module or ""

    package_parts = module_name.split(".")[:-1]
    trim = max(level - 1, 0)
    if trim:
        package_parts = package_parts[: len(package_parts) - trim]
    extra_parts = imported_module.split(".") if imported_module else []
    return ".".join(part for part in [*package_parts, *extra_parts] if part)


class _ReferenceCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.references: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        name = _expression_to_reference(node.func)
        if name:
            self.references.add(name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _expression_to_reference(node)
        if name:
            self.references.add(name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.references.add(node.id)


def _expression_to_reference(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expression_to_reference(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def summarize_chunk(chunk: CodeChunk, max_lines: int = 12) -> str:
    content_lines = chunk.content.splitlines()
    if len(content_lines) <= max_lines:
        return chunk.content
    head = content_lines[:max_lines]
    return "\n".join([*head, "..."])


def iter_module_symbols(chunks: Iterable[CodeChunk], module_name: str) -> list[CodeChunk]:
    return [chunk for chunk in chunks if chunk.module == module_name]
