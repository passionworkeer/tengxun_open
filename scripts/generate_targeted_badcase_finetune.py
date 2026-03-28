#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

from evaluation.baseline import EvalCase, load_eval_cases
from rag.rrf_retriever import build_retriever


TARGET_FAILURE_TYPES = {"Type E", "Type B"}
VARIANT_STYLES = (
    "cot_repair",
    "json_contract",
    "negative_guardrail",
    "evidence_first",
)


def select_bad_cases(
    *,
    eval_cases: list[EvalCase],
    result_rows: list[dict[str, Any]],
) -> list[tuple[EvalCase, dict[str, Any]]]:
    case_map = {case.case_id: case for case in eval_cases}
    selected: list[tuple[EvalCase, dict[str, Any]]] = []
    for row in result_rows:
        if float(row.get("f1", 0.0)) != 0.0:
            continue
        case = case_map.get(row["case_id"])
        if case is None or case.failure_type not in TARGET_FAILURE_TYPES:
            continue
        selected.append((case, row))
    return selected


def build_instruction(case: EvalCase) -> str:
    if case.failure_type == "Type E":
        return (
            "分析动态符号解析链。优先定位字符串别名表、symbol_by_name/by_name/"
            "loader helper，再把运行时解析终点还原成最终 FQN。"
        )
    return (
        "分析注册/装饰器/finalize 触发链。区分触发注册的中间 helper、"
        "真正构造对象的方法，以及最终的 direct/indirect/implicit 依赖。"
    )


def build_instruction_variant(case: EvalCase, style: str) -> str:
    base = build_instruction(case)
    if style == "cot_repair":
        return base + " 输出时先给四步推理，再给最终依赖。"
    if style == "json_contract":
        return base + " 最终答案必须收敛成严格 JSON，避免自由发挥。"
    if style == "negative_guardrail":
        return (
            base
            + " 特别注意不要把 alias helper / finalize hook / proxy wrapper 误报成 direct_deps。"
        )
    if style == "evidence_first":
        return base + " 先列出运行时解析证据，再写 direct/indirect/implicit。"
    raise ValueError(f"Unsupported style: {style}")


def build_reasoning(case: EvalCase) -> list[str]:
    if case.failure_type == "Type E":
        return [
            "Step 1: 先抽取问题里的字符串字面量或别名值，不要直接把 helper 当最终答案。",
            "Step 2: 回到别名表、loader/backend registry 或 symbol_by_name/by_name 调用点，找到该字面量映射到的真实导入路径。",
            "Step 3: 把 `module:attr` 或 dotted path 规范化成最终 FQN，并确认它在源码里真实存在。",
            "Step 4: direct_deps 只放终点符号；映射表和解析 helper 放到 indirect/implicit。"
        ]
    return [
        "Step 1: 找到注册入口，例如 decorator、finalize、task factory 或 proxy。",
        "Step 2: 沿着注册链继续追踪，分清触发注册的 helper 和真正构造对象的核心方法。",
        "Step 3: 如果有 registry / pending queue / side effect，记为 indirect 或 implicit，而不是误报为 direct。",
        "Step 4: 只把最终 materialize 的函数或类放进 direct_deps。"
    ]


def build_output(case: EvalCase) -> str:
    steps = build_reasoning(case)
    ground_truth = {
        "direct_deps": list(case.direct_gold_fqns),
        "indirect_deps": list(case.indirect_gold_fqns),
        "implicit_deps": list(case.implicit_gold_fqns),
    }
    return (
        "推理过程：\n"
        + "\n".join(steps)
        + "\n\n最终依赖：\n"
        + json.dumps(ground_truth, ensure_ascii=False)
    )


def build_output_variant(case: EvalCase, style: str) -> str:
    reasoning = build_reasoning(case)
    ground_truth = {
        "direct_deps": list(case.direct_gold_fqns),
        "indirect_deps": list(case.indirect_gold_fqns),
        "implicit_deps": list(case.implicit_gold_fqns),
    }
    if style == "json_contract":
        payload = {
            "reasoning_steps": reasoning,
            "ground_truth": ground_truth,
        }
        return json.dumps(payload, ensure_ascii=False)
    if style == "negative_guardrail":
        guardrail = (
            "纠错提醒：不要把中间 alias / registry / decorator wrapper 当成 direct_deps。"
            if case.failure_type == "Type E"
            else "纠错提醒：不要把 finalize / decorator / proxy 入口本身当成最终 direct_deps。"
        )
        return (
            guardrail
            + "\n\n推理过程：\n"
            + "\n".join(reasoning)
            + "\n\n最终依赖：\n"
            + json.dumps(ground_truth, ensure_ascii=False)
        )
    if style == "evidence_first":
        evidence = (
            "证据顺序：字符串/别名值 -> alias table / symbol_by_name -> 终点符号"
            if case.failure_type == "Type E"
            else "证据顺序：注册入口 -> materialize helper -> 最终 direct symbol"
        )
        return (
            evidence
            + "\n\n推理过程：\n"
            + "\n".join(reasoning)
            + "\n\n最终依赖：\n"
            + json.dumps(ground_truth, ensure_ascii=False)
        )
    return build_output(case)


