from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
REQUIRED_FIELDS = {"instruction", "input", "output", "difficulty", "verified"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_FAILURE_TYPES = {"Type A", "Type B", "Type C", "Type D", "Type E"}
GROUND_TRUTH_KEYS = ("direct_deps", "indirect_deps", "implicit_deps")


@dataclass(frozen=True)
class ValidationSummary:
    valid_records: int
    invalid_records: int
    difficulty_distribution: dict[str, int]
    hard_ratio: float
    min_records: int
    min_hard_ratio: float
    gate_errors: tuple[str, ...]
    ready: bool


def _extract_ground_truth(record: dict[str, Any]) -> dict[str, Any] | None:
    ground_truth = record.get("ground_truth")
    if isinstance(ground_truth, dict):
        return ground_truth

    output = record.get("output")
    if not isinstance(output, str) or not output.strip():
        return None

    candidates: list[str] = []
    candidates.extend(match.group(1).strip() for match in JSON_FENCE_PATTERN.finditer(output))

    stripped = output.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

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


def _validate_dep_lists(ground_truth: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    total_items = 0

    for key in GROUND_TRUTH_KEYS:
        value = ground_truth.get(key)
        if not isinstance(value, list):
            errors.append(f"{key} must be a list")
            continue
        invalid = [
            item for item in value
            if not isinstance(item, str) or not FQN_PATTERN.fullmatch(item)
        ]
        if invalid:
            errors.append(f"invalid FQNs in {key}: {invalid}")
        total_items += len(value)

    if not errors and total_items == 0:
        errors.append("ground_truth must contain at least one dependency")

    return errors


def validate_record(record: dict[str, Any]) -> list[str]:
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
    if verified is True and (not isinstance(verify_method, str) or not verify_method.strip()):
        errors.append("verify_method must be a non-empty string when verified is true")

    for key in ("category", "repo_path"):
        if key in record and record[key] is not None and not isinstance(record[key], str):
            errors.append(f"{key} must be a string when present")

    ground_truth = _extract_ground_truth(record)
    if ground_truth is None:
        errors.append(
            "output must contain a JSON answer block with direct_deps / indirect_deps / implicit_deps, "
            "or the record must include a ground_truth field"
        )
    else:
        errors.extend(_validate_dep_lists(ground_truth))

    return errors


def validate_jsonl(
    path: Path,
    min_records: int = 500,
    min_hard_ratio: float = 0.3,
) -> ValidationSummary:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    valid = 0
    invalid = 0
    difficulty_counter: Counter[str] = Counter()
    hard_count = 0

    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
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
        gate_errors.append(
            f"valid_records={valid} is below min_records={min_records}"
        )
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
