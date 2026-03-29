from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImplicitLevelPrediction:
    predicted_level: int
    should_use_rag: bool
    score: int
    reasons: tuple[str, ...]


_HIGH_SIGNAL_KEYWORDS = (
    "symbol_by_name",
    "by_name",
    "loader",
    "backend",
    "strategy",
    "task_cls",
    "django",
    "alias",
)

_SIDE_EFFECT_KEYWORDS = (
    "finalize",
    "decorator",
    "register",
    "registration",
    "shared-task",
    "shared task",
    "autodiscover",
    "proxy",
    "lazy",
)

_LOW_SIGNAL_KEYWORDS = (
    "top-level",
    "top level",
    "real class",
    "real function",
    "delegate",
    "helper function",
    "re-export",
    "re export",
)


def predict_implicit_level(
    *,
    question: str,
    entry_symbol: str = "",
    entry_file: str = "",
) -> ImplicitLevelPrediction:
    text = " ".join(part for part in (question, entry_symbol, entry_file) if part).lower()
    score = 1
    reasons: list[str] = []

    if any(quote in question for quote in ("'", '"', "`")):
        score += 1
        reasons.append("contains_literal_or_symbol_quote")

    if any(keyword in text for keyword in _HIGH_SIGNAL_KEYWORDS):
        score += 2
        reasons.append("dynamic_resolution_keyword")

    if any(keyword in text for keyword in _SIDE_EFFECT_KEYWORDS):
        score += 2
        reasons.append("side_effect_or_registration_keyword")

    if "resolve to" in text or "最终" in question:
        score += 1
        reasons.append("explicit_resolution_request")

    if entry_symbol.count(".") >= 3:
        score += 1
        reasons.append("deep_entry_symbol")

    if any(keyword in text for keyword in _LOW_SIGNAL_KEYWORDS):
        score -= 1
        reasons.append("simple_export_or_delegate_pattern")

    predicted_level = max(1, min(5, score))
    return ImplicitLevelPrediction(
        predicted_level=predicted_level,
        should_use_rag=predicted_level >= 3,
        score=score,
        reasons=tuple(reasons),
    )


def choose_case_score(
    *,
    case_result: dict[str, Any],
    should_use_rag: bool,
) -> float:
    if should_use_rag:
        return float(case_result["with_rag"]["f1"])
    return float(case_result["no_rag"]["f1"])
