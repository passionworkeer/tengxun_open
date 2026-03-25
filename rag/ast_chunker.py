from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class CodeChunk:
    symbol: str
    kind: str
    start_line: int
    end_line: int
    content: str


def chunk_python_source(module_name: str, source: str) -> list[CodeChunk]:
    tree = ast.parse(source)
    lines = source.splitlines()
    chunks: list[CodeChunk] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start_line = getattr(node, "lineno", 1)
            end_line = getattr(node, "end_lineno", start_line)
            content = "\n".join(lines[start_line - 1 : end_line])
            chunks.append(
                CodeChunk(
                    symbol=f"{module_name}.{node.name}",
                    kind=type(node).__name__,
                    start_line=start_line,
                    end_line=end_line,
                    content=content,
                )
            )

    return chunks

