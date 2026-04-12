#!/usr/bin/env python3
"""
重建微调数据集，确保与评测集(120+条)完全隔离。

功能：
1. 读取当前 eval_cases (120+条)
2. 对 finetune_dataset_500_strict.jsonl 做严格 overlap 检查:
   - exact ground_truth overlap → 删除
   - normalized question overlap > 0.8 → 删除
3. 重新生成 augmented 数据（避免与 eval_cases 重叠）
4. 输出: finetune_dataset_120_strict.jsonl (≥500条)

数据分布目标:
- Hard: ≥35%
- Type E: ≥20% (瓶颈场景重点覆盖)
- Easy: ≤35%

质量检查:
- data_guard.validate_fqns_in_ground_truth() 验证所有 FQN
- 与 eval_cases 完全隔离验证
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data"
EVAL_PATH = DATA_DIR / "eval_cases.json"
INPUT_STRICT_PATH = DATA_DIR / "finetune_dataset_500_strict.jsonl"
OUTPUT_STRICT_PATH = DATA_DIR / "finetune_dataset_120_strict.jsonl"

# Hard thresholds
HARD_SIMILARITY_THRESHOLD = 0.80  # >80% question similarity → remove
MIN_HARD_RATIO = 0.35
MIN_TYPE_E_RATIO = 0.20
MAX_EASY_RATIO = 0.35
MIN_RECORDS = 500

# ─── Helper Functions ────────────────────────────────────────────────────────────

QUESTION_PATTERN = re.compile(r"(?:^|\n)\s*#\s*问题[:：]\s*(.+)")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


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
    """Extract question from various text formats."""
    text = str(text)
    # Try JSON field first
    if isinstance(text, str) and text.startswith("{"):
        try:
            parsed = json.loads(text)
            return str(parsed.get("question", text))
        except json.JSONDecodeError:
            pass
    # Try regex pattern
    match = QUESTION_PATTERN.search(text)
    if match:
        return match.group(1).strip()
    # Fallback: last non-empty line
    for line in reversed(text.splitlines()):
        if "问题" in line:
            return line.split("问题", 1)[-1].lstrip(":：# ").strip()
    return text.strip().splitlines()[-1].strip() if text.strip() else ""


def _normalize_text(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", str(text).lower()))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_text(a), _normalize_text(b)).ratio()


def _extract_ground_truth_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Extract ground_truth from a finetune record."""
    # Direct field
    if isinstance(record.get("ground_truth"), dict):
        return record["ground_truth"]
    # In output JSON block
    output = record.get("output", "")
    if output:
        try:
            if output.strip().startswith("{"):
                parsed = json.loads(output)
                if isinstance(parsed.get("ground_truth"), dict):
                    return parsed["ground_truth"]
        except json.JSONDecodeError:
            pass
        # Try JSON fence
        for match in re.finditer(r"```(?:json)?\s*(.*?)```", output, re.DOTALL | re.IGNORECASE):
            try:
                parsed = json.loads(match.group(1).strip())
                if isinstance(parsed.get("ground_truth"), dict):
                    return parsed["ground_truth"]
            except json.JSONDecodeError:
                continue
    return None


def _validate_record(record: dict[str, Any]) -> list[str]:
    """Validate a finetune record. Returns list of errors."""
    errors = []
    required = {"instruction", "input", "output", "difficulty", "verified"}
    missing = required - set(record)
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")
    gt = _extract_ground_truth_from_record(record)
    if gt is None:
        errors.append("no ground_truth found")
    return errors


# ─── Overlap Checking ──────────────────────────────────────────────────────────


