from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
REQUIRED_FIELDS = {"question", "context", "answers", "difficulty"}


def validate_record(record: dict[str, object]) -> list[str]:
    errors: list[str] = []

    missing = REQUIRED_FIELDS - set(record)
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")

    answers = record.get("answers", [])
    if not isinstance(answers, list) or not answers:
        errors.append("answers must be a non-empty list")
    else:
        invalid = [item for item in answers if not isinstance(item, str) or not FQN_PATTERN.fullmatch(item)]
        if invalid:
            errors.append(f"invalid answers: {invalid}")

    return errors


def validate_jsonl(path: Path) -> tuple[int, int]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    valid = 0
    invalid = 0

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        errors = validate_record(record)
        if errors:
            invalid += 1
            print(f"line {line_number}: {'; '.join(errors)}")
        else:
            valid += 1

    return valid, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate finetune dataset JSONL.")
    parser.add_argument("dataset", type=Path, help="Path to finetune_dataset.jsonl")
    args = parser.parse_args()

    valid, invalid = validate_jsonl(args.dataset)
    print(
        json.dumps(
            {"valid_records": valid, "invalid_records": invalid},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if invalid == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

