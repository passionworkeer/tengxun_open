"""
DependencyPathIndexer: 索引 symbol_by_name 调用链路径，而非孤立 chunks。

核心思路：
  当问题问 "Which class does `symbol_by_name('celery.backends.redis:RedisBackend')` resolve to?"
  我们不只是检索 RedisBackend 的定义 chunk，
  而是索引完整路径:
    symbol_by_name call → BACKEND_ALIASES['redis'] → 'celery.backends.redis:RedisBackend' → RedisBackend

Exports:
    DependencyPathIndexer
    PathInfo
    PathType
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator

if sys.version_info < (3, 9):
    pass  # polyfill if needed


# ─── Path type enum ───────────────────────────────────────────────────────────

class PathType(Enum):
    """路径类型"""
    DIRECT = "direct"          # 符号直接定义，无间接跳转
    ALIAS_LOOKUP = "alias"     # 经由 ALIASES/BACKEND_ALIASES/LOADER_ALIASES 查找
    DOT_CHAIN = "dot_chain"    # A.B.C 多级属性访问
    IMPLICIT = "implicit"      # 通过 symbol_by_name 隐式解析（跨模块）


# ─── PathInfo dataclass ───────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PathInfo:
    """
    符号解析路径信息

    Attributes:
        source_call: 调用 symbol_by_name 的代码位置 (file:lineno)
        source_symbol: 调用点的函数/方法名 (e.g. "celery.app.backends.by_name")
        alias_key: 使用的 alias 键 (e.g. "redis")，若无 alias 则为 None
        alias_dict: 使用的 alias 字典名 (e.g. "BACKEND_ALIASES")，若无则 None
        alias_target: alias 字典映射到的目标字符串 (e.g. "celery.backends.redis:RedisBackend")
        resolved_fqn: 最终解析到的完全限定名 (e.g. "celery.backends.redis.RedisBackend")
        path_type: 路径类型
        hops: 路径上的每一步描述
        entry_symbol: 问题的 entry_symbol (如果有)
        question_snippet: 相关问题片段（用于相关性匹配）
    """
    source_call: str          # "celery/app/backends.py:49"
    source_symbol: str         # "celery.app.backends.by_name"
    alias_key: str | None
    alias_dict: str | None
    alias_target: str | None
    resolved_fqn: str
    path_type: PathType
    hops: tuple[str, ...]
    entry_symbol: str = ""
    question_snippet: str = ""


# ─── Core indexer ─────────────────────────────────────────────────────────────

_ALIAS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(BACKEND_ALIASES|LOADER_ALIASES|ALIASES)\[", re.I),
    re.compile(r"symbol_by_name\s*\(", re.I),
    re.compile(r"import_object\s*\(", re.I),
    re.compile(r"instantiate\s*\(", re.I),
    re.compile(r"config_from_object\s*\(", re.I),
]


def _looks_like_alias_lookup(aliases_var: str) -> bool:
    """检查变量名是否像 alias 字典"""
    aliases_var = aliases_var.upper()
    return any(
        aliases_var.startswith(prefix)
        for prefix in ("BACKEND_", "LOADER_", "CELERY_", "")
        if aliases_var
    )


class DependencyPathIndexer:
    """
    索引 Celery 源码中 symbol_by_name 调用链。

    扫描所有调用 symbol_by_name 的代码位置，建立从调用点到最终解析目标
    的路径索引。用于解决 Type E（Hard 场景）的多跳符号解析问题。

    使用方式:
        indexer = DependencyPathIndexer("external/celery")
        indexer.build_index()

        # 检索
        paths = indexer.search_paths(
            question="Which backend class does celery.app.backends.by_name('redis') resolve to?",
            entry_symbol="celery.app.backends.by_name",
        )
    """

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root)
        self._paths: list[PathInfo] = []
        self._fqn_to_paths: dict[str, list[PathInfo]] = {}
        self._symbol_to_paths: dict[str, list[PathInfo]] = {}
        self._alias_map: dict[str, dict[str, str]] = {}  # alias_dict_name -> {key -> target}

        # 加载所有 alias 字典
        self._load_alias_dicts()

    # ── Alias dict loading ──────────────────────────────────────────────────

    def _load_alias_dicts(self) -> None:
        """扫描源码，提取所有 ALIASES-like 字典"""
        self._alias_map.clear()
        celery_root = self.repo_root / "celery"

        for pyfile in celery_root.rglob("*.py"):
            if "t/" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            self._scan_file_for_aliases(pyfile)

        # 也扫描 kombu（如果存在）
        kombu_root = self.repo_root / "kombu"
        if kombu_root.exists():
            for pyfile in kombu_root.rglob("*.py"):
                if "t/" in str(pyfile):
                    continue
                self._scan_file_for_aliases(pyfile)

    def _scan_file_for_aliases(self, pyfile: Path) -> None:
        """用 AST 解析单个文件，提取 alias 字典"""
        try:
            content = pyfile.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(pyfile))
        except (SyntaxError, OSError):
            return

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                var_name = target.id
                # 只关心 _ALIASES 变量
                if not (var_name.endswith("ALIASES") or var_name == "ALIASES"):
                    continue
                alias_dict = self._extract_alias_dict(node.value)
                if alias_dict:
                    key = f"{pyfile.stem}.{var_name}"  # e.g. "backends.BACKEND_ALIASES"
                    self._alias_map[key] = alias_dict

    def _extract_alias_dict(self, node: ast.AST) -> dict[str, str]:
        """从 AST 节点提取 {key: value} 字典"""
        if isinstance(node, ast.Dict):
            result: dict[str, str] = {}
            for k, v in zip(node.keys, node.values):
                if isinstance(k, (ast.Constant, ast.Str)) and isinstance(v, (ast.Constant, ast.Str)):
                    key = k.value if isinstance(k, ast.Constant) else k.s
                    val = v.value if isinstance(v, ast.Constant) else v.s
                    if isinstance(key, str) and isinstance(val, str):
                        result[key] = val
                elif isinstance(k, (ast.Constant, ast.Str)) and isinstance(v, ast.Constant) and isinstance(k.value if isinstance(k, ast.Constant) else k.s, str):
                    key = k.value if isinstance(k, ast.Constant) else k.s
                    val = v.value if isinstance(v, ast.Constant) else v.s
                    if isinstance(key, str) and isinstance(val, str):
                        result[key] = val
            return result
        return {}

    def _populate_alias_paths(self) -> None:
        """
        从已加载的 alias 字典直接预建路径索引。

        这是关键的一步：即使 Celery 源码中没有 `BACKEND_ALIASES['redis']`
        这样的字面量查找，我们也应该为 BACKEND_ALIASES 中的每个条目建立路径。
        因为问题会直接问 "by_name('redis') resolves to what?"，
        我们需要直接回答 'redis' -> 'celery.backends.redis:RedisBackend'。

        Deduplication: skip entries already added by _scan_file_for_alias_subscripts
        by checking self._paths for existing (alias_key, resolved_fqn) pairs.
        """
        seen_pairs: set[tuple[str | None, str]] = {
            (p.alias_key, p.resolved_fqn) for p in self._paths
        }

        for dict_name, mapping in self._alias_map.items():
            for key, target in mapping.items():
                resolved_fqn = self._resolve_symbol_name(target)
                pair = (key, resolved_fqn)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                # Determine the best source_call based on dict_name
                # e.g. "backends.BACKEND_ALIASES" -> "celery/app/backends.py"
                source_call = self._guess_source_file(dict_name)
                source_symbol = dict_name.replace(".", "/").rsplit("/", 1)[-1]

                hops: list[str] = [
                    f"ALIAS[{key!r}]",
                    f"-> {target!r}",
                    f"resolved: {resolved_fqn}",
                ]

                path_info = PathInfo(
                    source_call=source_call,
                    source_symbol=source_symbol,
                    alias_key=key,
                    alias_dict=dict_name.split(".")[-1],  # e.g. "BACKEND_ALIASES"
                    alias_target=target,
                    resolved_fqn=resolved_fqn,
                    path_type=PathType.ALIAS_LOOKUP,
                    hops=tuple(hops),
                )

                self._paths.append(path_info)
                self._fqn_to_paths.setdefault(resolved_fqn, []).append(path_info)
                self._symbol_to_paths.setdefault(source_symbol, []).append(path_info)

    def _guess_source_file(self, dict_name: str) -> str:
        """从 alias 字典名推断源文件路径"""
        # "backends.BACKEND_ALIASES" -> "celery/app/backends.py"
        parts = dict_name.split(".")
        if len(parts) >= 2:
            module = parts[0]
            dict_var = parts[1].replace("BACKEND_ALIASES", "backends").replace("LOADER_ALIASES", "loaders/__init__").replace("ALIASES", module)
            return f"celery/{module}/{dict_var.lower().replace('_aliases', 's') if '_aliases' in dict_var.lower() else dict_var.lower()}.py"
        return "celery/unknown.py"

    # ── Index building ─────────────────────────────────────────────────────

    def build_index(self) -> None:
        """扫描所有源文件，建立路径索引"""
        self._paths.clear()
        self._fqn_to_paths.clear()
        self._symbol_to_paths.clear()

        celery_root = self.repo_root / "celery"
        for pyfile in celery_root.rglob("*.py"):
            if "t/" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            self._scan_file_for_symbol_by_name(pyfile)
            self._scan_file_for_alias_subscripts(pyfile)

        # 关键：从已加载的 alias 字典直接预建路径
        # 这样即使源码中没有 BACKEND_ALIASES['redis'] 这样的字面量，
        # 我们也能索引 redis -> RedisBackend
        self._populate_alias_paths()

    def _scan_file_for_symbol_by_name(self, pyfile: Path) -> None:
        """扫描单个文件，提取所有 symbol_by_name 调用"""
        try:
            content = pyfile.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(pyfile))
        except (SyntaxError, OSError):
            return

        # 获取模块名
        module_name = self._module_name_from_path(pyfile)

        # 获取所有函数定义（用于确定调用点的函数上下文）
        func_defs: dict[int, str] = {}
        class_defs: dict[int, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_defs[node.lineno] = node.name
            elif isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        class_defs[method.lineno] = f"{node.name}.{method.name}"

        # 查找 symbol_by_name / import_object / instantiate 调用
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Name):
                continue
            if func.id not in ("symbol_by_name", "import_object", "instantiate"):
                continue

            lineno = node.lineno
            # 确定调用点的上下文函数
            context_func = ""
            for start_line in sorted(func_defs.keys(), reverse=True):
                if start_line < lineno:
                    context_func = func_defs[start_line]
                    break

            # 提取调用参数
            args = [a for a in node.args]
            if len(args) < 1:
                continue

            # 第一个参数：name 字符串
            name_arg = args[0]
            name_str = self._extract_string_literal(name_arg)
            if not name_str:
                continue

            # 第二个参数（可选）：aliases 字典
            aliases_arg = args[1] if len(args) > 1 else None
            alias_key: str | None = None
            alias_dict_name: str | None = None
            alias_target: str | None = None
            path_type = PathType.IMPLICIT

            if aliases_arg is not None:
                alias_dict_name, alias_key = self._resolve_alias_lookup(aliases_arg, name_str)
                if alias_dict_name and alias_key:
                    alias_target = self._lookup_alias(alias_dict_name, alias_key)
                    path_type = PathType.ALIAS_LOOKUP
                    if alias_target:
                        # 使用 alias 映射后的值
                        name_str = alias_target

            # 解析 name_str 为最终 FQN
            resolved_fqn = self._resolve_symbol_name(name_str)

            # 构建 hops 描述
            rel_path = str(pyfile.relative_to(self.repo_root))
            source_call = f"{rel_path}:{lineno}"
            source_symbol = f"{module_name}.{context_func}" if context_func else module_name

            hops: list[str] = [f"call {func.id}('{name_str}')"]
            if alias_dict_name and alias_key:
                hops.append(f"lookup {alias_dict_name}[{alias_key!r}] -> {alias_target!r}")
            elif path_type == PathType.IMPLICIT:
                hops.append("resolve via symbol_by_name")
            hops.append(f"resolved: {resolved_fqn}")

            path_info = PathInfo(
                source_call=source_call,
                source_symbol=source_symbol,
                alias_key=alias_key,
                alias_dict=alias_dict_name,
                alias_target=alias_target,
                resolved_fqn=resolved_fqn,
                path_type=path_type,
                hops=tuple(hops),
            )

            self._paths.append(path_info)
            self._fqn_to_paths.setdefault(resolved_fqn, []).append(path_info)
            self._symbol_to_paths.setdefault(source_symbol, []).append(path_info)

    def _scan_file_for_alias_subscripts(self, pyfile: Path) -> None:
        """
        扫描单个文件，提取 ALIASES[key] 字面量查找。

        这些是索引的关键：BACKEND_ALIASES['redis'] 这样的字面量查找
        直接映射到最终 FQN，不需要运行时求值。
        """
        try:
            content = pyfile.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(pyfile))
        except (SyntaxError, OSError):
            return

        module_name = self._module_name_from_path(pyfile)
        rel_path = str(pyfile.relative_to(self.repo_root))

        # Find enclosing function for each Subscript node
        func_defs: dict[int, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_defs[node.lineno] = node.name

        # Walk tree looking for ALIAS subscript lookups
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue

            # Check if this is an alias lookup: ALIASES['key'] or BACKEND_ALIASES['key']
            if not isinstance(node.value, ast.Name):
                continue
            var_name = node.value.id
            if not _looks_like_alias_lookup(var_name):
                continue

            key = self._extract_string_literal(node.slice)
            if not key:
                continue

            # Look up the alias value
            alias_target = self._lookup_alias(var_name, key)
            if not alias_target:
                continue

            # Resolve to FQN
            resolved_fqn = self._resolve_symbol_name(alias_target)

            # Determine enclosing function
            context_func = ""
            for start_line in sorted(func_defs.keys(), reverse=True):
                if start_line < node.lineno:
                    context_func = func_defs[start_line]
                    break

            source_call = f"{rel_path}:{node.lineno}"
            source_symbol = f"{module_name}.{context_func}" if context_func else module_name

            hops: list[str] = [
                f"ALIASES[{key!r}]",
                f"-> {alias_target!r}",
                f"resolved: {resolved_fqn}",
            ]

            path_info = PathInfo(
                source_call=source_call,
                source_symbol=source_symbol,
                alias_key=key,
                alias_dict=var_name,
                alias_target=alias_target,
                resolved_fqn=resolved_fqn,
                path_type=PathType.ALIAS_LOOKUP,
                hops=tuple(hops),
            )

            self._paths.append(path_info)
            self._fqn_to_paths.setdefault(resolved_fqn, []).append(path_info)
            self._symbol_to_paths.setdefault(source_symbol, []).append(path_info)

    def _resolve_alias_lookup(self, node: ast.AST, name: str) -> tuple[str | None, str | None]:
        """
        解析 alias 查找模式: BACKEND_ALIASES['redis'] 或 BACKEND_ALIASES.get('redis')
        返回 (alias_dict_name, alias_key)
        """
        # pattern: aliases[key] where aliases is a variable
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name):
                var_name = node.value.id
                if _looks_like_alias_lookup(var_name):
                    key = self._extract_string_literal(node.slice)
                    if key:
                        return (var_name, key)
        elif isinstance(node, ast.Call):  # .get() call
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    var_name = node.func.value.id
                    if _looks_like_alias_lookup(var_name):
                        key = self._extract_string_literal(node.args[0]) if node.args else None
                        if key:
                            return (var_name, key)
        return (None, None)

    def _lookup_alias(self, alias_dict_name: str, key: str) -> str | None:
        """在已加载的 alias 字典中查找 key"""
        # Search across all loaded alias dicts
        for dict_name, mapping in self._alias_map.items():
            if key in mapping:
                return mapping[key]
        # Also try to match by dict name suffix
        for dict_name, mapping in self._alias_map.items():
            if alias_dict_name in dict_name or dict_name in alias_dict_name:
                if key in mapping:
                    return mapping[key]
        return None

    def _resolve_symbol_name(self, name: str) -> str:
        """
        将 'celery.backends.redis:RedisBackend' 或 'celery.backends.redis.RedisBackend'
        解析为规范 FQN: 'celery.backends.redis.RedisBackend'
        """
        name = name.strip()
        if ':' in name:
            # 'module:class' notation
            module, _, cls = name.partition(':')
            return f"{module}.{cls}"
        return name

    def _extract_string_literal(self, node: ast.AST) -> str | None:
        """从 AST 节点提取字符串字面量"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Str):  # Python < 3.8
            return node.s
        return None

    def _module_name_from_path(self, pyfile: Path) -> str:
        """将文件路径转换为模块名"""
        parts = list(pyfile.parts)
        # Remove repo_root prefix
        for i, part in enumerate(parts):
            if part == "celery" or part == "kombu":
                parts = parts[i:]
                break
        if not parts:
            return pyfile.stem
        # Remove __init__ suffix
        if parts[-1] == "__init__":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(".py", "")
        return ".".join(p for p in parts if p)

    # ── Retrieval ───────────────────────────────────────────────────────────

    def search_paths(
        self,
        question: str,
        entry_symbol: str = "",
        entry_file: str = "",
        top_k: int = 5,
    ) -> list[PathInfo]:
        """
        搜索与问题相关的符号解析路径。

        Args:
            question: 用户问题
            entry_symbol: 可选的入口符号
            entry_file: 可选的入口文件
            top_k: 返回的最大路径数

        Returns:
            按相关性降序排列的 PathInfo 列表
        """
        candidates: list[tuple[float, PathInfo]] = []

        # Extract string literals from question (e.g. 'redis', 'default')
        question_literals = self._extract_string_literals_from_text(question)
        question_lower = question.lower()

        # Extract symbol names from question
        question_symbols = self._extract_symbol_names_from_text(question)

        # Entry symbol parts
        entry_parts = entry_symbol.rsplit(".", 1) if entry_symbol else []

        # Normalize entry file
        entry_file_clean = entry_file.replace("\\", "/") if entry_file else ""

        for path in self._paths:
            score = 0.0
            explained = False  # Track if we can explain WHY this path is relevant

            # ── Strategy 1: Alias key exact match (MOST IMPORTANT for Type E) ──
            # If question mentions 'redis' and path has alias_key='redis', it's a direct hit
            if path.alias_key:
                key_lower = path.alias_key.lower()
                # Exact literal match in question
                if key_lower in question_lower:
                    score += 10.0
                    explained = True
                # Check if any question literal matches
                for lit in question_literals:
                    if lit.lower() == key_lower:
                        score += 10.0
                        explained = True
                        break

            # ── Strategy 2: Resolved FQN component match ──
            # Check if resolved FQN components appear in question
            resolved_lower = path.resolved_fqn.lower()
            resolved_parts = [p.lower() for p in path.resolved_fqn.split(".")]
            for q_sym in question_symbols:
                q_lower = q_sym.lower()
                if q_lower in resolved_lower:
                    score += 4.0
                # Match last component (class/function name)
                if resolved_parts and q_lower == resolved_parts[-1]:
                    score += 5.0
                    explained = True
                # Match any part
                for part in resolved_parts:
                    if q_lower == part and len(part) > 3:
                        score += 2.0

            # ── Strategy 3: Alias target string match ──
            if path.alias_target:
                alias_target_lower = path.alias_target.lower()
                for q_lit in question_literals:
                    if q_lit.lower() in alias_target_lower:
                        score += 3.0

            # ── Strategy 4: Entry symbol context ──
            if entry_symbol:
                if path.source_symbol.endswith(entry_symbol) or entry_symbol in path.source_symbol:
                    score += 3.0
                    explained = True
                if entry_parts and path.source_symbol.endswith(entry_parts[-1]):
                    score += 2.0

            # ── Strategy 5: Entry file context ──
            if entry_file_clean:
                path_file = path.source_call.rsplit(":", 1)[0].replace("\\", "/")
                if entry_file_clean in path_file or path_file.endswith(entry_file_clean):
                    score += 1.5

            # ── Strategy 6: ALIAS_LOOKUP type bonus (Type E specific) ──
            if path.path_type == PathType.ALIAS_LOOKUP and explained:
                score += 2.0

            if score > 0:
                candidates.append((score, path))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [path for _, path in candidates[:top_k]]

    def search_by_fqn(self, fqn: str) -> list[PathInfo]:
        """根据 resolved FQN 查找路径（精确匹配）"""
        fqn_lower = fqn.lower()
        return [
            p for p in self._paths
            if p.resolved_fqn.lower() == fqn_lower
            or fqn_lower in p.resolved_fqn.lower()
        ]

    def search_by_alias_key(self, key: str) -> list[PathInfo]:
        """根据 alias key 查找路径（如 'redis', 'default'）"""
        key_lower = key.lower()
        return [p for p in self._paths if p.alias_key and p.alias_key.lower() == key_lower]

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def n_paths(self) -> int:
        return len(self._paths)

    @property
    def n_aliases(self) -> int:
        return sum(len(d) for d in self._alias_map.values())

    def stats(self) -> dict[str, int | list[str]]:
        """返回索引统计信息"""
        path_types: dict[str, int] = {}
        for p in self._paths:
            pt = p.path_type.value
            path_types[pt] = path_types.get(pt, 0) + 1
        return {
            "total_paths": len(self._paths),
            "unique_fqns": len(self._fqn_to_paths),
            "unique_sources": len(set(p.source_symbol for p in self._paths)),
            "total_aliases": self.n_aliases,
            "alias_dicts_loaded": len(self._alias_map),
            "by_path_type": path_types,
        }

    def __len__(self) -> int:
        return len(self._paths)

    def __iter__(self) -> Iterator[PathInfo]:
        return iter(self._paths)

    # ── Path summary for RAG context ─────────────────────────────────────

    def format_paths_for_context(self, paths: list[PathInfo]) -> str:
        """将路径列表格式化为 RAG 上下文文本"""
        if not paths:
            return "No dependency paths found."
        lines = ["## Symbol Resolution Paths\n"]
        for i, path in enumerate(paths, 1):
            lines.append(f"### Path {i} ({path.path_type.value})")
            lines.append(f"- **Source**: `{path.source_call}`")
            if path.alias_key:
                lines.append(f"- **Alias**: `{path.alias_dict}[{path.alias_key!r}]` -> `{path.alias_target}`")
            lines.append(f"- **Resolved FQN**: `{path.resolved_fqn}`")
            for hop in path.hops:
                lines.append(f"  1. {hop}")
            lines.append("")
        return "\n".join(lines)

    # ─── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_string_literals_from_text(text: str) -> list[str]:
        """从文本中提取带引号的字符串字面量"""
        return re.findall(r"['\"]([^'\"]{2,})['\"]", text)

    @staticmethod
    def _extract_symbol_names_from_text(text: str) -> list[str]:
        """从文本中提取类似 FQN 的符号名"""
        # Match patterns like celery.backends.redis.RedisBackend
        return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+", text)
