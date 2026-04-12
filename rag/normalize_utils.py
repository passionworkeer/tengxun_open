"""
符号规范化工具模块

提供统一的 FQN（完全限定名）规范化逻辑，整合多个模块中重复的规范化实现：
- evaluation/metrics.py: canonicalize_dependency_symbol()
- pe/post_processor.py: normalize_fqn()
- rag/ast_chunker.py: normalize_symbol_target()

规范化处理：
1. 去除首尾空白、引号
2. 统一路径分隔符（::/: -> .）
3. 统一斜杠（/ -> .）
4. 去除 .py 后缀
5. 合并多个点（.+ -> .）
"""

from __future__ import annotations

import re

# 多个点合并正则
_SEPARATOR_RE = re.compile(r"\.+")


def normalize_fqn(value: str) -> str:
    """
    规范化 FQN 字符串为标准格式

    处理引号、转义符，统一路径格式。

    处理流程：
    1. strip 空白和引号
    2. :: -> .（C++作用域 -> Python点号）
    3. : -> .（常见路径分隔）
    4. / -> .（Unix风格路径）
    5. .py. -> .（去除中间.py）
    6. 去除尾部 .py
    7. 合并多个点
    8. 去除首尾点

    Examples:
        "'celery.app.trace'" -> "celery.app.trace"
        '"celery:app:trace"' -> "celery.app.trace"
        "celery::app::trace" -> "celery.app.trace"
        "celery/app/trace" -> "celery.app.trace"
        "celery.app.trace.py" -> "celery.app.trace"

    Args:
        value: 待规范化的字符串

    Returns:
        规范化后的 FQN 字符串
    """
    text = value.strip().strip('"').strip("'")
    text = text.replace("::", ".")
    text = text.replace(":", ".")
    text = text.replace("/", ".")
    text = text.replace(".py.", ".")
    if text.endswith(".py"):
        text = text[:-3]
    text = _SEPARATOR_RE.sub(".", text).strip(".")
    return text


# 向后兼容别名
normalize_symbol_target = normalize_fqn
canonicalize_dependency_symbol = normalize_fqn
