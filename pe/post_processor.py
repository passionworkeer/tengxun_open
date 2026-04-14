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
import logging
import re
import sys
from typing import Iterable, Sequence

# 统一规范化函数
from rag.normalize_utils import normalize_fqn as _normalize_fqn

_logger = logging.getLogger(__name__)

# 模块级计数器：追踪JSON解析失败次数
_JSON_PARSE_FAIL_COUNT = 0


# FQN格式正则：形如 celery.app.trace.build_tracer
FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
# 代码块提取正则
CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
# 符号路径提取正则
SYMBOL_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+"
)


def normalize_fqn(value: str) -> str:
    """Normalise a string to its canonical FQN form.

    Delegates to :func:`rag.normalize_utils.normalize_fqn`, which typically
    strips whitespace, lowercases the string, and replaces separator characters
    (``/``, ``:``) with dots so that ``celery.app.base:celery`` and
    ``celery.app.base.celery`` are treated as equivalent.

    Args:
        value: A raw symbol string, possibly with surrounding whitespace,
            mixed casing, or non-standard separators.

    Returns:
        The canonical FQN string with normalised casing and separators.
    """
    return _normalize_fqn(value)


def is_valid_fqn(value: str) -> bool:
    r"""Check whether a string is a syntactically valid FQN.

    The string is first normalised via :func:`normalize_fqn`, then matched
    against the regular-expression pattern
    ``^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$``.
    This accepts dotted identifiers such as ``celery.app.trace.build_tracer``
    but rejects bare words, names starting with a digit, and strings
    containing characters outside the identifier charset.

    Args:
        value: The candidate string to validate.

    Returns:
        True when the normalised string is a valid FQN; False otherwise.
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
    """Parse model output that is expected to carry three dependency layers.

    This function preserves the ``direct_deps / indirect_deps / implicit_deps``
    tiered structure when the model returns well-formed JSON.  Each layer is
    independently normalised, validated, optionally filtered against the
    ``allowed_fqns`` whitelist, and deduplicated while preserving order.

    If the output cannot be decoded as JSON or the top-level structure does not
    contain the expected keys, the function returns ``None`` and leaves it to
    the caller to fall back to the flat :func:`parse_model_output` path.

    Args:
        raw_output: The unprocessed model response string.
        allowed_fqns: Optional whitelist of permissible FQNs; any candidate not
            in this set is dropped from every layer.

    Returns:
        A dictionary mapping layer names (``direct_deps``, ``indirect_deps``,
        ``implicit_deps``) to lists of normalised FQNs, or ``None`` when the
        output is not valid JSON or lacks the required keys.
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
    """Remove duplicates from a sequence while preserving the first-seen order.

    Each item is normalised via :func:`normalize_fqn` before comparison so that
    ``Celery``, ``celery``, and ``CELERY`` are all treated as the same key.
    The first occurrence (in iteration order) is retained; subsequent duplicates
    are discarded.

    Args:
        items: Any iterable of symbol strings, possibly containing duplicates
            or inconsistently-cased entries.

    Returns:
        A new list containing only the first-seen normalised entry for each
        unique symbol, in the original iteration order.
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
    """Extract FQN candidates from raw model output text.

    The extraction strategy tries three approaches in order of preference:

    1. **JSON in code fences** — if the text contains a fenced code block
       (`` ```json … ``` ``), only the block body is examined.
    2. **Top-level JSON array** — if the text is a valid JSON array, every
       element is taken as a candidate.
    3. **Symbol regex fallback** — a broad dotted-identifier pattern
       (``SYMBOL_PATTERN``) is run over the remaining text and each match is
       checked for FQN validity.

    Candidates are returned in the order they were discovered but are
    intentionally **not** deduplicated here; callers should apply
    :func:`dedupe_preserve_order` if needed.

    Args:
        text: Raw model output that may contain JSON, fenced blocks, and/or
            free-text descriptions.

    Returns:
        A list of not-yet-deduplicated FQN strings extracted from the text.
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
    """Attempt to parse ``text`` as a JSON array of FQN strings.

    The function accepts two structural forms:

    1. A flat array of strings, e.g. ``["celery.app.base.Celery", ...]``.
    2. A nested object containing an ``answers``, ``fqns``, ``predictions``,
       ``output``, ``result``, or ``fqn`` key whose value is an array
       (recursively flattened by :func:`_flatten_json`).

    Non-string leaf values (``int``, ``float``) are accepted and coerced to
    ``str``.  Any JSON decode error or structural mismatch causes the function
    to return ``None``, incrementing the module-level failure counter and
    logging a debug message.

    Args:
        text: The candidate JSON string.

    Returns:
        A flat list of string FQN candidates on success; ``None`` on parse
        failure or unexpected structure.
    """
    global _JSON_PARSE_FAIL_COUNT
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        _JSON_PARSE_FAIL_COUNT += 1
        _logger.debug(
            f"JSON parse failed (total failures: {_JSON_PARSE_FAIL_COUNT}): "
            f"first 100 chars: {text[:100]!r}"
        )
        print(
            f"[DEBUG] JSON parse failed #{_JSON_PARSE_FAIL_COUNT}, "
            f"falling back to regex extraction",
            file=sys.stderr,
        )
        return None

    flattened = _flatten_json(parsed)
    return [str(item) for item in flattened if isinstance(item, (str, int, float))]


def _flatten_json(value: object) -> list[object]:
    """Recursively flatten a parsed JSON value into a list of leaf values.

    When ``value`` is a list, the function recurses into each element and
    concatenates the results.  When it is a dict, it first checks for any of
    the six prioritised keys (``answers``, ``fqns``, ``predictions``,
    ``output``, ``result``, ``fqn``) in that order; the first match is
    expanded recursively.  If none of those keys exist, all dictionary values
    are recursively flattened and concatenated.  Scalar values (including
    numbers and booleans) are returned as single-element lists.

    This strategy allows the function to transparently handle both flat
    response arrays and the nested response envelopes produced by various
    model providers without requiring callers to know the exact shape in advance.

    Args:
        value: Any object produced by :func:`json.loads`.

    Returns:
        A flat list of all leaf values encountered during traversal.
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
