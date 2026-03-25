from __future__ import annotations

import json
import re
from typing import Iterable, Sequence


FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
SYMBOL_PATTERN = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+")


def normalize_fqn(value: str) -> str:
    return value.strip().strip('"').strip("'").replace(":", ".")


def is_valid_fqn(value: str) -> bool:
    return bool(FQN_PATTERN.fullmatch(normalize_fqn(value)))


def parse_model_output(
    raw_output: str,
    allowed_fqns: Sequence[str] | None = None,
) -> list[str]:
    text = raw_output.strip()
    if not text:
        return []

    candidates = _extract_candidates(text)
    if allowed_fqns is not None:
        allow_set = {normalize_fqn(item) for item in allowed_fqns}
        candidates = [candidate for candidate in candidates if candidate in allow_set]
    return dedupe_preserve_order(candidate for candidate in candidates if is_valid_fqn(candidate))


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
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
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None

    flattened = _flatten_json(parsed)
    return [str(item) for item in flattened if isinstance(item, (str, int, float))]


def _flatten_json(value: object) -> list[object]:
    if isinstance(value, list):
        flattened: list[object] = []
        for item in value:
            flattened.extend(_flatten_json(item))
        return flattened
    if isinstance(value, dict):
        prioritized_keys = ("answers", "fqns", "predictions", "output", "result", "fqn")
        for key in prioritized_keys:
            if key in value:
                return _flatten_json(value[key])
        flattened = []
        for item in value.values():
            flattened.extend(_flatten_json(item))
        return flattened
    return [value]
