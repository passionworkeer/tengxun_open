from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence


SYSTEM_PROMPT = """\
You are a senior Python static analysis expert working on cross-file dependency resolution.
Resolve the final dependency structure precisely against the provided Celery source context.
Output only a JSON object in this shape:
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
Do not include explanations, markdown, XML tags, or any extra prose.
"""


COT_TEMPLATE = """\
Reason internally using this checklist before answering:
1. Identify whether the entry is a re-export, alias, decorator flow, dynamic string target, or long multi-hop chain.
2. Separate stable public entry points from conditional internal substeps.
3. Follow the chain until the final real symbol or stable trigger point is reached.
4. Distinguish direct, indirect, and implicit dependencies instead of flattening everything into one list.
5. Return only the required JSON object.
"""


OUTPUT_INSTRUCTIONS = """Return only a JSON object with:
{
  "ground_truth": {
    "direct_deps": ["..."],
    "indirect_deps": ["..."],
    "implicit_deps": ["..."]
  }
}"""


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "fewshot_examples_20.json"
REQUIRED_FEW_SHOT_TARGET = 20
_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class GroundTruth:
    direct_deps: tuple[str, ...]
    indirect_deps: tuple[str, ...]
    implicit_deps: tuple[str, ...]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "direct_deps": list(self.direct_deps),
            "indirect_deps": list(self.indirect_deps),
            "implicit_deps": list(self.implicit_deps),
        }


@dataclass(frozen=True)
class FewShotExample:
    case_id: str
    failure_type: str
    title: str
    question: str
    environment_preconditions: tuple[str, ...]
    reasoning_steps: tuple[str, ...]
    ground_truth: GroundTruth


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    cot_template: str
    few_shot_examples: tuple[FewShotExample, ...]
    user_prompt: str

    def as_text(self) -> str:
        blocks = [self.system_prompt.strip(), self.cot_template.strip()]
        if self.few_shot_examples:
            blocks.append(
                "\n\n".join(format_few_shot_example(example) for example in self.few_shot_examples)
            )
        blocks.append(self.user_prompt.strip())
        return "\n\n".join(block for block in blocks if block)


def _tokenize(text: str) -> set[str]:
    normalized = (
        text.replace(":", ".")
        .replace("/", ".")
        .replace("`", " ")
        .replace("-", " ")
    )
    tokens: set[str] = set()
    for raw_token in _TOKEN_PATTERN.findall(normalized):
        token = raw_token.lower()
        tokens.add(token)
        split_token = re.sub(r"(?<!^)(?=[A-Z])", " ", raw_token).lower()
        tokens.update(piece for piece in split_token.split() if piece)
    return tokens


