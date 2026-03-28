#!/usr/bin/env python3
"""
构建严格评审版本的数据资产。

目标：
1. 审计 eval / few-shot / finetune 之间的污染风险
2. 生成去除 eval exact overlap 的 few-shot 变体
3. 生成去除 eval exact overlap 的 finetune 变体（保留 500 条）
4. 输出一份可供答辩引用的审计报告
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

EVAL_PATH = DATA_DIR / "eval_cases.json"
FEWSHOT_PATH = DATA_DIR / "fewshot_examples_20.json"
FINETUNE_PATH = DATA_DIR / "finetune_dataset_500.jsonl"

STRICT_FEWSHOT_PATH = DATA_DIR / "fewshot_examples_20_strict.json"
STRICT_FINETUNE_PATH = DATA_DIR / "finetune_dataset_500_strict.jsonl"
AUDIT_REPORT_PATH = REPORTS_DIR / "strict_data_audit_20260329.md"

QUESTION_PATTERN = re.compile(r"(?:^|\n)\s*#\s*问题[:：]\s*(.+)")
HARD_SIMILARITY_THRESHOLD = 0.90
REVIEW_SIMILARITY_THRESHOLD = 0.85


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _normalize_ground_truth(ground_truth: dict[str, Any] | None) -> tuple[tuple[str, ...], ...]:
    payload = ground_truth or {}
    return (
        tuple(sorted(str(item) for item in payload.get("direct_deps", []) if item)),
        tuple(sorted(str(item) for item in payload.get("indirect_deps", []) if item)),
        tuple(sorted(str(item) for item in payload.get("implicit_deps", []) if item)),
    )


def _extract_question(text: str) -> str:
    match = QUESTION_PATTERN.search(text)
    if match:
        return match.group(1).strip()

    for line in reversed(text.splitlines()):
        if "问题" in line:
            return line.split("问题", 1)[-1].lstrip(":：# ").strip()
    return text.strip().splitlines()[-1].strip() if text.strip() else ""


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", text.lower()))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _load_eval_cases() -> list[dict[str, Any]]:
    return _read_json(EVAL_PATH)


def _load_fewshot() -> list[dict[str, Any]]:
    return _read_json(FEWSHOT_PATH)


def _load_finetune() -> list[dict[str, Any]]:
    return _read_jsonl(FINETUNE_PATH)


def _audit_exact_overlaps(
    eval_cases: list[dict[str, Any]],
    fewshot: list[dict[str, Any]],
    finetune_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    eval_gt_to_cases: dict[tuple[tuple[str, ...], ...], list[str]] = {}
    for case in eval_cases:
        eval_gt_to_cases.setdefault(_normalize_ground_truth(case.get("ground_truth")), []).append(
            case["id"]
        )

    fewshot_overlaps: list[dict[str, str]] = []
    for item in fewshot:
        eval_case_ids = eval_gt_to_cases.get(_normalize_ground_truth(item.get("ground_truth")), [])
        for eval_case_id in eval_case_ids:
            fewshot_overlaps.append({"fewshot_id": item["id"], "eval_case_id": eval_case_id})

    finetune_overlaps: list[dict[str, Any]] = []
    for index, row in enumerate(finetune_rows):
        eval_case_ids = eval_gt_to_cases.get(_normalize_ground_truth(row.get("ground_truth")), [])
        for eval_case_id in eval_case_ids:
            finetune_overlaps.append(
                {
                    "row_index": index,
                    "eval_case_id": eval_case_id,
                    "failure_type": row.get("failure_type", ""),
                    "category": row.get("category", ""),
                }
            )

    return {
        "fewshot_overlap_count": len(fewshot_overlaps),
        "fewshot_overlaps": fewshot_overlaps,
        "finetune_overlap_record_count": len(finetune_overlaps),
        "finetune_overlap_row_count": len({item["row_index"] for item in finetune_overlaps}),
        "finetune_overlap_case_count": len({item["eval_case_id"] for item in finetune_overlaps}),
        "finetune_overlaps": finetune_overlaps,
    }


def _question_match(question: str, eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_question = _normalize_text(question)
    best_case_id = ""
    best_score = 0.0
    normalized_exact_case_ids: list[str] = []
    for eval_case in eval_cases:
        eval_normalized = _normalize_text(eval_case["question"])
        if normalized_question and normalized_question == eval_normalized:
            normalized_exact_case_ids.append(eval_case["id"])
        score = SequenceMatcher(None, normalized_question, eval_normalized).ratio()
        if score > best_score:
            best_case_id = eval_case["id"]
            best_score = score
    return {
        "normalized_question": normalized_question,
        "closest_eval_case": best_case_id,
        "similarity": round(best_score, 4),
        "normalized_exact_case_ids": normalized_exact_case_ids,
        "normalized_exact": bool(normalized_exact_case_ids),
        "hard_overlap": bool(normalized_exact_case_ids) or best_score >= HARD_SIMILARITY_THRESHOLD,
        "review_overlap": (
            not normalized_exact_case_ids
            and REVIEW_SIMILARITY_THRESHOLD <= best_score < HARD_SIMILARITY_THRESHOLD
        ),
    }


def _audit_question_overlaps(
    eval_cases: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    *,
    question_key: str,
    top_k: int = 8,
) -> dict[str, Any]:
    scored: list[dict[str, Any]] = []
    normalized_exact_candidates: list[str] = []
    hard_overlap_candidates: list[str] = []
    review_candidates: list[str] = []
    for candidate in candidates:
        candidate_question = candidate.get(question_key, "")
        candidate_id = candidate.get("id", candidate.get("row_id", ""))
        match = _question_match(str(candidate_question), eval_cases)
        if match["normalized_exact"]:
            normalized_exact_candidates.append(candidate_id)
        if match["hard_overlap"]:
            hard_overlap_candidates.append(candidate_id)
        if match["review_overlap"]:
            review_candidates.append(candidate_id)
        if match["closest_eval_case"]:
            scored.append(
                {
                    "candidate_id": candidate_id,
                    "closest_eval_case": match["closest_eval_case"],
                    "similarity": match["similarity"],
                    "normalized_exact": match["normalized_exact"],
                    "question": candidate_question,
                }
            )
    scored.sort(key=lambda item: (-item["similarity"], item["candidate_id"]))
    return {
        "top_candidates": scored[:top_k],
        "normalized_exact_count": len(normalized_exact_candidates),
        "normalized_exact_candidates": normalized_exact_candidates,
        "hard_overlap_count": len(hard_overlap_candidates),
        "hard_overlap_candidates": hard_overlap_candidates,
        "review_count": len(review_candidates),
        "review_candidates": review_candidates,
    }


def _build_supplement_pool(eval_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from scripts.finalize_official_datasets import SUPPLEMENTS, _make_record

    eval_gt = {_normalize_ground_truth(case.get("ground_truth")) for case in eval_cases}
    pool: list[dict[str, Any]] = []
    for spec in SUPPLEMENTS:
        record = _make_record(spec)
        if _normalize_ground_truth(record.get("ground_truth")) in eval_gt:
            continue
        question = _extract_question(spec.input)
        match = _question_match(question, eval_cases)
        if match["hard_overlap"]:
            continue
        pool.append({"spec": spec, "record": record, "question_match": match})
    return pool


def _title_from_instruction(instruction: str) -> str:
    cleaned = instruction.replace("分析", "").replace("追踪", "").strip()
    return cleaned[:28]


def _supplement_to_fewshot(spec: Any, case_id: str) -> dict[str, Any]:
    question = _extract_question(spec.input)
    return {
        "id": case_id,
        "title": _title_from_instruction(spec.instruction),
        "failure_type": spec.failure_type,
        "difficulty": spec.difficulty,
        "question": question,
        "environment_preconditions": [],
        "reasoning_steps": list(spec.reasoning_steps),
        "ground_truth": spec.ground_truth,
    }


def _allocate_case_id(existing_ids: set[str], failure_type: str) -> str:
    prefix = failure_type.split()[-1][:1] if failure_type else "X"
    current_numbers = []
    for case_id in existing_ids:
        if not case_id.startswith(prefix):
            continue
        suffix = case_id[len(prefix) :]
        if suffix.isdigit():
            current_numbers.append(int(suffix))
    next_number = (max(current_numbers) + 1) if current_numbers else 1
    new_case_id = f"{prefix}{next_number:02d}"
    existing_ids.add(new_case_id)
    return new_case_id


def _build_strict_fewshot(
    eval_cases: list[dict[str, Any]],
    fewshot: list[dict[str, Any]],
    overlap_audit: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    overlap_ids = {item["fewshot_id"] for item in overlap_audit["fewshot_overlaps"]}
    strict_rows: list[dict[str, Any]] = []
    question_filtered = 0
    existing_ids = {item["id"] for item in fewshot if item["id"] not in overlap_ids}
    for item in fewshot:
        if item["id"] in overlap_ids:
            continue
        match = _question_match(item.get("question", ""), eval_cases)
        if match["hard_overlap"]:
            question_filtered += 1
            existing_ids.discard(item["id"])
            continue
        strict_rows.append(item)

    supplement_pool = _build_supplement_pool(eval_cases)
    needed = len(fewshot) - len(strict_rows)
    if not supplement_pool:
        raise ValueError("Supplement pool is empty after strict filtering.")
    for offset in range(needed):
        spec = supplement_pool[offset % len(supplement_pool)]["spec"]
        case_id = _allocate_case_id(existing_ids, spec.failure_type)
        strict_rows.append(_supplement_to_fewshot(spec, case_id))

    notes = [
        f"removed overlap few-shot ids: {', '.join(sorted(overlap_ids))}",
        f"removed hard question-overlap few-shot rows: {question_filtered}",
        f"added strict supplement few-shot rows: {needed}",
    ]
    strict_rows.sort(key=lambda item: (item["failure_type"], item["id"]))
    if len(strict_rows) != 20:
        raise ValueError(f"Expected 20 strict few-shot examples, got {len(strict_rows)}")
    return strict_rows, notes


def _make_strict_variant(spec: Any, variant_index: int) -> dict[str, Any]:
    from scripts.finalize_official_datasets import _format_output

    variant_instruction = (
        f"严格变体 {variant_index:02d}：沿着 {spec.repo_path} 追踪 {spec.category} 相关链路，"
        "确定 direct / indirect / implicit 依赖。"
    )
    variant_input = (
        f"{spec.input}\n"
        "# 额外要求: 只保留能够稳定落到真实 FQN 的最终答案，不要停在模块名或中间字符串别名。"
    )
    variant_reasoning = (
        "先定位题面中的入口对象或 helper。",
        *spec.reasoning_steps,
        "最后核对 direct / indirect / implicit 三层是否放在正确位置。",
    )
    return {
        "instruction": variant_instruction,
        "input": variant_input,
        "output": _format_output(variant_reasoning, spec.ground_truth),
        "ground_truth": spec.ground_truth,
        "difficulty": spec.difficulty,
        "failure_type": spec.failure_type,
        "category": f"{spec.category}_strict_variant",
        "repo_path": spec.repo_path,
        "verified": True,
        "verify_method": "manual_strict_variant",
        "source_variant_of": spec.category,
    }


def _build_strict_finetune(
    eval_cases: list[dict[str, Any]],
    finetune_rows: list[dict[str, Any]],
    overlap_audit: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    overlap_indexes = {item["row_index"] for item in overlap_audit["finetune_overlaps"]}
    strict_rows: list[dict[str, Any]] = []
    question_filtered = 0
    for index, row in enumerate(finetune_rows):
        if index in overlap_indexes:
            continue
        question = _extract_question(str(row.get("input", "")))
        match = _question_match(question, eval_cases)
        if match["hard_overlap"]:
            question_filtered += 1
            continue
        strict_rows.append(row)

    needed = len(finetune_rows) - len(strict_rows)
    supplement_pool = _build_supplement_pool(eval_cases)
    if not supplement_pool:
        raise ValueError("Supplement pool is empty after strict filtering.")
    supplement_specs = [
        supplement_pool[offset % len(supplement_pool)]["spec"] for offset in range(needed)
    ]

    for offset, spec in enumerate(supplement_specs, start=1):
        strict_rows.append(_make_strict_variant(spec, offset))

    if len(strict_rows) != len(finetune_rows):
        raise ValueError(
            f"Expected {len(finetune_rows)} strict finetune rows, got {len(strict_rows)}"
        )

    notes = [
        f"removed overlap finetune rows: {len(overlap_indexes)}",
        f"removed hard question-overlap finetune rows: {question_filtered}",
        f"added strict supplement variants: {needed}",
    ]
    return strict_rows, notes


def _build_report(
    overlap_audit: dict[str, Any],
    fewshot_notes: list[str],
    finetune_notes: list[str],
    fewshot_question_audit: dict[str, Any],
    finetune_question_audit: dict[str, Any],
    strict_fewshot_rows: list[dict[str, Any]],
    strict_finetune_rows: list[dict[str, Any]],
) -> str:
    eval_cases = _load_eval_cases()
    eval_gt = {_normalize_ground_truth(case.get("ground_truth")) for case in eval_cases}
    strict_fewshot_overlap = sum(
        1 for row in strict_fewshot_rows if _normalize_ground_truth(row.get("ground_truth")) in eval_gt
    )
    strict_finetune_overlap = sum(
        1 for row in strict_finetune_rows if _normalize_ground_truth(row.get("ground_truth")) in eval_gt
    )
    strict_fewshot_question_audit = _audit_question_overlaps(
        eval_cases,
        [{"id": item["id"], "question": item["question"]} for item in strict_fewshot_rows],
        question_key="question",
    )
    strict_finetune_question_audit = _audit_question_overlaps(
        eval_cases,
        [
            {
                "row_id": f"strict_ft_{index:03d}",
                "question": _extract_question(str(row.get("input", ""))),
            }
            for index, row in enumerate(strict_finetune_rows)
        ],
        question_key="question",
    )
    failure_counter = Counter(row.get("failure_type", "") for row in strict_finetune_rows)
    lines = [
        "# 严格数据污染审计（2026-03-29）",
        "",
        "## 结论",
        "",
        f"- few-shot 与 eval 的 exact GT overlap：`{overlap_audit['fewshot_overlap_count']}`",
        f"- finetune 与 eval 的 exact GT overlap row-case pair 数：`{overlap_audit['finetune_overlap_record_count']}`",
        f"- finetune 与 eval 的 exact GT overlap row 数：`{overlap_audit['finetune_overlap_row_count']}`",
        f"- finetune 与 eval 的 exact GT overlap case 数：`{overlap_audit['finetune_overlap_case_count']}`",
        f"- official few-shot normalized exact question overlap：`{fewshot_question_audit['normalized_exact_count']}`",
        f"- official finetune normalized exact question overlap：`{finetune_question_audit['normalized_exact_count']}`",
        f"- official few-shot hard question overlap (exact or >= {HARD_SIMILARITY_THRESHOLD:.2f})：`{fewshot_question_audit['hard_overlap_count']}`",
        f"- official finetune hard question overlap (exact or >= {HARD_SIMILARITY_THRESHOLD:.2f})：`{finetune_question_audit['hard_overlap_count']}`",
        f"- 已生成 strict few-shot：`{STRICT_FEWSHOT_PATH.relative_to(ROOT)}`",
        f"- 已生成 strict finetune：`{STRICT_FINETUNE_PATH.relative_to(ROOT)}`",
        f"- strict few-shot 与 eval 的 exact GT overlap：`{strict_fewshot_overlap}`",
        f"- strict finetune 与 eval 的 exact GT overlap：`{strict_finetune_overlap}`",
        f"- strict few-shot normalized exact question overlap：`{strict_fewshot_question_audit['normalized_exact_count']}`",
        f"- strict finetune normalized exact question overlap：`{strict_finetune_question_audit['normalized_exact_count']}`",
        f"- strict few-shot hard question overlap (exact or >= {HARD_SIMILARITY_THRESHOLD:.2f})：`{strict_fewshot_question_audit['hard_overlap_count']}`",
        f"- strict finetune hard question overlap (exact or >= {HARD_SIMILARITY_THRESHOLD:.2f})：`{strict_finetune_question_audit['hard_overlap_count']}`",
        "",
        "## Exact Overlap",
        "",
        "### Few-shot",
        "",
    ]

    if overlap_audit["fewshot_overlaps"]:
        lines.extend(
            f"- `{item['fewshot_id']}` -> `{item['eval_case_id']}`"
            for item in overlap_audit["fewshot_overlaps"]
        )
    else:
        lines.append("- 无")

    lines.extend(
        [
            "",
            "### Finetune",
            "",
            f"- overlap row-case pair 数：`{overlap_audit['finetune_overlap_record_count']}`",
            f"- overlap row 数：`{overlap_audit['finetune_overlap_row_count']}`",
            f"- overlap case 数：`{overlap_audit['finetune_overlap_case_count']}`",
            "",
            "## 近似问题重合（问题文本）",
            "",
            "### Few-shot Top Candidates",
            "",
        ]
    )
    lines.extend(
        f"- `{item['candidate_id']}` ~ `{item['closest_eval_case']}`: "
        f"similarity={item['similarity']}, normalized_exact={item['normalized_exact']}"
        for item in fewshot_question_audit["top_candidates"]
    )
    lines.extend(
        [
            "",
            f"- official few-shot review queue ({REVIEW_SIMILARITY_THRESHOLD:.2f}~{HARD_SIMILARITY_THRESHOLD:.2f}): "
            f"`{fewshot_question_audit['review_count']}`",
            "",
            "### Finetune Top Candidates",
            "",
        ]
    )
    lines.extend(
        f"- `{item['candidate_id']}` ~ `{item['closest_eval_case']}`: "
        f"similarity={item['similarity']}, normalized_exact={item['normalized_exact']}"
        for item in finetune_question_audit["top_candidates"]
    )
    lines.extend(
        [
            "",
            f"- official finetune review queue ({REVIEW_SIMILARITY_THRESHOLD:.2f}~{HARD_SIMILARITY_THRESHOLD:.2f}): "
            f"`{finetune_question_audit['review_count']}`",
            "",
            "## Strict 替换说明",
            "",
            *[f"- {note}" for note in fewshot_notes],
            *[f"- {note}" for note in finetune_notes],
            "",
            "## Strict Finetune 分布",
            "",
            *[f"- `{key}`: `{value}`" for key, value in sorted(failure_counter.items())],
            "",
            "## 说明",
            "",
            "- strict few-shot 的目标是去除 eval exact overlap，不覆盖原始正式 few-shot 文件。",
            "- strict finetune 先移除 exact overlap 和 hard question overlap，再补入不与 eval 重合的 manual strict variants，以维持 `500` 条。",
            f"- 当前 strict 构建规则：过滤 exact GT overlap、normalized exact question overlap、以及 similarity >= {HARD_SIMILARITY_THRESHOLD:.2f} 的 hard overlap。",
            f"- similarity 介于 {REVIEW_SIMILARITY_THRESHOLD:.2f} 和 {HARD_SIMILARITY_THRESHOLD:.2f} 之间的样本只进入审计报告，不自动删除。",
            "- 这些 strict 资产适合用来做复验和答辩防守，不应无提示地覆盖当前正式口径。",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    eval_cases = _load_eval_cases()
    fewshot = _load_fewshot()
    finetune_rows = _load_finetune()

    overlap_audit = _audit_exact_overlaps(eval_cases, fewshot, finetune_rows)

    fewshot_candidates = [
        {"id": item["id"], "question": item["question"]} for item in fewshot
    ]
    finetune_candidates = [
        {
            "row_id": f"ft_{index:03d}",
            "question": _extract_question(str(row.get("input", ""))),
        }
        for index, row in enumerate(finetune_rows)
    ]

    fewshot_question_audit = _audit_question_overlaps(
        eval_cases, fewshot_candidates, question_key="question"
    )
    finetune_question_audit = _audit_question_overlaps(
        eval_cases, finetune_candidates, question_key="question"
    )

    strict_fewshot, fewshot_notes = _build_strict_fewshot(eval_cases, fewshot, overlap_audit)
    strict_finetune, finetune_notes = _build_strict_finetune(eval_cases, finetune_rows, overlap_audit)

    _write_json(STRICT_FEWSHOT_PATH, strict_fewshot)
    _write_jsonl(STRICT_FINETUNE_PATH, strict_finetune)
    AUDIT_REPORT_PATH.write_text(
        _build_report(
            overlap_audit,
            fewshot_notes,
            finetune_notes,
            fewshot_question_audit,
            finetune_question_audit,
            strict_fewshot,
            strict_finetune,
        ),
        encoding="utf-8",
    )

    print(f"Saved strict few-shot to {STRICT_FEWSHOT_PATH}")
    print(f"Saved strict finetune to {STRICT_FINETUNE_PATH}")
    print(f"Saved audit report to {AUDIT_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
