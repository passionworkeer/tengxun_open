from __future__ import annotations

from dataclasses import dataclass


SYSTEM_PROMPT = """\
You are a senior Python static analysis expert.
Your task is to resolve cross-file dependency targets precisely.
Only output a JSON array of fully qualified names (FQNs).
Do not include explanations, markdown, or extra prose.
"""


COT_TEMPLATE = """\
Follow this reasoning procedure internally before answering:
1. Identify the entry symbol and its module.
2. Resolve explicit imports and re-exports in the current file.
3. Trace decorators, inheritance, or dynamic registration when relevant.
4. Return the final dependency targets as FQNs.
"""


@dataclass(frozen=True)
class FewShotExample:
    question: str
    context: str
    answer: list[str]


REQUIRED_FEW_SHOT_TARGET = 20


# TODO: replace placeholders with manually curated high-quality examples.
FEW_SHOT_LIBRARY: list[FewShotExample] = []


def build_user_prompt(question: str, context: str) -> str:
    return (
        "Question:\n"
        f"{question.strip()}\n\n"
        "Context:\n"
        f"{context.strip()}\n\n"
        "Return only a JSON array of FQNs."
    )


def few_shot_gap() -> int:
    return max(REQUIRED_FEW_SHOT_TARGET - len(FEW_SHOT_LIBRARY), 0)