def _coerce_string_list(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _load_example(item: dict[str, object]) -> FewShotExample:
    ground_truth = item.get("ground_truth", {})
    if not isinstance(ground_truth, dict):
        raise ValueError(f"Invalid ground_truth payload for {item.get('id', '<unknown>')}")

    return FewShotExample(
        case_id=str(item.get("id", "")).strip(),
        failure_type=str(item.get("failure_type", "")).strip(),
        title=str(item.get("title", "")).strip(),
        question=str(item.get("question", "")).strip(),
        environment_preconditions=_coerce_string_list(
            item.get("environment_preconditions") if isinstance(item, dict) else None
        ),
        reasoning_steps=_coerce_string_list(
            item.get("reasoning_steps") if isinstance(item, dict) else None
        ),
        ground_truth=GroundTruth(
            direct_deps=_coerce_string_list(ground_truth.get("direct_deps")),
            indirect_deps=_coerce_string_list(ground_truth.get("indirect_deps")),
            implicit_deps=_coerce_string_list(ground_truth.get("implicit_deps")),
        ),
    )


@lru_cache(maxsize=1)
def load_few_shot_examples(path: str | Path = DATA_PATH) -> tuple[FewShotExample, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return tuple(_load_example(item) for item in raw)


FEW_SHOT_LIBRARY: tuple[FewShotExample, ...] = load_few_shot_examples()


def format_few_shot_example(example: FewShotExample) -> str:
    preconditions = (
        "\n".join(f"{idx}. {item}" for idx, item in enumerate(example.environment_preconditions, start=1))
        if example.environment_preconditions
        else "None"
    )
    reasoning = "\n".join(
        f"{idx}. {item}" for idx, item in enumerate(example.reasoning_steps, start=1)
    )
    answer = json.dumps(
        {"ground_truth": example.ground_truth.as_dict()},
        ensure_ascii=False,
        indent=2,
    )
    return (
        f"[Few-shot {example.case_id} | {example.failure_type} | {example.title}]\n"
        f"Question:\n{example.question}\n\n"
        f"Environment Preconditions:\n{preconditions}\n\n"
        f"Reasoning:\n{reasoning}\n\n"
        f"Answer:\n{answer}"
    )


def select_few_shot_examples(
    question: str,
    context: str = "",
    entry_symbol: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
) -> list[FewShotExample]:
    examples = list(library or FEW_SHOT_LIBRARY)
    if max_examples <= 0 or not examples:
        return []

    query_text = " ".join(part for part in (question, context, entry_symbol) if part)
    query_tokens = _tokenize(query_text)
    entry_tail = entry_symbol.rsplit(".", 1)[-1].lower() if entry_symbol else ""

    scored: list[tuple[float, FewShotExample]] = []
    for example in examples:
        example_text = " ".join(
            [
                example.case_id,
                example.failure_type,
                example.title,
                example.question,
                " ".join(example.environment_preconditions),
                " ".join(example.reasoning_steps),
                " ".join(example.ground_truth.direct_deps),
                " ".join(example.ground_truth.indirect_deps),
                " ".join(example.ground_truth.implicit_deps),
            ]
        )
        example_tokens = _tokenize(example_text)
        overlap = len(query_tokens & example_tokens)
        failure_hit = 1 if any(token in example.failure_type.lower() for token in query_tokens) else 0
        entry_hit = 1 if entry_tail and entry_tail in example_text.lower() else 0
        long_chain_bonus = 0.5 if example.case_id.startswith("A") else 0.0
        score = overlap * 3.0 + failure_hit * 2.0 + entry_hit * 2.5 + long_chain_bonus
        scored.append((score, example))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].case_id.startswith("A"),
            item[1].case_id.startswith("B"),
            item[1].case_id,
        ),
        reverse=True,
    )

    selected: list[FewShotExample] = []
    seen_ids: set[str] = set()
    for _, example in scored:
        if example.case_id in seen_ids:
            continue
        selected.append(example)
        seen_ids.add(example.case_id)
        if len(selected) >= max_examples:
            break
    return selected


def build_user_prompt(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
) -> str:
    lines = ["Question:", question.strip()]
    if entry_symbol.strip():
        lines.extend(["", "Entry Symbol:", entry_symbol.strip()])
    if entry_file.strip():
        lines.extend(["", "Entry File:", entry_file.strip()])
    lines.extend(
        [
            "",
            "Context:",
            context.strip(),
            "",
            OUTPUT_INSTRUCTIONS,
        ]
    )
    return "\n".join(lines)


def build_prompt_bundle(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
) -> PromptBundle:
    selected = select_few_shot_examples(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        max_examples=max_examples,
        library=library,
    )
    return PromptBundle(
        system_prompt=SYSTEM_PROMPT,
        cot_template=COT_TEMPLATE,
        few_shot_examples=tuple(selected),
        user_prompt=build_user_prompt(
            question=question,
            context=context,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        ),
    )


def build_messages(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
) -> list[dict[str, str]]:
    bundle = build_prompt_bundle(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        entry_file=entry_file,
        max_examples=max_examples,
    )
    messages = [{"role": "system", "content": bundle.system_prompt.strip()}]
    if bundle.cot_template.strip():
        messages.append({"role": "system", "content": bundle.cot_template.strip()})
    for example in bundle.few_shot_examples:
        messages.append({"role": "user", "content": format_few_shot_example(example)})
    messages.append({"role": "user", "content": bundle.user_prompt.strip()})
    return messages


def few_shot_gap(library: Iterable[FewShotExample] | None = None) -> int:
    size = len(list(library)) if library is not None else len(FEW_SHOT_LIBRARY)
    return max(REQUIRED_FEW_SHOT_TARGET - size, 0)
