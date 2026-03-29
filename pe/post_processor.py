"""
输出后处理模块

功能：
1. 解析模型输出的JSON/文本
2. FQN格式校验
3. 去重（保持原始顺序）
4. 过滤非法路径

这是PE（提示词工程）的最后一道防线，
确保模型输出符合预期的格式规范。
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Sequence


# FQN格式正则：形如 celery.app.trace.build_tracer
FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
# 代码块提取正则
CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
# 符号路径提取正则
SYMBOL_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+"
)


def normalize_fqn(value: str) -> str:
    """
    规范化FQN字符串

    处理引号、转义符，统一格式。
    """
    text = value.strip().strip('"').strip("'")
    text = text.replace("::", ".")
    text = text.replace(":", ".")
    text = text.replace("/", ".")
    text = text.replace(".py.", ".")
    if text.endswith(".py"):
        text = text[:-3]
    text = re.sub(r"\.+", ".", text).strip(".")
    return text


def is_valid_fqn(value: str) -> bool:
    r"""
    检查字符串是否为有效的FQN格式

    FQN必须符合：^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$
    """
    return bool(FQN_PATTERN.fullmatch(normalize_fqn(value)))


def parse_model_output(
    raw_output: str,
    allowed_fqns: Sequence[str] | None = None,
) -> list[str]:
    """
    解析模型输出

    处理流程：
    1. 提取代码块内容（如果有）
    2. 尝试解析JSON
    3. 如果JSON解析失败，使用正则提取符号路径
    4. 可选：过滤到allowed_fqns白名单

    Args:
        raw_output: 模型原始输出
        allowed_fqns: 可选的FQN白名单

    Returns:
        解析出的FQN列表
    """
    text = raw_output.strip()
    if not text:
        return []

    candidates = _extract_candidates(text)
    if allowed_fqns is not None:
        allow_set = {normalize_fqn(item) for item in allowed_fqns}
        candidates = [candidate for candidate in candidates if candidate in allow_set]
    return dedupe_preserve_order(
        candidate for candidate in candidates if is_valid_fqn(candidate)
    )


def parse_model_output_layers(
    raw_output: str,
    allowed_fqns: Sequence[str] | None = None,
) -> dict[str, list[str]] | None:
    """
    优先保留 direct / indirect / implicit 三层结构。

    若输出可解析成 JSON，则逐层清洗；
    若无法解析，返回 None，由上层决定是否退回扁平模式。
    """

    text = raw_output.strip()
    if not text:
        return None

    fenced = CODE_FENCE_PATTERN.search(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    ground_truth = parsed.get("ground_truth", parsed)
    if not isinstance(ground_truth, dict):
        return None

    allow_set = None
    if allowed_fqns is not None:
        allow_set = {normalize_fqn(item) for item in allowed_fqns}

    layers: dict[str, list[str]] = {}
    for key in ("direct_deps", "indirect_deps", "implicit_deps"):
        values = ground_truth.get(key, [])
        if not isinstance(values, list):
            layers[key] = []
            continue
        cleaned = []
        for value in values:
            if not isinstance(value, str):
                continue
            normalized = normalize_fqn(value)
            if not is_valid_fqn(normalized):
                continue
            if allow_set is not None and normalized not in allow_set:
                continue
            cleaned.append(normalized)
        layers[key] = dedupe_preserve_order(cleaned)
    return layers


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    """
    去重并保持原始顺序

    用于确保输出的FQN列表顺序有意义。
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = normalize_fqn(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _extract_candidates(text: str) -> list[str]:
    """
    从文本中提取FQN候选

    优先从代码块解析，否则用正则匹配。
    """
    fenced = CODE_FENCE_PATTERN.search(text)
    if fenced:
        text = fenced.group(1).strip()

    parsed_json = _try_parse_json(text)
    if parsed_json is not None:
        return [normalize_fqn(item) for item in parsed_json]

    return [
        normalize_fqn(match.group(0))
        for match in SYMBOL_PATTERN.finditer(text)
        if is_valid_fqn(match.group(0))
    ]


def _try_parse_json(text: str) -> list[str] | None:
    """
    尝试解析JSON

    支持两种格式：
    1. 直接是字符串数组
    2. 包含 ground_truth 等键的嵌套对象
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    flattened = _flatten_json(parsed)
    return [str(item) for item in flattened if isinstance(item, (str, int, float))]


def _flatten_json(value: object) -> list[object]:
    """
    扁平化JSON对象

    优先提取特定键（answers/fqns/predictions/output/result/fqn），
    否则递归展开所有值。
    """
    if isinstance(value, list):
        flattened: list[object] = []
        for item in value:
            flattened.extend(_flatten_json(item))
        return flattened
    if isinstance(value, dict):
        # 优先键：按优先级尝试
        prioritized_keys = ("answers", "fqns", "predictions", "output", "result", "fqn")
        for key in prioritized_keys:
            if key in value:
                return _flatten_json(value[key])
        # 递归展开
        flattened = []
        for item in value.values():
            flattened.extend(_flatten_json(item))
        return flattened
    return [value]
