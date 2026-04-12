"""
AST代码分块模块

功能：
- 将Python源码解析为AST（抽象语法树）
- 按函数/类/模块级别精确切分代码块
- 提取每个代码块的元数据（导入、导出、字符串目标、引用等）

核心数据结构：
- CodeChunk: 代表一个代码块，包含符号名、签名、文档字符串、import列表等

与暴力字符分块（512字符硬切）的区别：
- 保留完整的函数/类定义
- 保留语法结构信息
- 便于后续检索和依赖分析
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# 统一规范化函数
from .normalize_utils import normalize_symbol_target


# 字符串目标匹配模式：匹配形如 "celery.app.trace.build_tracer" 的符号路径
_STRING_TARGET_PATTERN = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+$"
)


@dataclass(frozen=True)
class CodeChunk:
    """
    代码块数据结构

    代表仓库中的一个可检索代码单元。

    Attributes:
        chunk_id: 唯一标识符，格式为 "repo_path::module.symbol:start-end"
        repo_path: 相对于仓库根目录的文件路径
        module: 模块名（点分隔格式）
        symbol: 符号名（函数/类名，含完整路径）
        kind: 类型 (module/class/function/async_function/method)
        start_line: 起始行号
        end_line: 结束行号
        signature: 函数/类的签名行
        docstring: 文档字符串
        content: 代码内容
        imports: 导入的模块/符号元组
        exported_names: 通过 __all__ 导出的名称
        string_targets: 字符串形式的符号引用（如 importlib路径）
        references: 代码中引用的其他符号
        parent_symbol: 父符号（对于类方法而言）
    """

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


def module_name_from_path(path: Path, repo_root: Path) -> str:
    """
    从文件路径推导模块名

    处理 __init__.py 的特殊情况，将其转换为包路径。

    Examples:
        celery/app/base.py -> celery.app.base
        celery/app/__init__.py -> celery.app
    """
    relative = path.resolve().relative_to(repo_root.resolve())
    parts = list(relative.parts)
    if not parts:
        return ""
    parts[-1] = Path(parts[-1]).stem
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(part for part in parts if part)


def discover_python_files(repo_root: Path) -> list[Path]:
    """递归发现仓库中所有Python文件"""
    return sorted(path for path in repo_root.rglob("*.py") if path.is_file())


def chunk_python_file(path: Path, repo_root: Path) -> list[CodeChunk]:
    """
    将单个Python文件分块

    Args:
        path: Python文件路径
        repo_root: 仓库根目录

    Returns:
        代码块列表
    """
    repo_root = repo_root.resolve()
    module_name = module_name_from_path(path, repo_root)
    repo_path = path.resolve().relative_to(repo_root).as_posix()
    source = path.read_text(encoding="utf-8")
    return chunk_python_source(
        module_name=module_name, source=source, repo_path=repo_path
    )


def chunk_repository(repo_root: Path | str) -> list[CodeChunk]:
    """
    对整个仓库进行代码分块

    遍历所有Python文件，生成完整的代码块索引。
    """
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
    """
    将Python源码解析为代码块列表

    处理流程：
    1. 解析AST
    2. 为整个模块创建一个块（包含模块级import和docstring）
    3. 递归遍历顶层定义（函数/类），为每个创建一个块
    4. 对于类，递归遍历其内部方法

    Args:
        module_name: 模块名
        source: Python源码
        repo_path: 文件路径标识

    Returns:
        代码块列表
    """
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
    """
    为模块级别创建代码块

    收集模块级的import、__all__导出、字符串目标和代码引用。
    排除已分配给函数/类定义的内容。
    """
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
    """
    递归收集函数/类定义代码块

    对于类定义，会递归处理其内部的方法和嵌套类。
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return []

    symbol = (
        f"{parent_symbol}.{node.name}"
        if parent_symbol
        else f"{module_name}.{node.name}"
    )
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
    """
    获取节点的起始行号

    考虑装饰器列表，返回第一个装饰器或节点本身的行号。
    """
    decorators = getattr(node, "decorator_list", None) or []
    if decorators:
        return min(
            getattr(item, "lineno", getattr(node, "lineno", 1)) for item in decorators
        )
    return getattr(node, "lineno", 1)


