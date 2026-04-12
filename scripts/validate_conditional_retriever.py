"""
P0-4: End-to-end validation of rag/conditional_retriever.py

Runs classify_question_type on all 81 eval_cases and validates:
1. RAG enable/disable decision vs difficulty ground truth
2. Predicted failure_type vs ground truth
3. Overall quality metrics

Outputs: artifacts/conditional_retriever_validation.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rag.conditional_retriever import classify_question_type


def load_eval_cases() -> list[dict[str, Any]]:
    """Load and validate eval_cases.json."""
    path = PROJECT_ROOT / "data" / "eval_cases.json"
    with open(path, "r", encoding="utf-8") as f:
        cases = json.load(f)
    return cases


def normalize_ft(ft: str) -> str:
    """Normalize failure_type to 'Type X' format."""
    ft = ft.strip()
    if not ft.startswith("Type "):
        # Try to match 'type_a' -> 'Type A'
        import re
        m = re.match(r"type_([a-e])", ft, re.I)
        if m:
            idx = "abcde".index(m.group(1).lower())
            ft = f"Type {chr(65 + idx)}"  # A=65
    return ft


def run_validation() -> dict[str, Any]:
    """Run full validation on all 81 cases."""
    cases = load_eval_cases()
    results: list[dict[str, Any]] = []

    # Aggregate stats
    total = len(cases)
    rag_enabled_count = 0
    rag_disabled_count = 0

    # Match counters
    ft_match = 0  # failure_type matches
    ft_mismatch = 0
    diff_match = 0  # difficulty matches
    diff_mismatch = 0

    # RAG decision accuracy
    rag_agree = 0   # classifier agrees with ground truth (hard/medium -> rag, easy -> no rag)
    rag_disagree = 0

    # Per-type stats
    by_gt_ft: dict[str, dict] = defaultdict(lambda: {
        "total": 0,
        "rag_enabled": 0,
        "ft_correct": 0,
        "diff_correct": 0,
        "mismatches": [],
    })

    # Per-difficulty stats
    by_gt_diff: dict[str, dict] = defaultdict(lambda: {
        "total": 0,
        "rag_enabled": 0,
        "rag_disabled": 0,
    })

    for case in cases:
        case_id = case.get("case_id", "unknown")
        question = case.get("question", "")
        gt_ft = case.get("failure_type", "")
        gt_diff = case.get("difficulty", "")
        entry_file = case.get("entry_file") or case.get("source_file", "")
        entry_symbol = case.get("entry_symbol") or ""

        # Run classifier
        classification = classify_question_type(
            question=question,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            difficulty_hint="",  # No hint - pure classification
        )

        pred_rag = classification.rag_recommended
        pred_ft = classification.failure_type or ""
        pred_diff = classification.difficulty
        signals = list(classification.signals)

        # Count RAG
        if pred_rag:
            rag_enabled_count += 1
        else:
            rag_disabled_count += 1

        # Difficulty match
        diff_ok = pred_diff == gt_diff
        if diff_ok:
            diff_match += 1
        else:
            diff_mismatch += 1

        # Failure type match (normalize both)
        pred_ft_norm = normalize_ft(pred_ft)
        gt_ft_norm = normalize_ft(gt_ft)
        ft_ok = pred_ft_norm == gt_ft_norm
        if ft_ok:
            ft_match += 1
        else:
            ft_mismatch += 1

        # RAG decision accuracy: hard/medium should enable RAG, easy should disable
        expected_rag = gt_diff in ("hard", "medium")
        rag_agrees = pred_rag == expected_rag
        if rag_agrees:
            rag_agree += 1
        else:
            rag_disagree += 1

        # Per-group stats
        by_gt_ft[gt_ft_norm]["total"] += 1
        if pred_rag:
            by_gt_ft[gt_ft_norm]["rag_enabled"] += 1
        if ft_ok:
            by_gt_ft[gt_ft_norm]["ft_correct"] += 1
        if diff_ok:
            by_gt_ft[gt_ft_norm]["diff_correct"] += 1
        if not ft_ok or not diff_ok:
            by_gt_ft[gt_ft_norm]["mismatches"].append({
                "case_id": case_id,
                "gt_ft": gt_ft_norm,
                "pred_ft": pred_ft_norm,
                "gt_diff": gt_diff,
                "pred_diff": pred_diff,
                "rag_pred": pred_rag,
            })

        by_gt_diff[gt_diff]["total"] += 1
        if pred_rag:
            by_gt_diff[gt_diff]["rag_enabled"] += 1
        else:
            by_gt_diff[gt_diff]["rag_disabled"] += 1

        # Store per-case result
        results.append({
            "case_id": case_id,
            "question": question[:80] + "..." if len(question) > 80 else question,
            "gt_failure_type": gt_ft_norm,
            "pred_failure_type": pred_ft_norm,
            "gt_difficulty": gt_diff,
            "pred_difficulty": pred_diff,
            "rag_enabled": pred_rag,
            "rag_expected": expected_rag,
            "rag_correct": rag_agrees,
            "ft_correct": ft_ok,
            "diff_correct": diff_ok,
            "signals": signals[:5],  # cap for JSON size
            "reason": classification.reason,
        })

    # Build summary
    rag_enable_rate = rag_enabled_count / total * 100
    ft_accuracy = ft_match / total * 100
    diff_accuracy = diff_match / total * 100
    rag_accuracy = rag_agree / total * 100

    # Per-type accuracy
    ft_accuracy_by_type = {}
    for ft, stats in sorted(by_gt_ft.items()):
        t = stats["total"]
        ft_accuracy_by_type[ft] = {
            "total": t,
            "ft_accuracy": stats["ft_correct"] / t * 100 if t else 0,
            "diff_accuracy": stats["diff_correct"] / t * 100 if t else 0,
            "rag_enable_rate": stats["rag_enabled"] / t * 100 if t else 0,
            "mismatch_cases": stats["mismatches"],
        }

    diff_stats = {}
    for d, s in sorted(by_gt_diff.items()):
        t = s["total"]
        diff_stats[d] = {
            "total": t,
            "rag_enabled": s["rag_enabled"],
            "rag_disabled": s["rag_disabled"],
            "rag_enable_rate": s["rag_enabled"] / t * 100 if t else 0,
        }

    # Key findings
    findings = []

    if rag_accuracy < 80:
        findings.append({
            "severity": "HIGH",
            "issue": "Low RAG decision accuracy",
            "detail": f"Only {rag_accuracy:.1f}% of cases have correct RAG enable/disable decisions",
            "recommendation": "Review classify_question_type thresholds for difficulty inference",
        })
    else:
        findings.append({
            "severity": "INFO",
            "issue": "RAG decision accuracy acceptable",
            "detail": f"{rag_accuracy:.1f}% accuracy ({rag_agree}/{total} correct)",
        })

    if ft_accuracy < 70:
        findings.append({
            "severity": "HIGH",
            "issue": "Low failure_type classification accuracy",
            "detail": f"Only {ft_accuracy:.1f}% of cases have correct failure_type ({ft_match}/{total})",
            "recommendation": "Patterns for Type C/D may be too weak or overlapping with Type E",
        })

    # Specific patterns
    type_e_cases = by_gt_ft.get("Type E", {})
    type_e_mismatches = type_e_cases.get("mismatches", [])
    if len(type_e_mismatches) > 5:
        findings.append({
            "severity": "MEDIUM",
            "issue": "Type E classification noisy",
            "detail": f"{len(type_e_mismatches)} Type E cases were misclassified",
            "examples": type_e_mismatches[:3],
        })

    report = {
        "summary": {
            "total_cases": total,
            "rag_enabled_count": rag_enabled_count,
            "rag_disabled_count": rag_disabled_count,
            "rag_enable_rate_pct": round(rag_enable_rate, 2),
            "ft_match_count": ft_match,
            "ft_mismatch_count": ft_mismatch,
            "ft_accuracy_pct": round(ft_accuracy, 2),
            "diff_match_count": diff_match,
            "diff_mismatch_count": diff_mismatch,
            "diff_accuracy_pct": round(diff_accuracy, 2),
            "rag_decision_agree_count": rag_agree,
            "rag_decision_disagree_count": rag_disagree,
            "rag_decision_accuracy_pct": round(rag_accuracy, 2),
        },
        "by_gt_failure_type": ft_accuracy_by_type,
        "by_gt_difficulty": diff_stats,
        "findings": findings,
        "per_case_results": results,
    }

    return report


def main():
    print("=" * 60)
    print("P0-4: conditional_retriever end-to-end validation")
    print("=" * 60)

    print("Running classify_question_type on all 81 cases...")
    report = run_validation()

    # Print summary
    s = report["summary"]
    print(f"\nTotal cases: {s['total_cases']}")
    print(f"RAG enabled: {s['rag_enabled_count']} ({s['rag_enable_rate_pct']}%)")
    print(f"RAG disabled: {s['rag_disabled_count']} ({100 - s['rag_enable_rate_pct']:.1f}%)")
    print()
    print(f"Failure type accuracy: {s['ft_accuracy_pct']}% ({s['ft_match_count']}/{s['total_cases']})")
    print(f"Difficulty accuracy:   {s['diff_accuracy_pct']}% ({s['diff_match_count']}/{s['total_cases']})")
    print(f"RAG decision accuracy: {s['rag_decision_accuracy_pct']}% ({s['rag_decision_agree_count']}/{s['total_cases']})")
    print()

    print("By failure_type:")
    for ft, stats in report["by_gt_failure_type"].items():
        print(f"  {ft}: total={stats['total']}, "
              f"ft_acc={stats['ft_accuracy']:.0f}%, "
              f"diff_acc={stats['diff_accuracy']:.0f}%, "
              f"rag_rate={stats['rag_enable_rate']:.0f}%")

    print()
    print("By difficulty:")
    for d, stats in report["by_gt_difficulty"].items():
        print(f"  {d}: total={stats['total']}, "
              f"rag_enabled={stats['rag_enabled']}, "
              f"rag_disabled={stats['rag_disabled']}")

    print()
    print("Key findings:")
    for f in report["findings"]:
        print(f"  [{f['severity']}] {f['issue']}: {f['detail']}")

    # Write output
    out_path = PROJECT_ROOT / "artifacts" / "conditional_retriever_validation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report written to: {out_path}")

    return report


if __name__ == "__main__":
    main()
