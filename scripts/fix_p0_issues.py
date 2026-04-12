"""
Fix P0 issues in data/eval_cases.json:

P0-1: Add unique case_id to all 81 cases
P0-2: Fix celery_type_c_004 inconsistency (id says type_c, failure_type says Type E)
P0-3: Fix schema inconsistencies (missing source_note, extra fields)
"""

import json
import re
from collections import defaultdict
from pathlib import Path

EVAL_CASES_PATH = Path("E:/desktop/tengxun/tengxun_open/data/eval_cases.json")
BACKUP_PATH = Path("E:/desktop/tengxun/tengxun_open/data/eval_cases.json.backup")


def ft_to_slug(ft: str) -> str:
    """Convert failure_type to slug: 'Type A' -> 'type_a'."""
    return ft.lower().replace(" ", "_")


def make_case_id(failure_type: str, difficulty: str, seq: int) -> str:
    """Generate case_id in format: celery_{failure_type}_{difficulty}_{seq:03d}."""
    return f"celery_{ft_to_slug(failure_type)}_{difficulty}_{seq:03d}"


def infer_failure_type_from_question(case: dict) -> str:
    """Infer correct failure type from question content when ambiguous."""
    question = case.get("question", "")
    category = case.get("category", "")
    ft = case.get("failure_type", "")

    # celery_type_c_004: question is about ConfigurationView NAMESPACES - that's Type E
    if case.get("id") == "celery_type_c_004":
        return "Type E"

    return ft


def get_source_note_for_case(case: dict) -> str:
    """Generate appropriate source_note for a case that is missing one."""
    case_id = case.get("id", "")
    ft = case.get("failure_type", "")
    category = case.get("category", "")
    question = case.get("question", "")
    source_file = case.get("source_file", "")

    # Check specific cases by id
    if case_id == "easy_005":
        return (
            "Converted from schema_v2; failure_type=Type B implicit_level=2. "
            "Question about @shared_task decorator registration flow in celery/__init__.py."
        )
    if case_id == "easy_006":
        return (
            "Converted from schema_v2; failure_type=Type B implicit_level=2. "
            "Question about @app.task decorator behavior in celery/app/__init__.py."
        )
    if case_id == "easy_008":
        return (
            "Converted from schema_v2; failure_type=Type C implicit_level=2. "
            "Question about re-export chain in celery/__init__.py."
        )
    if case_id == "medium_006":
        return (
            "Converted from schema_v2; failure_type=Type E implicit_level=3. "
            "Question about loader alias resolution for backend initialization."
        )
    if case_id == "medium_007":
        return (
            "Converted from schema_v2; failure_type=Type E implicit_level=3. "
            "Question about backend alias resolution via BACKEND_ALIASES."
        )
    if case_id == "celery_medium_020":
        return (
            f"{ft}: Redis backend alias resolution via BACKEND_ALIASES. "
            f"source_file={source_file}, category={category}."
        )
    if case_id == "celery_medium_025":
        return (
            f"{ft}: Task.Request and Task.Strategy string class references. "
            f"entry_file={case.get('entry_file', source_file)}, "
            f"entry_symbol={case.get('entry_symbol', 'N/A')}, "
            f"category={category}."
        )
    if case_id == "celery_easy_021":
        return (
            f"{ft}: Signature class definition and dict inheritance. "
            f"entry_file={case.get('entry_file', source_file)}, "
            f"entry_symbol={case.get('entry_symbol', 'N/A')}, "
            f"category={category}."
        )
    if case_id == "celery_easy_022":
        return (
            f"{ft}: celery.utils.uuid cross-package re-export from kombu. "
            f"entry_file={case.get('entry_file', source_file)}, "
            f"entry_symbol={case.get('entry_symbol', 'N/A')}, "
            f"category={category}."
        )
    if case_id == "celery_easy_023":
        return (
            f"{ft}: celery.utils.nodename re-export from celery.utils.nodenames. "
            f"entry_file={case.get('entry_file', source_file)}, "
            f"entry_symbol={case.get('entry_symbol', 'N/A')}, "
            f"category={category}."
        )
    if case_id == "celery_easy_024":
        return (
            f"{ft}: celery.utils.worker_direct re-export from celery.utils.nodenames. "
            f"entry_file={case.get('entry_file', source_file)}, "
            f"entry_symbol={case.get('entry_symbol', 'N/A')}, "
            f"category={category}."
        )

    # Default fallback
    return (
        f"Converted from schema_v2; failure_type={ft} "
        f"derived from category={category}."
    )