def pick_context_excerpt(retriever, case: EvalCase, max_chars: int = 1600) -> str:
    chunk = None
    if case.entry_symbol and case.entry_symbol in retriever.symbol_to_ids:
        chunk_id = retriever.symbol_to_ids[case.entry_symbol][0]
        chunk = retriever.chunk_by_id[chunk_id]
    elif case.entry_file:
        module_name = _entry_file_to_module(case.entry_file)
        for chunk_id in retriever.module_to_ids.get(module_name, ()):
            candidate = retriever.chunk_by_id[chunk_id]
            if candidate.kind == "module":
                chunk = candidate
                break
        if chunk is None and retriever.module_to_ids.get(module_name):
            chunk = retriever.chunk_by_id[retriever.module_to_ids[module_name][0]]

    if chunk is None:
        return ""
    content = chunk.content.strip()
    if len(content) <= max_chars:
        return content
    return content[: max_chars - 3].rstrip() + "..."


def _entry_file_to_module(entry_file: str) -> str:
    path = Path(entry_file)
    parts = list(path.parts)
    if not parts:
        return ""
    stem = Path(parts[-1]).stem
    if stem == "__init__":
        parts = parts[:-1]
    else:
        parts[-1] = stem
    return ".".join(part for part in parts if part)


def build_input(case: EvalCase, excerpt: str) -> str:
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    if excerpt:
        parts.append(f"Entry Context:\n```python\n{excerpt}\n```")
    return "\n\n".join(parts)


def build_input_variant(case: EvalCase, excerpt: str, style: str) -> str:
    base = build_input(case, excerpt)
    if style == "cot_repair":
        prefix = "Repair Goal: 给出可复现的四步追踪链，最后再写最终依赖。"
    elif style == "json_contract":
        prefix = "Repair Goal: 输出必须可机读，最终一层使用 JSON。"
    elif style == "negative_guardrail":
        prefix = "Repair Goal: 先排除容易误报的 helper / wrapper / alias table，再确定最终 direct_deps。"
    elif style == "evidence_first":
        prefix = "Repair Goal: 先列 runtime 证据，再输出 direct/indirect/implicit。"
    else:
        raise ValueError(f"Unsupported style: {style}")
    return prefix + "\n\n" + base


def build_variant_records(
    *,
    case: EvalCase,
    source_row: dict[str, Any],
    excerpt: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for variant_id, style in enumerate(VARIANT_STYLES, start=1):
        record = {
            "instruction": build_instruction_variant(case, style),
            "input": build_input_variant(case, excerpt, style),
            "output": build_output_variant(case, style),
            "ground_truth": {
                "direct_deps": list(case.direct_gold_fqns),
                "indirect_deps": list(case.indirect_gold_fqns),
                "implicit_deps": list(case.implicit_gold_fqns),
            },
            "difficulty": case.difficulty,
            "failure_type": case.failure_type,
            "category": case.category,
            "repo_path": case.entry_file,
            "verified": True,
            "verify_method": "manual_bad_case_correction",
            "source_case_id": case.case_id,
            "source_model": "GPT-5.4 baseline",
            "source_badcase_f1": float(source_row.get("f1", 0.0)),
            "augment_strategy": "zero_f1_targeted_type_e_b_v2",
            "variant_id": variant_id,
            "variant_style": style,
        }
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate targeted bad-case finetune samples.")
    parser.add_argument("--cases", type=Path, default=Path("data/eval_cases.json"))
    parser.add_argument("--results", type=Path, default=Path("results/gpt5_eval_results.json"))
    parser.add_argument("--repo-root", type=Path, default=Path("external/celery"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/experiments/badcase_targeted_finetune_typeeb_v2.jsonl"),
    )
    args = parser.parse_args()

    eval_cases = load_eval_cases(args.cases)
    result_rows = json.loads(args.results.read_text(encoding="utf-8"))
    selected = select_bad_cases(eval_cases=eval_cases, result_rows=result_rows)
    retriever = build_retriever(args.repo_root)

    records: list[dict[str, Any]] = []
    for case, source_row in selected:
        excerpt = pick_context_excerpt(retriever, case)
        records.extend(
            build_variant_records(
                case=case,
                source_row=source_row,
                excerpt=excerpt,
            )
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {
        "num_records": len(records),
        "failure_type_distribution": {
            failure_type: sum(1 for record in records if record["failure_type"] == failure_type)
            for failure_type in sorted(TARGET_FAILURE_TYPES)
        },
        "variant_distribution": {
            style: sum(1 for record in records if record["variant_style"] == style)
            for style in VARIANT_STYLES
        },
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
