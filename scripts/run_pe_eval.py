"""
PE（Prompt Engineering）四维度逐步叠加评测脚本

严格单变量实验：
  Baseline → +System Prompt → +CoT → +Few-shot → +Post-processing

每步独立记录 Easy / Medium / Hard / Avg F1。

用法：
  python -m scripts.run_pe_eval --api-key <api-key>
  python -m scripts.run_pe_eval --api-key <api-key> --max-cases 5  # 调试用
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI

from evaluation.baseline import EvalCase, load_eval_cases
from evaluation.metrics import compute_layered_dependency_metrics
from pe.post_processor import parse_model_output
from pe.prompt_templates_v2 import (
    SYSTEM_PROMPT,
    COT_TEMPLATE,
    OUTPUT_INSTRUCTIONS,
    build_messages,
    select_few_shot_examples,
    format_few_shot_example,
)

API_BASE_URL = "https://ai.td.ee/v1"
DEFAULT_MODEL = "gpt-5.4"
DATA_PATH = Path("data/eval_cases.json")
OUTPUT_DIR = Path("results/pe_eval")


# ── 5 种 prompt 变体 ──────────────────────────────────────────────


def build_baseline_messages(case: EvalCase) -> list[dict[str, str]]:
    """Baseline：无 PE，仅 user 消息 + 输出格式要求"""
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}}'
    )
    return [{"role": "user", "content": "\n\n".join(parts)}]


def build_system_prompt_messages(case: EvalCase) -> list[dict[str, str]]:
    """+System Prompt：角色定义 + 格式约束"""
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}}'
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def build_cot_messages(case: EvalCase) -> list[dict[str, str]]:
    """+CoT：System Prompt + 推理引导"""
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}}'
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "system", "content": COT_TEMPLATE.strip()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def build_fewshot_messages(case: EvalCase) -> list[dict[str, str]]:
    """+Few-shot：System Prompt + CoT + 6 条动态选择的示例"""
    return build_messages(
        question=case.question,
        context="",
        entry_symbol=case.entry_symbol,
        entry_file=case.entry_file,
        max_examples=6,
    )


# ── 解析与评估 ────────────────────────────────────────────────────


def parse_response_v1(raw: str) -> dict[str, list[str]] | None:
    """Baseline / System Prompt / CoT 用的解析（兼容旧格式）"""
    text = raw.strip()
    if not text:
        return None
    try:
        # 尝试提取 JSON
        match = re.search(r"\{[^{]*\"ground_truth\"[^{]*\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
        else:
            data = json.loads(text)
        gt = data.get("ground_truth", {})
        return {
            "direct_deps": gt.get("direct_deps", []),
            "indirect_deps": gt.get("indirect_deps", []),
            "implicit_deps": gt.get("implicit_deps", []),
        }
    except (json.JSONDecodeError, AttributeError, KeyError):
        return None


def parse_response_with_postprocess(
    raw: str, case: EvalCase
) -> dict[str, list[str]] | None:
    """+Post-processing：用 post_processor 做格式净化后再解析"""
    text = raw.strip()
    if not text:
        return None
    # 先用 post_processor 提取 FQN 列表
    gold_all = (
        list(case.direct_gold_fqns)
        + list(case.indirect_gold_fqns)
        + list(case.implicit_gold_fqns)
    )
    cleaned = parse_model_output(text, allowed_fqns=None)
    if not cleaned:
        return parse_response_v1(raw)
    # 将清理后的 FQN 放回 ground_truth 结构
    original = parse_response_v1(raw)
    if original:
        # 用 cleaned 中的 FQN 替换原始解析结果中各字段
        # 由于 post_processor 不区分 dep 类型，统一放到 direct_deps
        original["direct_deps"] = cleaned
        original["indirect_deps"] = []
        original["implicit_deps"] = []
        return original
    return {"direct_deps": cleaned, "indirect_deps": [], "implicit_deps": []}


def compute_case_f1(pred: dict[str, list[str]] | None, case: EvalCase) -> float:
    return compute_case_scoring(pred, case)["union_f1"]


def build_ground_truth(case: EvalCase) -> dict[str, list[str]]:
    return {
        "direct_deps": list(case.direct_gold_fqns),
        "indirect_deps": list(case.indirect_gold_fqns),
        "implicit_deps": list(case.implicit_gold_fqns),
    }


def compute_case_scoring(
    pred: dict[str, list[str]] | None, case: EvalCase
) -> dict[str, Any]:
    scoring = compute_layered_dependency_metrics(build_ground_truth(case), pred or {})
    return {
        "union_f1": round(scoring.union.f1, 4),
        "macro_f1": round(scoring.macro_f1, 4),
        "direct_f1": round(scoring.direct.f1, 4),
        "indirect_f1": round(scoring.indirect.f1, 4),
        "implicit_f1": round(scoring.implicit.f1, 4),
        "mislayer_rate": round(scoring.mislayer_rate, 4),
        "exact_layer_match": scoring.exact_layer_match,
        "scoring": scoring.as_dict(),
    }


# ── 主评测循环 ────────────────────────────────────────────────────


@dataclass
class VariantResult:
    name: str
    cases: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        case_id: str,
        difficulty: str,
        failure_type: str,
        scoring: dict[str, Any],
        prediction: dict | None,
        raw_output: str,
    ):
        self.cases.append(
            {
                "case_id": case_id,
                "difficulty": difficulty,
                "failure_type": failure_type,
                "f1": scoring["union_f1"],
                "union_f1": scoring["union_f1"],
                "macro_f1": scoring["macro_f1"],
                "direct_f1": scoring["direct_f1"],
                "indirect_f1": scoring["indirect_f1"],
                "implicit_f1": scoring["implicit_f1"],
                "mislayer_rate": scoring["mislayer_rate"],
                "exact_layer_match": scoring["exact_layer_match"],
                "prediction": prediction,
                "strict_scoring": scoring["scoring"],
                "raw_output": raw_output,
            }
        )

    def summary(self) -> dict[str, Any]:
        def _avg(items: list[float]) -> float:
            return round(sum(items) / len(items), 4) if items else 0.0

        by_diff: dict[str, list[dict[str, Any]]] = {}
        for c in self.cases:
            by_diff.setdefault(c["difficulty"], []).append(c)

        def _diff_avg(difficulty: str, key: str) -> float:
            subset = by_diff.get(difficulty, [])
            return _avg([float(item[key]) for item in subset])

        all_union_f1 = [float(c["union_f1"]) for c in self.cases]
        all_macro_f1 = [float(c["macro_f1"]) for c in self.cases]
        all_mislayer = [float(c["mislayer_rate"]) for c in self.cases]
        return {
            "variant": self.name,
            "num_cases": len(self.cases),
            "easy_f1": _diff_avg("easy", "union_f1"),
            "medium_f1": _diff_avg("medium", "union_f1"),
            "hard_f1": _diff_avg("hard", "union_f1"),
            "avg_f1": _avg(all_union_f1),
            "avg_macro_f1": _avg(all_macro_f1),
            "avg_mislayer_rate": _avg(all_mislayer),
        }


VARIANTS = [
    ("baseline", build_baseline_messages, parse_response_v1),
    ("system_prompt", build_system_prompt_messages, parse_response_v1),
    ("cot", build_cot_messages, parse_response_v1),
    ("fewshot", build_fewshot_messages, parse_response_v1),
    ("postprocess", build_fewshot_messages, parse_response_with_postprocess),
]


def run_variant(
    variant_name: str,
    build_fn,
    parse_fn,
    cases: list[EvalCase],
    client: OpenAI,
    model: str,
    max_cases: int | None = None,
) -> VariantResult:
    result = VariantResult(name=variant_name)
    subset = cases[:max_cases] if max_cases else cases

    for i, case in enumerate(subset):
        print(
            f"  [{variant_name}] [{i + 1}/{len(subset)}] {case.case_id}...",
            end=" ",
            flush=True,
        )

        messages = build_fn(case)
        raw_output = ""
        prediction = None

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                    timeout=300,
                )
                msg = resp.choices[0].message
                raw_output = msg.content if msg and msg.content else ""
                if parse_fn == parse_response_with_postprocess:
                    prediction = parse_fn(raw_output, case)
                else:
                    prediction = parse_fn(raw_output)
                break
            except Exception as e:
                print(f"  retry {attempt + 1}: {e}", end=" ", flush=True)
                time.sleep(5)
                raw_output = str(e)

        scoring = compute_case_scoring(prediction, case)
        result.add(
            case.case_id,
            case.difficulty,
            case.failure_type,
            scoring,
            prediction,
            raw_output,
        )
        print(
            f"Union={scoring['union_f1']:.4f} Macro={scoring['macro_f1']:.4f}",
            flush=True,
        )

    return result


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="PE incremental evaluation with GPT-5.4"
    )
    parser.add_argument("--api-key", required=True, help="GPT-5.4 API key")
    parser.add_argument("--base-url", default=API_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--cases", type=Path, default=DATA_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--max-cases", type=int, default=None, help="Limit cases for testing"
    )
    parser.add_argument(
        "--variants",
        type=str,
        default="",
        help="Comma-separated variants to run, e.g. fewshot,postprocess",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Skip already-completed variants"
    )
    args = parser.parse_args()

    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.\n")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    selected_variants = None
    if args.variants.strip():
        selected_variants = {
            item.strip() for item in args.variants.split(",") if item.strip()
        }

    all_summaries = []
    for variant_name, build_fn, parse_fn in VARIANTS:
        if selected_variants is not None and variant_name not in selected_variants:
            continue
        out_file = args.output_dir / f"pe_{variant_name}.json"

        if args.resume and out_file.exists():
            print(f"=== {variant_name} === (resume: loading from {out_file})")
            existing = json.loads(out_file.read_text(encoding="utf-8"))
            vr = VariantResult(name=variant_name)
            vr.cases = existing
            summary = vr.summary()
        else:
            print(f"=== {variant_name} ===")
            vr = run_variant(
                variant_name,
                build_fn,
                parse_fn,
                cases,
                client,
                args.model,
                args.max_cases,
            )
            out_file.write_text(
                json.dumps(vr.cases, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            summary = vr.summary()

        all_summaries.append(summary)
        print(
            f"  => Easy F1={summary['easy_f1']:.4f}  Medium F1={summary['medium_f1']:.4f}  "
            f"Hard F1={summary['hard_f1']:.4f}  Avg Union F1={summary['avg_f1']:.4f}  "
            f"Avg Macro F1={summary['avg_macro_f1']:.4f}  "
            f"Avg Mislayer={summary['avg_mislayer_rate']:.4f}\n"
        )

    # 汇总表
    summary_file = args.output_dir / "pe_summary.json"
    summary_file.write_text(
        json.dumps(all_summaries, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print("PE Incremental Evaluation Summary")
    print("=" * 70)
    print(
        f"{'Variant':<18} {'Easy F1':>8} {'Medium F1':>10} {'Hard F1':>8} "
        f"{'Union':>8} {'Macro':>8} {'MisLayer':>9}"
    )
    print("-" * 80)
    for s in all_summaries:
        print(
            f"{s['variant']:<18} {s['easy_f1']:>8.4f} {s['medium_f1']:>10.4f} "
            f"{s['hard_f1']:>8.4f} {s['avg_f1']:>8.4f} "
            f"{s['avg_macro_f1']:>8.4f} {s['avg_mislayer_rate']:>9.4f}"
        )
    print("=" * 70)
    print(f"\nResults saved to {args.output_dir}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