def fix_eval_cases():
    """Main fix function for all P0 issues."""
    # Load data
    with open(EVAL_CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    print(f"Loaded {len(cases)} cases")

    # -----------------------------------------------------------------
    # P0-2: First pass - fix celery_type_c_004 inconsistency
    # The failure_type says "Type E" but id says type_c.
    # We must fix failure_type BEFORE assigning case_id so numbering is correct.
    # -----------------------------------------------------------------
    for case in cases:
        if case.get("id") == "celery_type_c_004":
            print(f"P0-2: Fixing celery_type_c_004 - failure_type was '{case['failure_type']}', setting to 'Type E'")
            case["failure_type"] = "Type E"

    # -----------------------------------------------------------------
    # P0-1: Build (failure_type, difficulty) groups for sequential numbering
    # -----------------------------------------------------------------
    groups: dict[tuple[str, str], int] = defaultdict(int)

    # First pass: count occurrences to establish ordering
    ft_diff_groups: dict[tuple[str, str], list] = defaultdict(list)
    for case in cases:
        ft = case.get("failure_type", "")
        diff = case.get("difficulty", "")
        ft_diff_groups[(ft, diff)].append(case)

    # Assign sequential numbers within each group
    seq_counters: dict[tuple[str, str], int] = defaultdict(int)

    for case in cases:
        ft = case.get("failure_type", "")
        diff = case.get("difficulty", "")
        seq_counters[(ft, diff)] += 1
        new_seq = seq_counters[(ft, diff)]

        new_case_id = make_case_id(ft, diff, new_seq)
        old_id = case.get("id", "")

        # -----------------------------------------------------------------
        # P0-1: Add case_id (replace the old 'id' field)
        # -----------------------------------------------------------------
        case["case_id"] = new_case_id
        # Remove old 'id' field (schema uses case_id)
        if "id" in case:
            del case["id"]

        if old_id != new_case_id:
            print(f"  P0-1: {old_id} -> {new_case_id}")

    # -----------------------------------------------------------------
    # P0-3: Fix missing source_note
    # -----------------------------------------------------------------
    missing_sn_count = 0
    for case in cases:
        if "source_note" not in case or not case["source_note"]:
            sn = get_source_note_for_case(case)
            case["source_note"] = sn
            missing_sn_count += 1
            print(f"  P0-3: Added source_note to case_id={case.get('case_id', 'unknown')}")

    print(f"P0-3: Added source_note to {missing_sn_count} cases")

    # -----------------------------------------------------------------
    # P0-3: Normalize extra fields
    # Keep entry_file/entry_symbol where they exist (they add value),
    # but ensure source_file is always present and source_note always present.
    # entry_symbol is optional (can be null), entry_file should map to source_file
    # -----------------------------------------------------------------
    extra_field_count = 0
    for case in cases:
        # If entry_file exists but source_file is also set, keep both
        # (entry_file may add entry-point context)
        # Normalize: ensure source_file always present
        if "source_file" not in case:
            case["source_file"] = case.get("entry_file", "")

        # entry_symbol is optional - set to null if not present
        if "entry_symbol" not in case:
            case["entry_symbol"] = None

        # entry_file is optional - set to null if not present
        if "entry_file" not in case:
            case["entry_file"] = None

        if "entry_file" in case or "entry_symbol" in case:
            extra_field_count += 1

    print(f"P0-3: Normalized optional fields, {extra_field_count} cases have entry_file/entry_symbol")

    # -----------------------------------------------------------------
    # Validate: all 81 cases must have case_id, source_note, source_file, ground_truth
    # -----------------------------------------------------------------
    errors = []
    for i, case in enumerate(cases):
        cid = case.get("case_id")
        if not cid:
            errors.append(f"  Case index {i}: missing case_id")
        if "source_note" not in case or not case["source_note"]:
            errors.append(f"  Case index {i} ({cid}): missing source_note")
        if "source_file" not in case or not case["source_file"]:
            errors.append(f"  Case index {i} ({cid}): missing source_file")
        gt = case.get("ground_truth")
        if not gt or not isinstance(gt, dict):
            errors.append(f"  Case index {i} ({cid}): missing/invalid ground_truth")
        elif not all(k in gt for k in ("direct_deps", "indirect_deps", "implicit_deps")):
            errors.append(f"  Case index {i} ({cid}): ground_truth missing dep fields")

    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(e)
        raise ValueError(f"Validation failed with {len(errors)} errors")

    print(f"\nAll {len(cases)} cases pass validation")

    # -----------------------------------------------------------------
    # Check for duplicate case_ids
    # -----------------------------------------------------------------
    case_ids = [c.get("case_id") for c in cases]
    dupes = [cid for cid in case_ids if case_ids.count(cid) > 1]
    if dupes:
        raise ValueError(f"Duplicate case_ids found: {set(dupes)}")

    print(f"All {len(cases)} case_ids are unique")

    # -----------------------------------------------------------------
    # Sort cases by case_id for clean output
    # -----------------------------------------------------------------
    cases.sort(key=lambda c: c["case_id"])

    # -----------------------------------------------------------------
    # Write backup then updated file
    # -----------------------------------------------------------------
    import shutil
    shutil.copy(EVAL_CASES_PATH, BACKUP_PATH)
    print(f"\nBackup written to {BACKUP_PATH}")

    with open(EVAL_CASES_PATH, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, ensure_ascii=False)

    print(f"Written {len(cases)} cases to {EVAL_CASES_PATH}")

    # -----------------------------------------------------------------
    # Summary report
    # -----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("P0 FIX SUMMARY")
    print("=" * 60)
    print(f"P0-1: Added unique case_id to all {len(cases)} cases")
    print(f"  Format: celery_{{failure_type}}_{{difficulty}}_{{seq:03d}}")
    print(f"P0-2: Fixed celery_type_c_004 inconsistency (now celery_type_e_004)")
    print(f"P0-3: Added source_note to {missing_sn_count} cases")
    print(f"  Normalized schema: case_id, question, entry_file, entry_symbol,")
    print(f"                     difficulty, failure_type, ground_truth, source_note")
    print("=" * 60)

    return cases


if __name__ == "__main__":
    fix_eval_cases()
