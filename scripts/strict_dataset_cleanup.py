#!/usr/bin/env python3
"""
严格数据清洗脚本

目标：
1. 修复正式评测集里少量不稳定/外部 helper 型 gold 标注
2. 为 few-shot 示例补齐 difficulty 字段，并修正明显的动态别名样例
3. 基于源码存在性校验，生成新的严格版微调 clean 文件
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from finetune.data_guard import _extract_ground_truth, validate_fqn

DATA_DIR = ROOT / "data"
SOURCE_DIR = ROOT / "external" / "celery" / "celery"
EVAL_PATH = DATA_DIR / "eval_cases.json"
FEWSHOT_PATH = DATA_DIR / "fewshot_examples_20.json"
FINETUNE_SOURCE_PATH = DATA_DIR / "finetune_dataset_500_clean.jsonl"
FINETUNE_OUTPUT_PATH = DATA_DIR / "finetune_dataset_500_clean_strict.jsonl"
REPORT_PATH = ROOT / "docs" / "data-quality-report-strict.md"
EXPECTED_COMMIT = "b8f85213f45c937670a6a6806ce55326a0eb537f"


@dataclass(frozen=True)
class FinetuneChange:
    index: int
    action: str
    category: str
    instruction: str
    before: dict[str, list[str]]
    after: dict[str, list[str]]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _dump_ground_truth(ground_truth: dict[str, list[str]]) -> str:
    return json.dumps(ground_truth, ensure_ascii=False)


def _rewrite_output(output: str, ground_truth: dict[str, list[str]]) -> str:
    marker = "最终依赖："
    payload = _dump_ground_truth(ground_truth)
    if marker in output:
        prefix, _, _ = output.partition(marker)
        return f"{prefix.rstrip()}\n\n{marker}\n{payload}"
    return payload


def _patch_eval_cases() -> list[str]:
    eval_cases = _read_json(EVAL_PATH)
    notes: list[str] = []

    for item in eval_cases:
        case_id = item["id"]
        if item.get("source_commit") != EXPECTED_COMMIT:
            item["source_commit"] = EXPECTED_COMMIT

        if case_id == "celery_hard_016":
            item["ground_truth"]["implicit_deps"] = []
            notes.append(f"{case_id}: 去掉外部 helper `importlib.import_module`")
        elif case_id == "celery_hard_015":
            item["ground_truth"]["implicit_deps"] = ["celery.signals.import_modules"]
            notes.append(f"{case_id}: 去掉外部 helper `vine.starpromise`")
        elif case_id == "celery_hard_018":
            item["ground_truth"]["implicit_deps"] = ["celery.utils.imports.symbol_by_name"]
            notes.append(
                f"{case_id}: 仅保留 Celery 内部可复核链路，移除 `os.environ.get` / `django.conf.settings`"
            )
        elif case_id == "celery_hard_019":
            item["ground_truth"]["implicit_deps"] = ["celery.utils.imports.import_from_cwd"]
            notes.append(f"{case_id}: 去掉外部 helper `importlib.import_module`")
        elif case_id == "celery_hard_121":
            item["ground_truth"]["implicit_deps"] = ["celery.signals.import_modules"]
            notes.append(f"{case_id}: 去掉外部 helper `vine.starpromise`")
        elif case_id == "celery_type_d_001":
            item["question"] = (
                "在 `celery/app/routes.py` 中，调用 "
                "`expand_router_string('my.router.module:RouterClass')` 时，"
                "负责把字符串参数 `router` 解析成真实符号的函数是哪个？"
            )
            item["ground_truth"] = {
                "direct_deps": ["celery.utils.imports.symbol_by_name"],
                "indirect_deps": [],
                "implicit_deps": [],
            }
            item["reasoning_hint"] = (
                "`expand_router_string` 内部首先执行 `router = symbol_by_name(router)`，"
                "参数名遮蔽不会改变真正负责解析字符串的函数。"
            )
            notes.append(f"{case_id}: 修正为稳定的内部解析函数问题")
        elif case_id == "celery_type_d_006":
            item["question"] = (
                "在 `celery/concurrency/__init__.py` 中，若在首次导入前设置 "
                "`CELERY_CUSTOM_WORKER_POOL='celery.concurrency.thread:TaskPool'`，"
                "那么 `get_implementation('custom')` 最终返回哪个 Celery 类？"
            )
            item["ground_truth"] = {
                "direct_deps": ["celery.concurrency.thread.TaskPool"],
                "indirect_deps": ["celery.concurrency.get_implementation"],
                "implicit_deps": ["celery.concurrency.ALIASES"],
            }
            item["reasoning_hint"] = (
                "模块导入时把环境变量写入 `ALIASES['custom']`，"
                "随后 `get_implementation('custom')` 按该别名返回线程池类。"
            )
            notes.append(f"{case_id}: 修正为稳定且可复核的内部目标类")
        elif case_id == "celery_type_a_003":
            item["ground_truth"]["implicit_deps"] = []
            notes.append(f"{case_id}: 去掉外部 helper `vine.starpromise`")
        elif case_id == "celery_medium_019":
            item["question"] = (
                "在 `celery/utils/imports.py` 中，`instantiate('celery.concurrency.prefork:TaskPool')` "
                "这条链路最终解析到哪个真实 Celery 符号？中间依赖哪个导入解析函数？"
            )
            item["ground_truth"] = {
                "direct_deps": ["celery.concurrency.prefork.TaskPool"],
                "indirect_deps": [
                    "celery.utils.imports.instantiate",
                    "celery.utils.imports.symbol_by_name",
                ],
                "implicit_deps": [],
            }
            item["reasoning_hint"] = (
                "`instantiate` 直接调用本模块已导入的 `symbol_by_name(name)`，"
                "最终把字符串解析为 `celery.concurrency.prefork.TaskPool`。"
            )
            notes.append(f"{case_id}: 用内部最终目标替换外部 re-export 细节")
        elif case_id == "celery_easy_020":
            item["question"] = (
                "`celery.utils.imports.load_extension_classes(namespace)` 这条扩展加载链里，"
                "哪个 Celery 函数先枚举 entry point 的 `(name, value)`，"
                "哪个 Celery 函数再把 `value` 字符串解析成真实类？"
            )
            item["ground_truth"] = {
                "direct_deps": [
                    "celery.utils.imports.load_extension_class_names",
                    "celery.utils.imports.load_extension_classes",
                ],
                "indirect_deps": ["celery.utils.imports.symbol_by_name"],
                "implicit_deps": [],
            }
            item["reasoning_hint"] = (
                "`load_extension_class_names` 负责枚举 entry point 名称和值，"
                "`load_extension_classes` 再把 value 字符串交给 `symbol_by_name` 解析。"
            )
            notes.append(f"{case_id}: 改成纯内部扩展加载链问题")

    _write_json(EVAL_PATH, eval_cases)
    return notes


def _patch_fewshot() -> list[str]:
    fewshot = _read_json(FEWSHOT_PATH)
    notes: list[str] = []
    difficulty_map = {
        "B01": "hard",
        "B02": "hard",
        "B03": "medium",
        "B04": "hard",
        "B05": "medium",
        "C01": "easy",
        "C02": "medium",
        "C03": "medium",
        "C04": "medium",
        "C05": "hard",
        "D01": "easy",
        "D02": "medium",
        "D03": "medium",
        "D04": "hard",
        "E01": "hard",
        "E02": "hard",
        "E03": "medium",
        "E04": "hard",
        "A01": "hard",
        "A02": "hard",
    }

    for item in fewshot:
        item["difficulty"] = difficulty_map[item["id"]]
        if item["id"] == "E04":
            item["ground_truth"] = {
                "direct_deps": ["celery.concurrency.thread.TaskPool"],
                "indirect_deps": ["celery.concurrency.get_implementation"],
                "implicit_deps": ["celery.concurrency.ALIASES"],
            }
            notes.append("E04: 改为内部可复核的 alias 解析结果")

    _write_json(FEWSHOT_PATH, fewshot)
    notes.append("fewshot: 20 条全部补齐 difficulty 字段")
    return notes


def _sanitize_ground_truth(ground_truth: dict[str, Any]) -> dict[str, list[str]]:
    cleaned: dict[str, list[str]] = {
        "direct_deps": [],
        "indirect_deps": [],
        "implicit_deps": [],
    }
    for key in cleaned:
        values = ground_truth.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            valid, _ = validate_fqn(value, SOURCE_DIR)
            if valid:
                cleaned[key].append(value)
    return cleaned


def _patch_finetune() -> tuple[list[dict[str, Any]], list[FinetuneChange]]:
    changes: list[FinetuneChange] = []
    cleaned_rows: list[dict[str, Any]] = []
    lines = FINETUNE_SOURCE_PATH.read_text(encoding="utf-8-sig").splitlines()

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        ground_truth = _extract_ground_truth(row)
        if not isinstance(ground_truth, dict):
            changes.append(
                FinetuneChange(
                    index=index,
                    action="drop",
                    category=str(row.get("category", "")),
                    instruction=str(row.get("instruction", "")),
                    before={},
                    after={},
                )
            )
            continue

        cleaned_ground_truth = _sanitize_ground_truth(ground_truth)
        before = {
            key: list(ground_truth.get(key, [])) if isinstance(ground_truth.get(key), list) else []
            for key in ("direct_deps", "indirect_deps", "implicit_deps")
        }
        total = sum(len(values) for values in cleaned_ground_truth.values())
        if total == 0 or not cleaned_ground_truth["direct_deps"]:
            changes.append(
                FinetuneChange(
                    index=index,
                    action="drop",
                    category=str(row.get("category", "")),
                    instruction=str(row.get("instruction", "")),
                    before=before,
                    after=cleaned_ground_truth,
                )
            )
            continue

        if cleaned_ground_truth != before:
            row["output"] = _rewrite_output(str(row.get("output", "")), cleaned_ground_truth)
            if "ground_truth" in row:
                row["ground_truth"] = cleaned_ground_truth
            changes.append(
                FinetuneChange(
                    index=index,
                    action="patch",
                    category=str(row.get("category", "")),
                    instruction=str(row.get("instruction", "")),
                    before=before,
                    after=cleaned_ground_truth,
                )
            )

        cleaned_rows.append(row)

    FINETUNE_OUTPUT_PATH.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in cleaned_rows) + "\n",
        encoding="utf-8",
    )
    return cleaned_rows, changes


def _write_report(
    eval_notes: list[str],
    fewshot_notes: list[str],
    finetune_rows: list[dict[str, Any]],
    finetune_changes: list[FinetuneChange],
) -> None:
    drops = [change for change in finetune_changes if change.action == "drop"]
    patches = [change for change in finetune_changes if change.action == "patch"]

    lines = [
        "# 严格数据质检报告",
        "",
        "**日期**: 2026-03-27",
        f"**Celery 版本**: `{EXPECTED_COMMIT}`",
        "",
        "## 结果摘要",
        "",
        "| 数据集 | 处理结果 |",
        "|------|------|",
        f"| `data/eval_cases.json` | 保留 54 条，修正 {len(eval_notes)} 处 gold / 题面口径 |",
        f"| `data/fewshot_examples_20.json` | 保留 20 条，补齐 20 条 `difficulty`，并修正 {max(len(fewshot_notes) - 1, 0)} 条示例 |",
        f"| `data/finetune_dataset_500_clean_strict.jsonl` | 从 488 条严格清到 {len(finetune_rows)} 条，删除 {len(drops)} 条，修补 {len(patches)} 条 |",
        "",
        "## 正式评测集修正",
        "",
    ]
    lines.extend(f"- {note}" for note in eval_notes)
    lines.extend(
        [
            "",
            "## Few-shot 修正",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in fewshot_notes)
    lines.extend(
        [
            "",
            "## 微调集删除项",
            "",
        ]
    )
    for change in drops:
        lines.append(
            f"- line {change.index}: `{change.category}` 删除。原因：清洗后无有效 direct_deps。"
        )
    lines.extend(
        [
            "",
            "## 微调集修补项",
            "",
        ]
    )
    for change in patches:
        lines.append(
            f"- line {change.index}: `{change.category}` 修补为 `{change.after}`。"
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    eval_notes = _patch_eval_cases()
    fewshot_notes = _patch_fewshot()
    finetune_rows, finetune_changes = _patch_finetune()
    _write_report(eval_notes, fewshot_notes, finetune_rows, finetune_changes)
    print(
        json.dumps(
            {
                "eval_notes": len(eval_notes),
                "fewshot_notes": len(fewshot_notes),
                "finetune_rows": len(finetune_rows),
                "finetune_drops": sum(
                    1 for change in finetune_changes if change.action == "drop"
                ),
                "finetune_patches": sum(
                    1 for change in finetune_changes if change.action == "patch"
                ),
                "finetune_output": str(FINETUNE_OUTPUT_PATH.relative_to(ROOT)),
                "report": str(REPORT_PATH.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
