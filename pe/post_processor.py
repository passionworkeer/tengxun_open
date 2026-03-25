from __future__ import annotations

import json
import re
from typing import Iterable


FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")


def normalize_fqn(value: str) -> str:
    return value.strip().strip('"').strip("'")


def is_valid_fqn(value: str) -> bool:
    return bool(FQN_PATTERN.fullmatch(normalize_fqn(value)))


def parse_model_output(raw_output: str) -> list[str]:
    raw_output = raw_output.strip()
    if not raw_output:
        return []

    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            candidates = [str(item) for item in parsed]
        else:
            candidates = [str(parsed)]
    except json.JSONDecodeError:
        candidates = [line for line in raw_output.splitlines() if line.strip()]

    return dedupe_preserve_order(
        normalize_fqn(item) for item in candidates if is_valid_fqn(item)
    )


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered

