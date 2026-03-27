"""
微调数据验证模块

功能：
1. 验证微调数据集的格式完整性
2. FQN格式校验
3. FQN路径存在性验证（防止幻觉）
4. 数据集级别gate检查（数量、难度分布）

这是微调数据准备的核心防线，
确保模型学习的是真实可用的代码依赖关系。
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


# FQN格式正则
FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
# JSON代码块提取正则
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
# 必需字段
REQUIRED_FIELDS = {"instruction", "input", "output", "difficulty", "verified"}
# 有效难度等级
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
# 有效失效类型
VALID_FAILURE_TYPES = {"Type A", "Type B", "Type C", "Type D", "Type E"}
# Ground truth字段
GROUND_TRUTH_KEYS = ("direct_deps", "indirect_deps", "implicit_deps")


@dataclass(frozen=True)
class ValidationSummary:
    """
    验证结果摘要

    Attributes:
        valid_records: 有效记录数
        invalid_records: 无效记录数
        difficulty_distribution: 难度分布
        hard_ratio: 难题比例
        min_records: 最少记录数要求
        min_hard_ratio: 最少难题比例要求
        gate_errors: gate检查错误列表
        ready: 是否通过所有检查
    """

    valid_records: int
    invalid_records: int
    difficulty_distribution: dict[str, int]
    hard_ratio: float
    min_records: int
    min_hard_ratio: float
    gate_errors: tuple[str, ...]
    ready: bool


def _extract_ground_truth(record: dict[str, Any]) -> dict[str, Any] | None:
    """
    从记录中提取ground_truth

    支持两种格式：
    1. 直接在record中有ground_truth字段
    2. 在output字段的JSON中包含ground_truth

    Returns:
        ground_truth字典或None
    """
    ground_truth = record.get("ground_truth")
    if isinstance(ground_truth, dict):
        return ground_truth

    output = record.get("output")
    if not isinstance(output, str) or not output.strip():
        return None

    # 尝试从代码块中提取JSON
    candidates: list[str] = []
    candidates.extend(
        match.group(1).strip() for match in JSON_FENCE_PATTERN.finditer(output)
    )

    stripped = output.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    # 尝试找到最后一个花括号开始的内容
    start = output.rfind("{")
    if start != -1:
        candidates.append(output[start:].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        if isinstance(parsed.get("ground_truth"), dict):
            return parsed["ground_truth"]
        if all(key in parsed for key in GROUND_TRUTH_KEYS):
            return parsed
    return None


def validate_fqn(fqn: str, source_dir: Path) -> tuple[bool, str]:
    """
    验证FQN路径是否真实存在

    这是防止幻觉的关键步骤。
    支持模块级FQN和方法级FQN的多种解析方式。

    修复方法级FQN问题：
    - celery.app.base.Celery.send_task 现在能正确找到 celery/app/base.py
    - 递归尝试所有可能的模块/符号切分点
    - 支持模块级FQN（如 celery.app.defaults -> app/defaults.py）

    Args:
        fqn: 要验证的完全限定名
        source_dir: Celery源码根目录

    Returns:
        (是否有效, 原因说明)
    """
    parts = fqn.split(".")
    if len(parts) < 2:
        return False, "FQN格式错误"

    # 外部包直接放行
    if parts[0] in ("kombu", "vine", "billiard", "pydantic", "eventlet", "gevent"):
        return True, "外部包"

    # 跳过第一个 celery 前缀（因为 source_dir 已经包含了）
    if parts[0] == "celery":
        parts = parts[1:]

    if len(parts) < 1:
        return False, "FQN格式错误"

    # 核心修复：递归尝试所有可能的模块/符号切分点
    # celery.app.base.Celery.send_task
    # 可能是：
    #   文件=celery/app/base.py, 符号=Celery（类）, 方法=send_task
    #   文件=celery/app/base/Celery.py, 符号=send_task
    # 从最长的模块路径开始尝试

    for split_at in range(len(parts), 0, -1):
        module_parts = parts[:split_at]
        symbol_name = parts[split_at] if split_at < len(parts) else None

        # 如果没有符号名，只检查模块文件是否存在
        if symbol_name is None:
            # 检查 module_parts/__init__.py
            path = source_dir / Path(*module_parts) / "__init__.py"
            if path.exists():
                return True, f"模块存在: {path}"
            # 检查 module_parts.py (单层模块)
            if len(module_parts) == 1:
                path2 = source_dir / f"{module_parts[0]}.py"
                if path2.exists():
                    return True, f"模块文件: {path2.name}"
            continue

        # 尝试 module/as/path.py
        if len(module_parts) >= 2:
            path1 = source_dir / Path(*module_parts[:-1]) / f"{module_parts[-1]}.py"
        elif len(module_parts) == 1:
            path1 = source_dir / f"{module_parts[0]}.py"
        else:
            continue

        # 尝试 module/as/path/__init__.py
        path2 = source_dir / Path(*module_parts) / "__init__.py"

        for path in [path1, path2]:
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8")
                    patterns = [
                        rf"class\s+{re.escape(symbol_name)}\s*[\(:]",
                        rf"def\s+{re.escape(symbol_name)}\s*\(",
                        rf"{re.escape(symbol_name)}\s*=",
                        rf"from\s+\S+\s+import\s+.*\b{re.escape(symbol_name)}\b",
                        rf"import\s+.*\b{re.escape(symbol_name)}\b",
                    ]
                    for pattern in patterns:
                        if re.search(pattern, content):
                            return True, f"在 {path.name} 中找到 {symbol_name}"
                except Exception:
                    pass

        # 额外检查：如果 symbol_name.py 文件存在，说明这是一个模块级FQN
        # celery.app.defaults -> app/defaults.py 是一个模块
        if len(module_parts) >= 1:
            module_file_path = source_dir / Path(*module_parts) / f"{symbol_name}.py"
            if module_file_path.exists():
                return True, f"模块文件: {module_file_path.name}"

    return False, "未找到符号定义"


def validate_fqns_in_ground_truth(
    ground_truth: dict[str, Any], source_dir: Path | None = None
) -> list[str]:
    """
    验证ground_truth中的所有FQN

    Args:
        ground_truth: ground_truth字典
        source_dir: 源码目录

    Returns:
        错误列表
    """
    errors: list[str] = []

    if source_dir is None:
        source_dir = Path("external/celery/celery")

    for key in GROUND_TRUTH_KEYS:
        value = ground_truth.get(key)
        if not isinstance(value, list):
            continue

        for fqn in value:
            if not isinstance(fqn, str):
                continue
            if not FQN_PATTERN.fullmatch(fqn):
                errors.append(f"invalid FQN format: {fqn}")
                continue

            valid, reason = validate_fqn(fqn, source_dir)
            if not valid:
                errors.append(f"FQN invalid: {fqn} ({reason})")

    return errors


def _validate_dep_lists(ground_truth: dict[str, Any]) -> list[str]:
    """验证依赖列表字段的格式"""
    errors: list[str] = []
    total_items = 0

    for key in GROUND_TRUTH_KEYS:
        value = ground_truth.get(key)
        if not isinstance(value, list):
            errors.append(f"{key} must be a list")
            continue
        invalid = [
            item
            for item in value
            if not isinstance(item, str) or not FQN_PATTERN.fullmatch(item)
        ]
        if invalid:
            errors.append(f"invalid FQNs in {key}: {invalid}")
        total_items += len(value)

    if not errors and total_items == 0:
        errors.append("ground_truth must contain at least one dependency")

    return errors


def validate_record(record: dict[str, Any]) -> list[str]:
    """
    验证单条微调记录

    检查：
    - 必需字段存在
    - 字段类型正确
    - difficulty/failure_type值有效
    - ground_truth格式正确且FQN有效

    Returns:
        错误列表
    """
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(record)
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")

    for key in ("instruction", "input", "output"):
        value = record.get(key)
        if key in record and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{key} must be a non-empty string")

    difficulty = record.get("difficulty")
    if difficulty is not None and difficulty not in VALID_DIFFICULTIES:
        errors.append(f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}")

    failure_type = record.get("failure_type")
    if failure_type is not None and failure_type not in VALID_FAILURE_TYPES:
        errors.append(f"failure_type must be one of {sorted(VALID_FAILURE_TYPES)}")

    verified = record.get("verified")
    if "verified" in record and not isinstance(verified, bool):
        errors.append("verified must be a boolean")

    verify_method = record.get("verify_method")
    if verified is True and (
        not isinstance(verify_method, str) or not verify_method.strip()
    ):
        errors.append("verify_method must be a non-empty string when verified is true")

    for key in ("category", "repo_path"):
        if (
            key in record
            and record[key] is not None
            and not isinstance(record[key], str)
        ):
            errors.append(f"{key} must be a string when present")

    ground_truth = _extract_ground_truth(record)
    if ground_truth is None:
        errors.append(
            "output must contain a JSON answer block with direct_deps / indirect_deps / implicit_deps, "
            "or the record must include a ground_truth field"
        )
    else:
        errors.extend(_validate_dep_lists(ground_truth))
        errors.extend(validate_fqns_in_ground_truth(ground_truth))

    return errors


def validate_jsonl(
    path: Path,
    min_records: int = 500,
    min_hard_ratio: float = 0.3,
) -> ValidationSummary:
    """
    验证JSONL格式的微调数据集

    Args:
        path: 数据集文件路径
        min_records: 最少有效记录数要求
        min_hard_ratio: 最少难题比例要求

    Returns:
        ValidationSummary对象
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    valid = 0
    invalid = 0
    difficulty_counter: Counter[str] = Counter()
    hard_count = 0

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            invalid += 1
            print(f"line {line_number}: invalid json: {exc.msg}")
            continue

        errors = validate_record(record)
        if errors:
            invalid += 1
            print(f"line {line_number}: {'; '.join(errors)}")
            continue

        valid += 1
        difficulty = str(record["difficulty"])
        difficulty_counter[difficulty] += 1
        if difficulty == "hard":
            hard_count += 1

    hard_ratio = round(hard_count / valid, 4) if valid else 0.0
    gate_errors: list[str] = []
    if valid < min_records:
        gate_errors.append(f"valid_records={valid} is below min_records={min_records}")
    if valid == 0:
        gate_errors.append("dataset contains no valid records")
    elif hard_ratio < min_hard_ratio:
        gate_errors.append(
            f"hard_ratio={hard_ratio} is below min_hard_ratio={min_hard_ratio}"
        )

    return ValidationSummary(
        valid_records=valid,
        invalid_records=invalid,
        difficulty_distribution=dict(sorted(difficulty_counter.items())),
        hard_ratio=hard_ratio,
        min_records=min_records,
        min_hard_ratio=min_hard_ratio,
        gate_errors=tuple(gate_errors),
        ready=(invalid == 0 and not gate_errors),
    )


def main() -> int:
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Validate finetune dataset JSONL.")
    parser.add_argument("dataset", type=Path, help="Path to finetune_dataset_500.jsonl")
    parser.add_argument(
        "--min-records",
        type=int,
        default=500,
        help="Minimum number of valid records required for the gate to pass.",
    )
    parser.add_argument(
        "--min-hard-ratio",
        type=float,
        default=0.3,
        help="Minimum hard-sample ratio required for the gate to pass.",
    )
    args = parser.parse_args()

    summary = validate_jsonl(
        args.dataset,
        min_records=args.min_records,
        min_hard_ratio=args.min_hard_ratio,
    )
    print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
    return 0 if summary.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