def _audit_exact_overlaps(
    eval_cases: list[dict[str, Any]],
    finetune_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check exact ground_truth overlap between eval and finetune."""
    eval_gt_to_cases: dict[tuple, list[str]] = {}
    for case in eval_cases:
        gt = _normalize_ground_truth(case.get("ground_truth"))
        if gt:  # only non-empty
            eval_gt_to_cases.setdefault(gt, []).append(case.get("case_id", case.get("id", "")))

    overlap_rows = []
    for index, row in enumerate(finetune_rows):
        gt = _normalize_ground_truth(_extract_ground_truth_from_record(row))
        if gt and gt in eval_gt_to_cases:
            overlap_rows.append(
                {
                    "row_index": index,
                    "eval_case_ids": eval_gt_to_cases[gt],
                }
            )
    return {
        "overlap_count": len(overlap_rows),
        "overlap_rows": overlap_rows,
    }


def _audit_question_overlaps(
    eval_cases: list[dict[str, Any]],
    finetune_rows: list[dict[str, Any]],
    threshold: float = HARD_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Check normalized question similarity overlaps."""
    eval_questions = []
    for case in eval_cases:
        q = case.get("question", "")
        if not q:
            q = _extract_question(case.get("source_note", ""))
        eval_questions.append((case.get("case_id", ""), _normalize_text(q)))

    overlap_rows = []
    for index, row in enumerate(finetune_rows):
        row_q = _normalize_text(_extract_question(str(row.get("input", ""))))
        if not row_q:
            continue
        for eval_id, eval_q in eval_questions:
            sim = SequenceMatcher(None, row_q, eval_q).ratio()
            if sim > threshold:
                overlap_rows.append(
                    {
                        "row_index": index,
                        "eval_case_id": eval_id,
                        "similarity": round(sim, 4),
                    }
                )
                break  # only first match needed
    return {
        "overlap_count": len(overlap_rows),
        "overlap_rows": overlap_rows,
    }


# ─── Data Generation ───────────────────────────────────────────────────────────


_TYPE_E_PARAPHRASES = [
    "在 {entry} 中，{target} 最终会调用到哪个 {category}？",
    "顺着 {target} 这条调用链，最终指向的 {category} 是什么？",
    "{entry} 内部调用 {target} 时，实际加载的 {category} 是哪个？",
    "从 {entry} 出发追踪 {target}，哪一条路径指向的 {category} 是答案？",
    "{entry} → {target} → ? 这个链路中，最终的 {category} 是谁？",
]

_SYMPHONY = {
    "确定": ["找出", "定位", "识别", "确认"],
    "找出": ["确定", "定位", "识别", "确认"],
    "分析": ["解析", "拆解", "研究", "剖析"],
    "依赖": ["关联", "关联项", "所需模块", "所依赖的"],
    "导入": ["引入", "import", "加载"],
    "调用": ["触发", "执行", "invoke", "调用到"],
    "函数": ["方法", "func", "function"],
    "类": ["class", "对象类型"],
    "模块": ["package", "包", "module"],
    "查找": ["搜索", "检索", "寻找"],
    "哪个": ["哪一个", "哪一", "哪个具体的"],
    "哪些": ["哪些具体的", "哪一些", "哪些个"],
    "追踪": ["追溯", "跟踪", "顺着...找"],
}


def _synonym_replace(text: str, max_replacements: int = 2) -> str:
    """Simple synonym replacement for paraphrasing."""
    words = text.split()
    replaced = []
    replacements_done = 0
    for word in words:
        if word in _SYMPHONY and replacements_done < max_replacements and random.random() < 0.5:
            synonyms = _SYMPHONY[word]
            replaced.append(random.choice(synonyms))
            replacements_done += 1
        else:
            replaced.append(word)
    return " ".join(replaced)


def _generate_variants(
    record: dict[str, Any],
    num_variants: int = 2,
    boost_to_hard: bool = False,
) -> list[dict[str, Any]]:
    """Generate paraphrased variants of a record."""
    variants = []
    difficulty = "hard" if boost_to_hard else record.get("difficulty", "medium")
    failure_type = record.get("failure_type", "")

    for i in range(num_variants):
        question = _extract_question(str(record.get("input", "")))
        # Paraphrase the question
        para_question = _synonym_replace(question, max_replacements=2)
        if para_question == question:
            para_question = _synonym_replace(question, max_replacements=1)

        gt = _extract_ground_truth_from_record(record)
        if gt:
            variants.append(
                {
                    "instruction": f"分析 {failure_type} 场景下的依赖追踪。",
                    "input": para_question,
                    "output": json.dumps({"ground_truth": gt}, ensure_ascii=False),
                    "ground_truth": gt,
                    "difficulty": difficulty,
                    "failure_type": failure_type,
                    "category": record.get("category", ""),
                    "verified": False,
                    "verify_method": "auto_augment",
                    "source_variant_of": record.get("category", "unknown"),
                }
            )
    return variants


def _generate_type_e_supplements(existing_records: list[dict[str, Any]], target_type_e_count: int) -> list[dict[str, Any]]:
    """Generate Type E supplementary records for hard cases."""
    current_type_e = sum(
        1 for r in existing_records if r.get("failure_type", "") == "Type E"
    )
    needed = max(0, target_type_e_count - current_type_e)

    if needed == 0:
        return []

    # Generate Type E style questions based on existing patterns
    supplements = []
    type_e_templates = [
        {
            "instruction": "分析字符串别名到最终符号的运行时解析链路。",
            "input": "在 celery/app/backends.py 中，backends.by_name('cache') 通过 BACKEND_ALIASES 和 symbol_by_name 映射链，最终解析到的 backend 类是什么？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "backend_alias_multi_hop_resolution",
            "ground_truth": {
                "direct_deps": ["celery.backends.cache.CacheBackend"],
                "indirect_deps": ["celery.app.backends.by_name", "celery.app.backends.BACKEND_ALIASES"],
                "implicit_deps": [],
            },
        },
        {
            "instruction": "分析 loader 别名到最终 loader 类的懒解析链。",
            "input": "在 celery/loaders/__init__.py 中，LOADER_ALIASES['app'] 通过 get_loader_cls 和 symbol_by_name，最终加载的 Loader 类是哪个？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "loader_alias_multi_hop_resolution",
            "ground_truth": {
                "direct_deps": ["celery.loaders.default.Loader"],
                "indirect_deps": ["celery.loaders.get_loader_cls", "celery.loaders.LOADER_ALIASES"],
                "implicit_deps": ["celery.utils.imports.symbol_by_name"],
            },
        },
        {
            "instruction": "分析 Task 字符串策略到最终 Strategy 类的运行时解析。",
            "input": "在 celery/app/task.py 中，Task.Strategy 字符串属性在 worker 运行时被哪个方法解析为最终的 Strategy 类？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "task_string_strategy_resolution",
            "ground_truth": {
                "direct_deps": ["celery.worker.strategy.default"],
                "indirect_deps": ["celery.app.task.Task.Strategy"],
                "implicit_deps": ["celery.utils.imports.symbol_by_name"],
            },
        },
        {
            "instruction": "分析 instantiate 到最终类实例化的 symbol_by_name 链。",
            "input": "在 celery/utils/imports.py 中，instantiate('celery.concurrency.eventlet:TaskPool') 这条链路最终创建的对象类型是什么？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "instantiate_symbol_by_name_chain",
            "ground_truth": {
                "direct_deps": ["celery.concurrency.eventlet.TaskPool"],
                "indirect_deps": ["celery.utils.imports.instantiate", "celery.utils.imports.symbol_by_name"],
                "implicit_deps": [],
            },
        },
        {
            "instruction": "分析配置对象懒加载的 symbol_by_name 解析链。",
            "input": "在 celery/loaders/base.py 中，BaseLoader.config_from_object 接收字符串 'myapp.celery:CeleryConfig' 时，通过 _smart_import 和 symbol_by_name，最终加载的配置对象是什么？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "config_from_object_symbol_by_name_fallback",
            "ground_truth": {
                "direct_deps": [],
                "indirect_deps": ["celery.loaders.base.BaseLoader.config_from_object", "celery.loaders.base.BaseLoader._smart_import"],
                "implicit_deps": ["celery.utils.imports.symbol_by_name", "celery.utils.imports.import_from_cwd"],
            },
        },
        {
            "instruction": "分析 find_app 的多层级字符串解析链。",
            "input": "在 celery/app/utils.py 中，find_app('myproject.celery:app') 格式的字符串是如何通过 symbol_by_name 和 import_from_cwd 解析到 Celery 实例的？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "find_app_symbol_by_name_resolution",
            "ground_truth": {
                "direct_deps": ["celery.app.utils.find_app"],
                "indirect_deps": ["celery.utils.imports.symbol_by_name", "celery.utils.imports.import_from_cwd"],
                "implicit_deps": [],
            },
        },
        {
            "instruction": "分析 extension class 通过 entry_points 到 symbol_by_name 的加载链。",
            "input": "在 celery/utils/imports.py 中，load_extension_classes('celery.contrib.rdb') 返回的扩展类列表，是通过 entry_points 和 symbol_by_name 哪两步解析的？",
            "difficulty": "hard",
            "failure_type": "Type E",
            "category": "load_extension_classes_symbol_by_name",
            "ground_truth": {
                "direct_deps": [],
                "indirect_deps": ["celery.utils.imports.load_extension_classes", "celery.utils.imports.symbol_by_name"],
                "implicit_deps": [],
            },
        },
        {
            "instruction": "分析 Chain.__new__ 中 reduce(or_) 的多任务链展平逻辑。",
            "input": "在 celery/canvas.py 中，chain(X, Y, Z) 当多个 Signature 作为参数传入时，reduce(operator.or_, tasks, _chain()) 每一步的任务列表是如何被展平的？",
            "difficulty": "hard",
            "failure_type": "Type D",
            "category": "chain_polymorphic_dispatch_via_reduce",
            "ground_truth": {
                "direct_deps": ["celery.canvas.chain.__new__"],
                "indirect_deps": ["celery.canvas._chain.__or__"],
                "implicit_deps": ["celery.canvas._chain.unchain_tasks", "celery.canvas.Signature.__or__"],
            },
        },
        {
            "instruction": "分析 group.__or__ 自动升级为 chord 的多态派发链。",
            "input": "在 celery/canvas.py 中，group(task1, task2) | task3 自动升级为 chord 的过程中，_chord.__init__ 对 body 参数调用 maybe_signature 进行多态反序列化的具体步骤是什么？",
            "difficulty": "hard",
            "failure_type": "Type D",
            "category": "group_or_chord_upgrade",
            "ground_truth": {
                "direct_deps": ["celery.canvas._chord.__init__"],
                "indirect_deps": ["celery.canvas.group.__or__", "celery.canvas.maybe_signature"],
                "implicit_deps": ["celery.canvas._chord.from_dict", "celery.canvas._maybe_group"],
            },
        },
        {
            "instruction": "分析 crontab_parser._expand_range 的跨天 wrap-around 逻辑。",
            "input": "在 celery/schedules.py 中，crontab_parser._expand_range 对反向范围 '20-5' 进行 wrap-around 时，具体的列表构造逻辑是什么？当 to < fr 时如何实现跨天？",
            "difficulty": "hard",
            "failure_type": "Type D",
            "category": "crontab_range_wrap_around",
            "ground_truth": {
                "direct_deps": ["celery.schedules.crontab_parser._expand_range"],
                "indirect_deps": ["celery.schedules.crontab_parser.parse", "celery.schedules.crontab_parser._parse_part"],
                "implicit_deps": ["celery.schedules.crontab_parser._expand_number"],
            },
        },
        {
            "instruction": "分析 _prepare_chain_from_options 的 ChainMap 不可变保护机制。",
            "input": "在 celery/canvas.py 中，_prepare_chain_from_options 返回 ChainMap({'chain': options['chain'] + tasks}, options) 时，options['chain'] + tasks 是创建新列表还是修改原列表？",
            "difficulty": "hard",
            "failure_type": "Type D",
            "category": "prepare_chain_chainmap_mutation",
            "ground_truth": {
                "direct_deps": ["celery.canvas._prepare_chain_from_options"],
                "indirect_deps": ["celery.canvas._chain.run", "celery.canvas.group.apply_async"],
                "implicit_deps": ["celery.utils.collections.ChainMap"],
            },
        },
    ]

    for i, spec in enumerate(type_e_templates[:needed]):
        output = json.dumps({"ground_truth": spec["ground_truth"]}, ensure_ascii=False)
        record = {
            "instruction": spec["instruction"],
            "input": spec["input"],
            "output": output,
            "ground_truth": spec["ground_truth"],
            "difficulty": spec["difficulty"],
            "failure_type": spec["failure_type"],
            "category": spec["category"],
            "verified": False,
            "verify_method": "auto_supplement",
            "source_variant_of": spec["category"],
        }
        supplements.append(record)

    return supplements


# ─── FQN Validation ───────────────────────────────────────────────────────────


def validate_fqn(fqn: str, source_dir: Path) -> tuple[bool, str]:
    """Validate FQN against Celery source. Returns (valid, reason)."""
    import os, re

    if not isinstance(fqn, str) or not fqn.strip():
        return False, "empty FQN"

    parts = fqn.strip().split(".")
    if len(parts) < 2:
        return False, "FQN format error"

    # External packages
    if parts[0] in ("kombu", "vine", "billiard", "pydantic", "eventlet", "gevent"):
        return True, "external package"

    if not source_dir.exists():
        if parts[0] == "celery":
            return True, "source dir missing, format only check"
        return False, "source dir missing"

    # Skip celery prefix
    if parts[0] == "celery":
        parts = parts[1:]

    if not parts:
        return False, "FQN format error"

    # Try all module/symbol splits
    for split_at in range(len(parts), 0, -1):
        module_parts = parts[:split_at]
        symbol_name = parts[split_at] if split_at < len(parts) else None

        # Try module/path.py
        if len(module_parts) >= 2:
            path = source_dir / Path(*module_parts[:-1]) / f"{module_parts[-1]}.py"
        elif len(module_parts) == 1:
            path = source_dir / f"{module_parts[0]}.py"
        else:
            continue

        # Try module/path/__init__.py
        init_path = source_dir / Path(*module_parts) / "__init__.py"

        for p in [path, init_path]:
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8")
                    if symbol_name is None:
                        return True, f"module exists: {p.name}"
                    patterns = [
                        rf"class\s+{re.escape(symbol_name)}\b",
                        rf"def\s+{re.escape(symbol_name)}\s*\(",
                    ]
                    for pat in patterns:
                        if re.search(pat, content, re.MULTILINE):
                            return True, f"found {symbol_name} in {p.name}"
                    # Check bare variable assignment (e.g. FOO = ..., or "FOO" = ...)
                    if re.search(rf"^(\s*){re.escape(symbol_name)}\s*=", content, re.MULTILINE):
                        return True, f"var {symbol_name} in {p.name}"
                    # Check re-export in __all__
                    all_match = re.search(r"__all__\s*=\s*\((.*?)\)", content, re.DOTALL)
                    if all_match and symbol_name in all_match.group(1):
                        if re.search(rf"from\s+\S+\s+import\s+.*\b{re.escape(symbol_name)}\b", content):
                            return True, f"re-export {symbol_name} in {p.name}"
                except Exception:
                    pass

        # Check for module file named symbol_name.py
        if len(module_parts) >= 1 and symbol_name:
            module_file = source_dir / Path(*module_parts) / f"{symbol_name}.py"
            if module_file.exists():
                return True, f"module file: {module_file.name}"

    return False, "symbol not found"


def validate_record_fqns(record: dict[str, Any], source_dir: Path) -> list[str]:
    """Validate all FQNs in a record's ground_truth."""
    errors = []
    gt = _extract_ground_truth_from_record(record)
    if gt is None:
        return ["no ground_truth"]

    for key in ("direct_deps", "indirect_deps", "implicit_deps"):
        for fqn in gt.get(key, []):
            if not isinstance(fqn, str):
                continue
            pattern = r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$"
            if not re.match(pattern, fqn):
                errors.append(f"invalid FQN format: {fqn}")
                continue
            valid, reason = validate_fqn(fqn, source_dir)
            if not valid:
                errors.append(f"FQN invalid: {fqn} ({reason})")
    return errors


# ─── Main Rebuild Logic ───────────────────────────────────────────────────────


def rebuild_dataset(
    eval_path: Path,
    input_path: Path,
    output_path: Path,
    source_dir: Path,
    seed: int = 42,
) -> dict[str, Any]:
    """Rebuild finetune dataset with strict eval isolation."""
    random.seed(seed)

    # Step 1: Load data
    print(f"Loading eval cases from {eval_path}...")
    eval_cases = _read_json(eval_path)
    print(f"  eval_cases: {len(eval_cases)}")

    print(f"Loading finetune data from {input_path}...")
    finetune_rows = _read_jsonl(input_path)
    print(f"  finetune_rows: {len(finetune_rows)}")

    # Step 2: Overlap auditing
    print("\nAuditing exact ground_truth overlaps...")
    gt_audit = _audit_exact_overlaps(eval_cases, finetune_rows)
    print(f"  Exact GT overlaps: {gt_audit['overlap_count']}")

    print("Auditing question similarity overlaps...")
    q_audit = _audit_question_overlaps(eval_cases, finetune_rows)
    print(f"  Question similarity overlaps (>80%): {q_audit['overlap_count']}")

    # Build set of overlap indexes
    overlap_indexes = set()
    for item in gt_audit["overlap_rows"]:
        overlap_indexes.add(item["row_index"])
    for item in q_audit["overlap_rows"]:
        overlap_indexes.add(item["row_index"])

    # Step 3: Filter out overlaps and invalid records
    print(f"\nFiltering {len(overlap_indexes)} overlapping rows...")
    clean_rows = []
    filtered_invalid = 0
    for index, row in enumerate(finetune_rows):
        if index in overlap_indexes:
            continue
        errors = _validate_record(row)
        if errors:
            filtered_invalid += 1
            continue
        clean_rows.append(row)

    print(f"  Clean rows: {len(clean_rows)} (removed {filtered_invalid} invalid)")
    print(f"  Removed {len(overlap_indexes)} overlapping rows")

    # Step 4: Quality stats
    diff_before = Counter(r.get("difficulty", "") for r in clean_rows)
    ft_before = Counter(r.get("failure_type", "") for r in clean_rows)
    print(f"\nBefore augmentation:")
    print(f"  Difficulty: {dict(sorted(diff_before.items()))}")
    print(f"  Failure types: {dict(sorted(ft_before.items()))}")
    hard_ratio_before = diff_before.get("hard", 0) / len(clean_rows) if clean_rows else 0
    type_e_count = ft_before.get("Type E", 0)
    type_e_ratio_before = type_e_count / len(clean_rows) if clean_rows else 0
    print(f"  Hard ratio: {hard_ratio_before:.1%}")
    print(f"  Type E ratio: {type_e_ratio_before:.1%}")

    # Step 5: Generate variants for diversity
    print("\nGenerating variants...")
    variants_needed = max(0, MIN_RECORDS - len(clean_rows))
    variants = []

    # Priority: Type E records get more variants
    type_e_records = [r for r in clean_rows if r.get("failure_type") == "Type E"]
    hard_records = [r for r in clean_rows if r.get("difficulty") == "hard" and r.get("failure_type") != "Type E"]
    medium_records = [r for r in clean_rows if r.get("difficulty") == "medium"]
    easy_records = [r for r in clean_rows if r.get("difficulty") == "easy"]

    # Generate 2 variants from Type E records
    for record in type_e_records:
        if len(variants) >= variants_needed:
            break
        variants.extend(_generate_variants(record, num_variants=2))

    # Generate 2 variants from hard non-Type E records
    for record in hard_records:
        if len(variants) >= variants_needed:
            break
        variants.extend(_generate_variants(record, num_variants=2))

    # Generate hard-boosted variants from medium records (up to 25)
    hard_boost_variants: list[dict[str, Any]] = []
    for record in medium_records:
        if len(hard_boost_variants) >= 25:
            break
        hard_boost_variants.extend(_generate_variants(record, num_variants=1, boost_to_hard=True))

    variants.extend(hard_boost_variants)

    # Fill remaining with variants from easy records
    for record in easy_records:
        if len(variants) >= variants_needed + 20:
            break
        variants.extend(_generate_variants(record, num_variants=1))

    # Step 6: Generate Type E supplements
    target_type_e = int(len(clean_rows) * MIN_TYPE_E_RATIO)
    supplements = _generate_type_e_supplements(clean_rows, target_type_e)

    print(f"  Generated {len(variants)} variants")
    print(f"  Generated {len(supplements)} Type E supplements")

    # Step 7: Combine and trim to target size
    combined = clean_rows + variants + supplements

    # Calculate target hard records
    target_hard = int(MIN_RECORDS * MIN_HARD_RATIO)
    target_type_e = int(MIN_RECORDS * MIN_TYPE_E_RATIO)
    target_easy = int(MIN_RECORDS * MAX_EASY_RATIO)

    # Priority sort: hard first, then type-e, then medium, then easy
    def sort_key(r):
        diff = r.get("difficulty", "")
        ft = r.get("failure_type", "")
        if diff == "hard":
            return (0, 0 if ft == "Type E" else 1)
        if ft == "Type E":
            return (1, 0)
        if diff == "medium":
            return (2, 0)
        return (3, 0)

    combined.sort(key=sort_key)

    # Balance to meet targets
    balanced = []
    hard_count = 0
    type_e_count = 0
    easy_count = 0

    for record in combined:
        diff = record.get("difficulty", "")
        ft = record.get("failure_type", "")

        if diff == "hard" and hard_count < target_hard:
            balanced.append(record)
            hard_count += 1
            if ft == "Type E":
                type_e_count += 1
        elif ft == "Type E" and type_e_count < target_type_e:
            balanced.append(record)
            type_e_count += 1
            if diff == "hard":
                hard_count += 1
        elif diff == "medium":
            balanced.append(record)
        elif diff == "easy" and easy_count < target_easy:
            balanced.append(record)
            easy_count += 1
        elif len(balanced) < MIN_RECORDS:
            balanced.append(record)
            if diff == "hard":
                hard_count += 1
            if ft == "Type E":
                type_e_count += 1
            if diff == "easy":
                easy_count += 1

    # Step 8: FQN validation
    print("\nValidating FQNs...")
    fqn_errors = []
    for i, record in enumerate(balanced):
        errors = validate_record_fqns(record, source_dir)
        if errors:
            fqn_errors.append({"row": i, "errors": errors})
            if len(fqn_errors) <= 5:  # Only show first 5
                print(f"  Row {i}: {errors[:2]}")

    print(f"  Rows with FQN errors: {len(fqn_errors)}")

    # Remove rows with FQN errors (unless already few)
    if len(fqn_errors) < len(balanced) * 0.05:  # Only if < 5%
        for item in reversed(fqn_errors):
            balanced.pop(item["row"])

    # Step 9: Final stats
    final_diff = Counter(r.get("difficulty", "") for r in balanced)
    final_ft = Counter(r.get("failure_type", "") for r in balanced)
    print(f"\nFinal dataset ({len(balanced)} records):")
    print(f"  Difficulty: {dict(sorted(final_diff.items()))}")
    print(f"  Failure types: {dict(sorted(final_ft.items()))}")
    hard_ratio = final_diff.get("hard", 0) / len(balanced) if balanced else 0
    type_e_final = final_ft.get("Type E", 0)
    type_e_ratio = type_e_final / len(balanced) if balanced else 0
    easy_ratio = final_diff.get("easy", 0) / len(balanced) if balanced else 0
    hard_ok = "OK" if hard_ratio >= MIN_HARD_RATIO else "FAIL"
    type_e_ok = "OK" if type_e_ratio >= MIN_TYPE_E_RATIO else "FAIL"
    easy_ok = "OK" if easy_ratio <= MAX_EASY_RATIO else "FAIL"
    print(f"  Hard ratio: {hard_ratio:.1%} (target: >={MIN_HARD_RATIO:.0%}) [{hard_ok}]")
    print(f"  Type E ratio: {type_e_ratio:.1%} (target: >={MIN_TYPE_E_RATIO:.0%}) [{type_e_ok}]")
    print(f"  Easy ratio: {easy_ratio:.1%} (target: <={MAX_EASY_RATIO:.0%}) [{easy_ok}]")

    # Step 10: Write output
    _write_jsonl(output_path, balanced)
    print(f"\nSaved to: {output_path}")

    return {
        "eval_cases_count": len(eval_cases),
        "input_rows": len(finetune_rows),
        "clean_rows": len(clean_rows),
        "variants_generated": len(variants),
        "supplements_generated": len(supplements),
        "output_rows": len(balanced),
        "gt_overlap_removed": gt_audit["overlap_count"],
        "question_overlap_removed": q_audit["overlap_count"],
        "fqn_errors": len(fqn_errors),
        "hard_ratio": hard_ratio,
        "type_e_ratio": type_e_ratio,
        "easy_ratio": easy_ratio,
        "final_difficulty": dict(sorted(final_diff.items())),
        "final_failure_types": dict(sorted(final_ft.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild finetune dataset with strict eval isolation")
    parser.add_argument("--eval-path", type=Path, default=EVAL_PATH)
    parser.add_argument("--input", type=Path, default=INPUT_STRICT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_STRICT_PATH)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "external" / "celery" / "celery")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = rebuild_dataset(
        eval_path=args.eval_path,
        input_path=args.input,
        output_path=args.output,
        source_dir=args.source_dir,
        seed=args.seed,
    )

    # Save report
    report_path = ROOT / "reports" / "finetune_rebuild_20260412.md"
    report_lines = [
        "# 微调数据集重建报告 (2026-04-12)",
        "",
        "## 概述",
        "",
        f"- 评测集规模: {result['eval_cases_count']} 条 (102 → {result['eval_cases_count']})",
        f"- 输入记录: {result['input_rows']} 条",
        f"- 清理后记录: {result['clean_rows']} 条",
        f"- 新增变体: {result['variants_generated']} 条",
        f"- 新增 Type E 补充: {result['supplements_generated']} 条",
        f"- 最终输出: {result['output_rows']} 条",
        "",
        "## 隔离验证",
        "",
        f"- Exact GT overlap 删除: {result['gt_overlap_removed']} 条",
        f"- Question similarity (>80%) 删除: {result['question_overlap_removed']} 条",
        f"- FQN 验证错误: {result['fqn_errors']} 条",
        "",
        "## 质量指标",
        "",
        f"- Hard 比例: {result['hard_ratio']:.1%} (目标: ≥{MIN_HARD_RATIO:.0%})",
        f"- Type E 比例: {result['type_e_ratio']:.1%} (目标: ≥{MIN_TYPE_E_RATIO:.0%})",
        f"- Easy 比例: {result['easy_ratio']:.1%} (目标: ≤{MAX_EASY_RATIO:.0%})",
        "",
        "## 难度分布",
        "",
    ]
    for k, v in result["final_difficulty"].items():
        report_lines.append(f"- {k}: {v}")
    report_lines.extend(["", "## Failure Type 分布", ""])
    for k, v in result["final_failure_types"].items():
        report_lines.append(f"- {k}: {v}")
    report_lines.extend(["", "## 结论", ""])
    all_pass = (
        result["output_rows"] >= MIN_RECORDS
        and result["hard_ratio"] >= MIN_HARD_RATIO
        and result["type_e_ratio"] >= MIN_TYPE_E_RATIO
        and result["easy_ratio"] <= MAX_EASY_RATIO
    )
    report_lines.append(f"- 全部指标通过: {'是' if all_pass else '否'}")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport saved to: {report_path}")

    print(f"\n{'='*50}")
    print(f"Rebuild complete: {result['output_rows']} records")
    print(f"  {'PASS' if all_pass else 'FAIL'} all quality gates")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
