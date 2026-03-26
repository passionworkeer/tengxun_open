#!/usr/bin/env python3
"""
Merge all batch_type_*.jsonl files into finetune_dataset_500.jsonl.
Only records passing validate_record() are included.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

# Add finetune dir to path so we can import data_guard
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR / "finetune"))
from data_guard import validate_record


def main() -> int:
    data_dir = SCRIPT_DIR / "data"
    output_path = data_dir / "finetune_dataset_500.jsonl"

    # Find all batch files
    batch_files = sorted(data_dir.glob("batch_type_*.jsonl"))

    if not batch_files:
        print("ERROR: No batch_type_*.jsonl files found in data/")
        return 1

    print(f"Found {len(batch_files)} batch files:")
    for f in batch_files:
        print(f"  - {f.name}")
    print()

    # Statistics tracking
    total_seen = 0
    total_valid = 0
    total_invalid = 0
    difficulty_counter: Counter[str] = Counter()
    failure_type_counter: Counter[str] = Counter()
    invalid_reasons: Counter[str] = Counter()
    valid_records: list[dict] = []

    with output_path.open("w", encoding="utf-8") as out_f:
        for batch_file in batch_files:
            print(f"Processing {batch_file.name}...")
            file_valid = 0
            file_invalid = 0

            for line_num, line in enumerate(
                batch_file.read_text(encoding="utf-8-sig").splitlines(), start=1
            ):
                if not line.strip():
                    continue

                total_seen += 1

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    total_invalid += 1
                    file_invalid += 1
                    invalid_reasons[f"json_error: {exc.msg}"] += 1
                    continue

                errors = validate_record(record)
                if errors:
                    total_invalid += 1
                    file_invalid += 1
                    for err in errors:
                        invalid_reasons[err] += 1
                    continue

                # Record is valid - add to output
                valid_records.append(record)
                difficulty = record.get("difficulty", "unknown")
                difficulty_counter[difficulty] += 1
                total_valid += 1
                file_valid += 1

                failure_type = record.get("failure_type")
                if failure_type:
                    failure_type_counter[failure_type] += 1

                # Write to output file
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

            print(f"  valid: {file_valid}, invalid: {file_invalid}")

    # Print summary
    print("\n" + "=" * 60)
    print("MERGE SUMMARY")
    print("=" * 60)
    print(f"Total seen:      {total_seen}")
    print(f"Total valid:     {total_valid}")
    print(f"Total invalid:   {total_invalid}")
    print(f"Valid rate:      {round(total_valid/total_seen*100, 2) if total_seen else 0}%")
    print()

    print("Difficulty distribution:")
    for diff in ("easy", "medium", "hard"):
        count = difficulty_counter.get(diff, 0)
        pct = round(count / total_valid * 100, 2) if total_valid else 0
        print(f"  {diff}: {count} ({pct}%)")
    print()

    hard_count = difficulty_counter.get("hard", 0)
    hard_ratio = round(hard_count / total_valid, 4) if total_valid else 0.0
    print(f"Hard ratio: {hard_ratio}")
    print(f"Hard ratio >= 0.3? {hard_ratio >= 0.3}")
    print()

    if failure_type_counter:
        print("Failure type distribution:")
        for ft, count in sorted(failure_type_counter.items()):
            print(f"  {ft}: {count}")
        print()

    # Top invalid reasons
    if invalid_reasons:
        print("Top invalid reasons:")
        for reason, count in invalid_reasons.most_common(10):
            print(f"  [{count:4d}] {reason}")
        print()

    # Gate check
    print("=" * 60)
    print("GATE CHECK")
    print("=" * 60)
    min_records = 500
    min_hard_ratio = 0.3
    gate_passed = True

    if total_valid < min_records:
        print(f"[FAIL] Records: {total_valid} < {min_records}")
        gate_passed = False
    else:
        print(f"[PASS] Records: {total_valid} >= {min_records}")

    if hard_ratio < min_hard_ratio:
        print(f"[FAIL] Hard ratio: {hard_ratio} < {min_hard_ratio}")
        gate_passed = False
    else:
        print(f"[PASS] Hard ratio: {hard_ratio} >= {min_hard_ratio}")

    print()
    if gate_passed:
        print("RESULT: ALL GATES PASSED")
        return 0
    else:
        print("RESULT: GATES FAILED - see above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