def _chunk_kind(node: ast.AST, parent_symbol: str | None) -> str:
    """
    判断代码块的类型

    Returns:
        - "class": 类定义
        - "method": 类的方法
        - "async_function": 异步函数
        - "function": 普通函数
    """
    if isinstance(node, ast.ClassDef):
        return "class"
    if parent_symbol:
        return "method"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    return "function"


def _extract_signature(node: ast.AST, lines: list[str]) -> str:
    """
    提取函数/类的签名行

    从起始行开始查找包含 def/class 关键字的行。
    """
    candidate_prefixes = ("def ", "async def ", "class ")
    for line_number in range(
        _node_start_line(node), getattr(node, "end_lineno", _node_start_line(node)) + 1
    ):
        line = lines[line_number - 1].strip()
        if line.startswith(candidate_prefixes):
            return line
    return lines[getattr(node, "lineno", 1) - 1].strip()


def _collect_import_targets(tree: ast.AST, module_name: str) -> list[str]:
    """
    收集导入目标

    处理 import xxx 和 from xxx import yyy 两种形式。
    返回完整的模块/符号路径。
    """
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
    """
    收集通过 __all__ 导出的名称

    只处理在 __all__ 赋值右侧的字符串常量列表。
    """
    exported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = []
        if isinstance(node, ast.Assign):
            targets = [
                target for target in node.targets if isinstance(target, ast.Name)
            ]
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
    """
    收集字符串形式的符号引用

    匹配形如 "celery.app.trace.build_tracer" 的字符串常量。
    这些通常是动态导入的目标路径。
    """
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip()
            if _STRING_TARGET_PATTERN.match(value):
                targets.add(normalize_symbol_target(value))
    return sorted(targets)


def _collect_references(tree: ast.AST) -> list[str]:
    """
    收集代码中的符号引用

    通过遍历 Call、Attribute、Name 节点收集。
    """
    collector = _ReferenceCollector()
    collector.visit(tree)
    return sorted(collector.references)


def _resolve_import_from(
    module_name: str, imported_module: str | None, level: int
) -> str:
    """
    解析相对导入的模块路径

    Args:
        module_name: 当前模块名
        imported_module: 导入的模块名
        level: 相对导入层级（1表示上级，2表示上上级）

    Returns:
        解析后的完整模块路径
    """
    if level <= 0:
        return imported_module or ""

    package_parts = module_name.split(".")[:-1]
    trim = max(level - 1, 0)
    if trim:
        package_parts = package_parts[: len(package_parts) - trim]
    extra_parts = imported_module.split(".") if imported_module else []
    return ".".join(part for part in [*package_parts, *extra_parts] if part)


class _ReferenceCollector(ast.NodeVisitor):
    """
    AST访问器：收集代码中的符号引用

    收集：
    - 函数调用（visit_Call）
    - 属性访问（visit_Attribute）
    - 名称引用（visit_Name）
    """

    def __init__(self) -> None:
        self.references: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        """收集函数调用"""
        name = _expression_to_reference(node.func)
        if name:
            self.references.add(name)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """收集属性访问"""
        name = _expression_to_reference(node)
        if name:
            self.references.add(name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """收集名称引用"""
        self.references.add(node.id)


def _expression_to_reference(node: ast.AST) -> str:
    """
    将表达式节点转换为符号引用字符串

    Examples:
        Name("foo") -> "foo"
        Attribute(Value, "attr") -> "value.attr"
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expression_to_reference(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def summarize_chunk(chunk: CodeChunk, max_lines: int = 12) -> str:
    """
    生成代码块的摘要文本

    如果代码块行数超过max_lines，只返回前max_lines行。
    """
    content_lines = chunk.content.splitlines()
    if len(content_lines) <= max_lines:
        return chunk.content
    head = content_lines[:max_lines]
    return "\n".join([*head, "..."])


def iter_module_symbols(
    chunks: Iterable[CodeChunk], module_name: str
) -> list[CodeChunk]:
    """获取指定模块的所有代码块"""
    return [chunk for chunk in chunks if chunk.module == module_name]
