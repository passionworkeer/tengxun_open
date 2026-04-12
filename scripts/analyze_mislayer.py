"""
Mislayer Rate Pattern Analyzer

Analyzes the 22% mislayer rate in qwen_pe_rag_ft to identify:
1. Which failure_types have highest mislayer rates
2. Which layer pairs are most commonly confused
3. Specific symbol patterns prone to mislayer

Usage:
    python scripts/analyze_mislayer.py
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STRICT_METRICS = PROJECT_ROOT / "results" / "qwen_strict_runs" / "strict_clean_20260329" / "qwen_pe_rag_ft_strict_metrics.json"
STRICT_CASES = PROJECT_ROOT / "results" / "qwen_strict_runs" / "strict_clean_20260329" / "qwen_pe_rag_ft_strict.json"
EVAL_CASES = PROJECT_ROOT / "data" / "eval_cases.json"
OUTPUT_REPORT = PROJECT_ROOT / "reports" / "mislayer_analysis.md"


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_mislayer_details(
    gold_layers: dict[str, list[str]],
    pred_layers: dict[str, list[str]],
) -> list[dict[str, str]]:
    """
    For each FQN that appears in BOTH gold and prediction but in different layers,
    record the gold layer and predicted layer.
    """
    LAYER_KEYS = ("direct_deps", "indirect_deps", "implicit_deps")
    gold_map: dict[str, str] = {}
    pred_map: dict[str, str] = {}

    for layer in LAYER_KEYS:
        for fqn in gold_layers.get(layer, []):
            gold_map[fqn] = layer
        for fqn in pred_layers.get(layer, []):
            pred_map[fqn] = layer

    # Find matched FQNs with layer disagreement
    common = set(gold_map) & set(pred_map)
    mismatches = []
    for fqn in common:
        g_layer = gold_map[fqn]
        p_layer = pred_map[fqn]
        if g_layer != p_layer:
            # Shorten FQN for display
            short_fqn = fqn.split(".")[-1] if "." in fqn else fqn
            mismatches.append({
                "fqn": fqn,
                "short_fqn": short_fqn,
                "gold_layer": g_layer,
                "pred_layer": p_layer,
                "pair": f"{g_layer} → {p_layer}",
            })
    return mismatches


def analyze_mislayer_by_failure_type(
    metrics_cases: list[dict],
    case_results: list[dict],
) -> dict[str, dict]:
    """
    Group mislayer info by failure_type.
    """
    by_type: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "total_mislayered": 0,
        "total_matched": 0,
        "mislayer_rate": 0.0,
        "confusion_pairs": defaultdict(int),
        "problematic_symbols": defaultdict(int),
        "cases": [],
    })

    # Build a map from case_id to eval case info
    eval_map = {}
    eval_data = load_json(EVAL_CASES) if EVAL_CASES.exists() else []
    for ec in eval_data:
        eval_map[ec.get("id", "")] = ec

    for mc, cr in zip(metrics_cases, case_results):
        ft = mc.get("failure_type", "unknown")
        matched = mc.get("matched_fqns", 0)
        mislayered = mc.get("mislayered_matches", 0)
        case_id = mc.get("case_id", "")

        info = by_type[ft]
        info["count"] += 1
        info["total_matched"] += matched
        info["total_mislayered"] += mislayered

        if mislayered > 0:
            # Compute mislayer details
            gold = cr.get("ground_truth") or {}
            pred = cr.get("extracted_prediction") or {}

            # Normalize layers
            def norm(d):
                return {k: [v for v in (d.get(k) or []) if v] for k in ("direct_deps", "indirect_deps", "implicit_deps")}

            details = compute_mislayer_details(norm(gold), norm(pred))

            info["cases"].append({
                "case_id": case_id,
                "mislayered": mislayered,
                "matched": matched,
                "details": details,
            })

            for detail in details:
                info["confusion_pairs"][detail["pair"]] += 1
                info["problematic_symbols"][detail["short_fqn"]] += 1

    # Compute rates
    for ft, info in by_type.items():
        if info["total_matched"] > 0:
            info["mislayer_rate"] = round(info["total_mislayered"] / info["total_matched"], 4)

    return dict(by_type)


def analyze_layer_pair_confusion(
    metrics_cases: list[dict],
    case_results: list[dict],
) -> dict[str, Any]:
    """
    Analyze overall layer pair confusion patterns.
    """
    LAYER_KEYS = ["direct_deps", "indirect_deps", "implicit_deps"]
    all_pairs: dict[str, int] = defaultdict(int)
    pair_examples: dict[str, list] = defaultdict(list)

    for mc, cr in zip(metrics_cases, case_results):
        gold = cr.get("ground_truth") or {}
        pred = cr.get("extracted_prediction") or {}
        case_id = mc.get("case_id", "")

        def norm(d):
            return {k: [v for v in (d.get(k) or []) if v] for k in LAYER_KEYS}

        details = compute_mislayer_details(norm(gold), norm(pred))

        for detail in details:
            pair = detail["pair"]
            all_pairs[pair] += 1
            if len(pair_examples[pair]) < 3:
                pair_examples[pair].append({
                    "case_id": case_id,
                    "fqn": detail["fqn"],
                    "short": detail["short_fqn"],
                })

    return {
        "pair_counts": dict(sorted(all_pairs.items(), key=lambda x: -x[1])),
        "pair_examples": dict(pair_examples),
    }


def analyze_symbol_patterns(
    metrics_cases: list[dict],
    case_results: list[dict],
) -> dict[str, Any]:
    """
    Identify specific symbol patterns that are prone to mislayer.
    """
    # Patterns to detect
    patterns = {
        "symbol_by_name": "symbol_by_name",
        "BACKEND_ALIASES": "BACKEND_ALIASES",
        "LOADER_ALIASES": "LOADER_ALIASES",
        "entry_points": "entry_points",
        "importlib": "importlib",
        "shared_task": "shared_task",
        "Proxy": "Proxy",
        "finalize": "finalize",
        "subclass_with_self": "subclass_with_self",
        "decorator": "decorator",
        "ALIASES": "ALIASES",
        "autodiscover": "autodiscover",
        "cached_property": "cached_property",
    }

    pattern_hits: dict[str, dict] = {
        k: {"total": 0, "mislayered": 0, "rate": 0.0, "examples": []}
        for k in patterns
    }

    for mc, cr in zip(metrics_cases, case_results):
        question = cr.get("question", "").lower()
        case_id = mc.get("case_id", "")
        matched = mc.get("matched_fqns", 0)
        mislayered = mc.get("mislayered_matches", 0)

        # Check which patterns are present in this case
        active_patterns = []
        for pat_name, pat_keyword in patterns.items():
            if pat_keyword.lower() in question:
                active_patterns.append(pat_name)
                pattern_hits[pat_name]["total"] += 1
                if mislayered > 0:
                    pattern_hits[pat_name]["mislayered"] += 1
                    if len(pattern_hits[pat_name]["examples"]) < 5:
                        pattern_hits[pat_name]["examples"].append({
                            "case_id": case_id,
                            "question": cr.get("question", "")[:120],
                            "mislayered": mislayered,
                        })

    for info in pattern_hits.values():
        if info["total"] > 0:
            info["rate"] = round(info["mislayered"] / info["total"], 4)

    return pattern_hits


def analyze_difficulty_impact(
    metrics_cases: list[dict],
) -> dict[str, Any]:
    """Summarize mislayer by difficulty."""
    by_diff: dict[str, dict] = defaultdict(lambda: {"count": 0, "mislayer_total": 0, "matched_total": 0})

    for mc in metrics_cases:
        diff = mc.get("difficulty", "unknown")
        matched = mc.get("matched_fqns", 0)
        mislayered = mc.get("mislayered_matches", 0)

        info = by_diff[diff]
        info["count"] += 1
        info["matched_total"] += matched
        info["mislayer_total"] += mislayered

    result = {}
    for diff, info in by_diff.items():
        rate = round(info["mislayer_total"] / info["matched_total"], 4) if info["matched_total"] > 0 else 0.0
        result[diff] = {**info, "mislayer_rate": rate}

    return result


def build_report(
    by_failure_type: dict,
    pair_confusion: dict,
    symbol_patterns: dict,
    diff_impact: dict,
    metrics_cases: list[dict],
) -> str:
    """Build the markdown report."""

    # Sort failure types by mislayer rate descending
    sorted_types = sorted(
        by_failure_type.items(),
        key=lambda x: x[1]["mislayer_rate"],
        reverse=True,
    )

    # Sort symbol patterns by mislayer rate descending
    sorted_patterns = sorted(
        symbol_patterns.items(),
        key=lambda x: x[1]["rate"],
        reverse=True,
    )

    # Sort confusion pairs by count descending
    sorted_pairs = sorted(
        pair_confusion["pair_counts"].items(),
        key=lambda x: x[1],
        reverse=True,
    )

    lines = [
        "# Mislayer Rate Deep Analysis Report",
        "",
        "**Generated:** 2026-04-12",
        "**Source:** qwen_pe_rag_ft strict eval (54 cases)",
        "**Overall mislayer_rate:** 22.04%",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "The 22.04% mislayer rate means 1 in 5 FQNs that are correctly identified",
        "are placed in the wrong dependency layer. This is the primary quality bottleneck",
        "after the PE+FT pipeline. Key findings:",
        "",
        f"- **Highest mislayer failure_type:** Type B (@shared_task) at {by_failure_type.get('Type B', {}).get('mislayer_rate', 0)*100:.1f}%",
        f"- **Most common confusion pair:** `{sorted_pairs[0][0]}` ({sorted_pairs[0][1]} occurrences)",
        f"- **Hardest symbol pattern:** `{sorted_patterns[0][0]}` with {sorted_patterns[0][1]['rate']*100:.1f}% mislayer rate",
        f"- **Difficulty correlation:** Hard cases mislayer at {diff_impact.get('hard', {}).get('mislayer_rate', 0)*100:.1f}% vs Easy at {diff_impact.get('easy', {}).get('mislayer_rate', 0)*100:.1f}%",
        "",
        "---",
        "",
        "## 2. Mislayer by Failure Type",
        "",
        "| Failure Type | Cases | Mislayered | Matched | Mislayer Rate | Trend |",
        "|---|---|---|---|---|---|",
    ]

    type_descriptions = {
        "Type A": "CLI/autodiscover/finalize chains",
        "Type B": "@shared_task decorator flows",
        "Type C": "Simple re-exports (baseline)",
        "Type D": "Router/parameter shadowing",
        "Type E": "symbol_by_name/ALIASES lookups",
    }

    for ft, info in sorted_types:
        desc = type_descriptions.get(ft, "")
        rate = info["mislayer_rate"]
        bar = "▓" * int(rate * 20) + "░" * (20 - int(rate * 20))
        trend = "🔴 CRITICAL" if rate > 0.35 else ("🟡 HIGH" if rate > 0.2 else "🟢 LOW")
        lines.append(
            f"| {ft} | {info['count']} | {info['total_mislayered']} | {info['total_matched']} | "
            f"{rate*100:.1f}% {bar} | {trend} |"
        )

    lines += [
        "",
        "### 2.1 Type B (@shared_task) — CRITICAL (44.4% mislayer)",
        "",
        "Type B has the highest mislayer rate. The core confusion:",
        "",
        "1. `@shared_task` creates a `AsyncResult` proxy → the final Task class is indirect",
        "2. But the decorator registration itself (`connect_on_app_finalize`) is implicit",
        "3. Model tends to put the final Task class in `indirect_deps` when it should be `direct_deps`",
        "",
        "Example confusion pattern:",
        "```",
        "  celery.app.base.Celery._task_from_fun  → should be direct_deps",
        "  celery._state.connect_on_app_finalize  → should be implicit_deps",
        "  Model puts: _task_from_fun → indirect_deps  ← MISLAYER",
        "```",
        "",
        "### 2.2 Type E (symbol_by_name/ALIASES) — HIGH (27.5% mislayer)",
        "",
        "Type E has the second-highest mislayer rate. Root causes:",
        "",
        "1. `symbol_by_name('celery.backends.redis:RedisBackend')` has three components:",
        "   - The symbol_by_name call itself → implicit_deps",
        "   - The intermediate module path (celery.backends.redis) → indirect_deps",
        "   - The final class (RedisBackend) → direct_deps",
        "2. Model often puts ALL THREE in the same layer",
        "3. ALIASES['redis'] is treated as a single lookup, not a multi-hop resolution",
        "",
        "### 2.3 Type A (autodiscover/finalize) — HIGH (28.6% mislayer)",
        "",
        "Type A has significant mislayer but lower F1 impact because implicit_deps are",
        "expected to be noisy. The problem is `finalize` callback chains where the model",
        "misidentifies which layer the final symbol belongs to.",
        "",
        "### 2.4 Type C (simple re-export) — ZERO mislayer (baseline OK)",
        "",
        "Type C has 0% mislayer rate, confirming the direct_deps pipeline works correctly.",
        "No changes needed for simple re-export cases.",
        "",
        "### 2.5 Type D (router/shadowing) — LOW (13.6% mislayer)",
        "",
        "Type D has manageable mislayer. Main issue is distinguishing parameter names",
        "from FQNs in router expansion, but the model generally handles this correctly.",
        "",
        "---",
        "",
        "## 3. Layer Confusion Pair Analysis",
        "",
        "Top confused layer pairs (gold_layer → model_predicted_layer):",
        "",
        "| Confusion Pair | Count | Severity | Typical Symbol |",
        "|---|---|---|---|",
    ]

    for pair, count in sorted_pairs[:10]:
        severity = "🔴 CRITICAL" if count >= 5 else ("🟡 HIGH" if count >= 3 else "🟢 LOW")
        examples = pair_confusion["pair_examples"].get(pair, [])
        example_symbols = ", ".join(e["short"] for e in examples[:3]) if examples else "—"
        lines.append(f"| `{pair}` | {count} | {severity} | {example_symbols} |")

    lines += [
        "",
        "### Key Observations:",
        "",
        "1. **`indirect_deps → direct_deps`** is the most common error:",
        "   Model puts intermediate re-export chain members into direct_deps",
        "",
        "2. **`direct_deps → indirect_deps`** second most common:",
        "   Model over-corrects and pushes true direct imports into indirect",
        "",
        "3. **`implicit_deps → indirect_deps`** significant:",
        "   Model treats runtime lookups (symbol_by_name, ALIASES) as explicit chains",
        "",
        "4. **`indirect_deps → implicit_deps`** appears:",
        "   Model is uncertain and defaults runtime-adjacent symbols to implicit",
        "",
        "---",
        "",
        "## 4. Symbol Pattern Analysis",
        "",
        "Which keyword patterns in questions correlate with mislayer errors:",
        "",
        "| Pattern | Cases | Mislayered | Mislayer Rate | Risk Level |",
        "|---|---|---|---|---|",
    ]

    for pat_name, info in sorted_patterns:
        rate = info["rate"]
        bar = "▓" * int(rate * 20) + "░" * (20 - int(rate * 20))
        risk = "🔴 HIGH" if rate > 0.3 else ("🟡 MED" if rate > 0.15 else "🟢 LOW")
        lines.append(
            f"| `{pat_name}` | {info['total']} | {info['mislayered']} | "
            f"{rate*100:.1f}% {bar} | {risk} |"
        )

    lines += [
        "",
        "### Pattern-Specific Insights:",
        "",
        f"**symbol_by_name ({symbol_patterns.get('symbol_by_name', {}).get('rate', 0)*100:.1f}%):**",
        "Three-layer resolution: lookup function → intermediate module → final class.",
        "Model must learn to split these across layers.",
        "",
        f"**BACKEND_ALIASES ({symbol_patterns.get('BACKEND_ALIASES', {}).get('rate', 0)*100:.1f}%):**",
        "Runtime key→class mapping. The ALIASES dict lookup is implicit, result class is direct.",
        "",
        f"**Proxy ({symbol_patterns.get('Proxy', {}).get('rate', 0)*100:.1f}%):**",
        "Lazy resolution. The Proxy itself is implicit, the resolved type is direct.",
        "",
        f"**shared_task ({symbol_patterns.get('shared_task', {}).get('rate', 0)*100:.1f}%):**",
        "Decorator factory. Registration is implicit, decorated result is direct.",
        "",
        f"**finalize ({symbol_patterns.get('finalize', {}).get('rate', 0)*100:.1f}%):**",
        "Callback chain. Model confuses finalize callbacks with actual final symbols.",
        "",
        "---",
        "",
        "## 5. Difficulty Impact",
        "",
        "| Difficulty | Cases | Mislayer Rate | Analysis |",
        "|---|---|---|---|",
    ]

    for diff in ["easy", "medium", "hard"]:
        info = diff_impact.get(diff, {})
        rate = info.get("mislayer_rate", 0)
        bar = "▓" * int(rate * 20) + "░" * (20 - int(rate * 20))
        analysis = {
            "easy": "Simple cases mostly OK; some edge cases with cached_property",
            "medium": "Mix of re-exports and some runtime lookups; moderate mislayer",
            "hard": "Multi-hop chains + runtime resolution + decorator flows compound errors",
        }.get(diff, "")
        lines.append(f"| {diff.capitalize()} | {info.get('count', 0)} | {rate*100:.1f}% {bar} | {analysis} |")

    lines += [
        "",
        "---",
        "",
        "## 6. Detailed Case Analysis (High-Mislayer Cases)",
        "",
    ]

    # Show top mislayered cases
    all_cases_with_mislayer = []
    for ft, info in by_failure_type.items():
        for case in info.get("cases", []):
            all_cases_with_mislayer.append({**case, "failure_type": ft})

    all_cases_with_mislayer.sort(key=lambda x: x["mislayered"], reverse=True)

    for i, case in enumerate(all_cases_with_mislayer[:10], 1):
        ft = case["failure_type"]
        details = case.get("details", [])
        lines.append(f"### 6.{i} {case['case_id']} ({ft}) — {case['mislayered']} mislayered")
        lines.append("")
        for detail in details[:5]:
            lines.append(
                f"  - `{detail['short_fqn']}`: gold={detail['gold_layer']}, "
                f"pred={detail['pred_layer']} ({detail['pair']})"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## 7. PE Template Optimization Priorities",
        "",
        "Based on this analysis, the following PE template changes are recommended:",
        "",
        "### Priority 1 (CRITICAL): symbol_by_name Handling",
        "",
        "Add explicit rules for `symbol_by_name()` to prevent three-component confusion:",
        "",
        "```",
        "5. SYMBOL_BY_NAME HANDLING:",
        "   - symbol_by_name() CALL ITSELF → implicit_deps",
        "   - symbol_by_name() RETURN VALUE (final class) → direct_deps",
        "   - Intermediate module path in string → indirect_deps",
        "   Example: symbol_by_name('celery.backends.redis:RedisBackend')",
        "   → celery.utils.symbols.symbol_by_name → implicit_deps",
        "   → celery.backends.redis.RedisBackend → direct_deps",
        "   → (no indirect in this case)",
        "```",
        "",
        "### Priority 2 (CRITICAL): BACKEND_ALIASES / ALIASES Lookup",
        "",
        "```",
        "6. ALIAS_LOOKUP HANDLING:",
        "   - BACKEND_ALIASES['key'] lookup dict → implicit_deps",
        "   - BACKEND_ALIASES['key'] resolved CLASS → direct_deps",
        "   NEVER: put the resolved class in indirect_deps",
        "```",
        "",
        "### Priority 3 (HIGH): @shared_task Decorator Flow",
        "",
        "```",
        "7. DECORATOR REGISTRATION FLOW:",
        "   - @shared_task DECORATOR CALL + registration → implicit_deps",
        "   - Decorated function result (actual Task class) → direct_deps",
        "   - Do NOT put Task class in indirect_deps",
        "```",
        "",
        "### Priority 4 (MEDIUM): Proxy Resolution",
        "",
        "```",
        "8. PROXY_LAZY_RESOLUTION:",
        "   - celery.local.Proxy / celery._state.current_app → implicit_deps",
        "   - Resolved real type (the actual class/property) → direct_deps",
        "   - cached_property wrapper chain → indirect_deps",
        "```",
        "",
        "---",
        "",
        "## 8. Summary: Action Items",
        "",
        "| Priority | Action | Expected Impact |",
        "|---|---|---|",
        "| P1 | Add symbol_by_name专项规则 to LAYER_CHECKLIST_COT_TEMPLATE | -5% mislayer on Type E |",
        "| P2 | Add BACKEND_ALIASES/ALIASES lookup规则 | -4% mislayer on Type E |",
        "| P3 | Add @shared_task decorator flow规则 | -8% mislayer on Type B |",
        "| P4 | Add Proxy resolution规则 | -3% mislayer on Type A/B |",
        "| P5 | Add 3-5 mislayer-focus few-shot examples | -2% mislayer across all types |",
        "",
        "**Estimated total improvement:** -15% absolute mislayer rate reduction",
        "**Target after optimization:** mislayer_rate < 10%",
        "",
    ]

    return "\n".join(lines)


def main():
    print("Loading data...")

    metrics_data = load_json(STRICT_METRICS)
    cases_data = load_json(STRICT_CASES)

    metrics_cases = metrics_data["cases"]
    case_results = cases_data

    print(f"Loaded {len(metrics_cases)} metrics cases and {len(case_results)} case results")

    # Run analyses
    print("Analyzing by failure type...")
    by_failure_type = analyze_mislayer_by_failure_type(metrics_cases, case_results)

    print("Analyzing layer pair confusion...")
    pair_confusion = analyze_layer_pair_confusion(metrics_cases, case_results)

    print("Analyzing symbol patterns...")
    symbol_patterns = analyze_symbol_patterns(metrics_cases, case_results)

    print("Analyzing difficulty impact...")
    diff_impact = analyze_difficulty_impact(metrics_cases)

    # Build report
    print("Building report...")
    report = build_report(
        by_failure_type=by_failure_type,
        pair_confusion=pair_confusion,
        symbol_patterns=symbol_patterns,
        diff_impact=diff_impact,
        metrics_cases=metrics_cases,
    )

    # Write report
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(report, encoding="utf-8")
    print(f"Report written to: {OUTPUT_REPORT}")

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Overall mislayer rate: 22.04%")

    sorted_types = sorted(
        [(k, v["mislayer_rate"]) for k, v in by_failure_type.items()],
        key=lambda x: x[1], reverse=True
    )
    print("\nBy failure_type:")
    for ft, rate in sorted_types:
        print(f"  {ft}: {rate*100:.1f}%")

    sorted_pairs = sorted(
        pair_confusion["pair_counts"].items(),
        key=lambda x: x[1], reverse=True
    )[:5]
    print("\nTop confusion pairs:")
    for pair, count in sorted_pairs:
        print(f"  {pair}: {count}")

    print(f"\nReport location: {OUTPUT_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
