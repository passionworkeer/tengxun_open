#!/usr/bin/env python3
"""
完整评测脚本: 运行所有策略组合，输出对比表格

策略列表:
  1. GPT-5.4 Baseline         → gpt_baseline
  2. GPT-5.4 PE              → pe_postprocess (fewshot + postprocess)
  3. GPT-5.4 PE + RAG        → gpt_rag_e2e (如果已运行)
  4. GLM-5 Baseline          → glm_baseline
  5. Qwen Baseline           → qwen_baseline_recovered
  6. Qwen PE                 → qwen_pe_only
  7. Qwen RAG                → qwen_rag_only
  8. Qwen PE + RAG           → qwen_pe_rag
  9. Qwen PE + FT           → qwen_pe_ft
 10. Qwen PE + RAG + FT     → qwen_pe_rag_ft

用法:
    # 仅生成对比表格（基于已有结果）
    python scripts/run_full_benchmark.py

    # 运行全部评测
    python scripts/run_full_benchmark.py --run-all --api-key <key>

    # 运行特定策略
    python scripts/run_full_benchmark.py --strategies gpt_baseline qwen_pe_rag_ft

输出:
    reports/full_benchmark_results.md   - 对比表格
    reports/full_benchmark_results.json - 结构化结果
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

RESULTS_DIR = _ROOT / "results"
REPORTS_DIR = _ROOT / "reports"
STRICT_METRICS_DIR = RESULTS_DIR / "strict_metrics_20260329"

# ─── 策略定义 ──────────────────────────────────────────────────────────────

STRATEGIES: dict[str, dict[str, Any]] = {
    # GPT 系列
    "gpt_baseline": {
        "label": "GPT-5.4 Baseline",
        "short": "GPT-B",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "gpt_baseline",
        "description": "GPT-5.4 无 PE 无 RAG",
        "requires_api": True,
        "api_type": "openai",
    },
    "gpt_pe": {
        "label": "GPT-5.4 PE",
        "short": "GPT-PE",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "pe_postprocess",
        "description": "GPT-5.4 + Fewshot + Postprocess",
        "requires_api": True,
        "api_type": "openai",
    },
    # GLM 系列
    "glm_baseline": {
        "label": "GLM-5 Baseline",
        "short": "GLM-B",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "glm_baseline",
        "description": "GLM-5 无 PE 无 RAG",
        "requires_api": True,
        "api_type": "openai",
    },
    # Qwen 系列
    "qwen_baseline": {
        "label": "Qwen Baseline",
        "short": "Qwen-B",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_baseline_recovered",
        "description": "Qwen3-9B 无 PE 无 RAG",
        "requires_api": False,
        "api_type": "vllm",
    },
    "qwen_pe": {
        "label": "Qwen PE",
        "short": "Qwen-PE",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_pe_only",
        "description": "Qwen + PE (Fewshot + Postprocess)",
        "requires_api": False,
        "api_type": "vllm",
    },
    "qwen_rag": {
        "label": "Qwen RAG",
        "short": "Qwen-R",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_rag_only",
        "description": "Qwen + RAG (无 PE)",
        "requires_api": False,
        "api_type": "vllm",
    },
    "qwen_pe_rag": {
        "label": "Qwen PE + RAG",
        "short": "Qwen-PE+R",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_pe_rag",
        "description": "Qwen + PE + RAG",
        "requires_api": False,
        "api_type": "vllm",
    },
    "qwen_pe_ft": {
        "label": "Qwen PE + FT",
        "short": "Qwen-PE+FT",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_pe_ft",
        "description": "Qwen + PE + Fine-tuned",
        "requires_api": False,
        "api_type": "vllm",
    },
    "qwen_pe_rag_ft": {
        "label": "Qwen PE + RAG + FT",
        "short": "Qwen-PE+R+FT",
        "result_path": STRICT_METRICS_DIR / "summary.json",
        "result_key": "qwen_pe_rag_ft",
        "description": "完整策略：Qwen + PE + RAG + Fine-tuned",
        "requires_api": False,
        "api_type": "vllm",
    },
}

# ─── 结果提取 ──────────────────────────────────────────────────────────────

def _safe_get(data: dict, *keys, default=None) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key, default)
        if data is None:
            return default
    return data


def extract_strategy_metrics(
    result_path: Path,
    result_key: str,
) -> dict[str, Any] | None:
    """
    从结果文件中提取指定策略的评测指标。
    支持多种格式：strict_summary, raw_list, standalone_result。
    """
    if not result_path.exists():
        return None

    try:
        data = json.load(open(result_path, encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return None

    # 格式 1: strict_metrics/summary.json (dict of strategies)
    if isinstance(data, dict) and result_key in data:
        strategy_data = data[result_key]
        summary = strategy_data.get("summary", {})
        return {
            "format": "strict_summary",
            "overall": summary.get("overall", {}),
            "by_difficulty": summary.get("by_difficulty", {}),
            "by_failure_type": summary.get("by_failure_type", {}),
            "source": str(result_path),
        }

    # 格式 2: raw list results
    if isinstance(data, list):
        return _extract_from_list(data, result_key, str(result_path))

    return None


def _extract_from_list(
    results: list[dict],
    strategy_hint: str,
    source: str,
) -> dict[str, Any] | None:
    """
    从原始结果列表计算评测指标。
    用于没有预先汇总的结果文件。
    """
    if not results:
        return None

    # 按 difficulty 分组
    by_diff: dict[str, list[dict]] = {}
    for r in results:
        diff = r.get("difficulty", "unknown")
        by_diff.setdefault(diff, []).append(r)

    def _avg_f1(items: list[dict]) -> float:
        if not items:
            return 0.0
        f1s = [r.get("f1", 0.0) for r in items if r.get("f1") is not None]
        return round(sum(f1s) / len(f1s), 4) if f1s else 0.0

    def _avg_macro_f1(items: list[dict]) -> float:
        if not items:
            return 0.0
        macros = [
            r.get("metrics", {}).get("avg_macro_f1", r.get("macro_f1", 0.0))
            for r in items
        ]
        valid = [m for m in macros if m]
        return round(sum(valid) / len(valid), 4) if valid else 0.0

    def _build_bucket(items: list[dict]) -> dict[str, Any]:
        count = len(items)
        f1s = [r.get("f1", 0.0) for r in items if r.get("f1") is not None]
        avg_f1 = round(sum(f1s) / len(f1s), 4) if f1s else 0.0
        return {
            "count": count,
            "avg_union_f1": avg_f1,
            "avg_macro_f1": _avg_macro_f1(items),
        }

    overall = _build_bucket(results)
    by_difficulty = {k: _build_bucket(v) for k, v in by_diff.items()}

    return {
        "format": "raw_list",
        "overall": overall,
        "by_difficulty": by_difficulty,
        "by_failure_type": {},
        "source": source,
    }


def _metric_row(
    metrics: dict[str, Any] | None,
    diff_key: str,
    metric: str = "avg_union_f1",
) -> str:
    """格式化单个指标单元格。"""
    if metrics is None:
        return "N/A"
    bucket = metrics.get("by_difficulty", {}).get(diff_key, {})
    if not bucket:
        return "N/A"
    val = bucket.get(metric, None)
    if val is None:
        return "N/A"
    return f"{val:.4f}"


def _overall_metric(
    metrics: dict[str, Any] | None,
    metric: str = "avg_union_f1",
) -> str:
    """格式化总体指标单元格。"""
    if metrics is None:
        return "N/A"
    val = metrics.get("overall", {}).get(metric, None)
    if val is None:
        return "N/A"
    return f"{val:.4f}"


# ─── 表格生成 ──────────────────────────────────────────────────────────────

def build_comparison_table(results: dict[str, dict[str, Any]]) -> str:
    """
    生成 Markdown 对比表格。

    结构:
    | Strategy | Easy | Medium | Hard | Overall | Δ vs Baseline |
    """
    lines: list[str] = [
        "# 完整评测对比表格",
        "",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"评测数据集: `data/eval_cases.json` (84 cases: 15 Easy, 19 Medium, 20 Hard, 30 Type A/B/C/D/E)",
        "",
        "## Union F1 Score (Primary Metric)",
        "",
        "| Strategy | Description | Easy | Medium | Hard | **Overall** | Δ Baseline | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]

    # 找 baseline
    baseline_key = "qwen_baseline"
    baseline_metrics = results.get(baseline_key, {}).get("metrics")
    baseline_overall = 0.0
    if baseline_metrics:
        baseline_overall = baseline_metrics.get("overall", {}).get("avg_union_f1", 0.0)

    # 按 Overall F1 降序排序
    def _overall(m: dict[str, Any] | None) -> float:
        if m is None:
            return -1.0
        return m.get("overall", {}).get("avg_union_f1", -1.0)

    sorted_strategies = sorted(
        results.items(),
        key=lambda x: _overall(x[1].get("metrics")),
        reverse=True,
    )

    for strategy_key, result in sorted_strategies:
        info = STRATEGIES.get(strategy_key, {})
        label = info.get("label", strategy_key)
        desc = info.get("description", "")
        short = info.get("short", "")
        metrics = result.get("metrics")
        source = result.get("source", "unknown")

        overall_str = _overall_metric(metrics, "avg_union_f1")
        easy_str = _metric_row(metrics, "easy", "avg_union_f1")
        medium_str = _metric_row(metrics, "medium", "avg_union_f1")
        hard_str = _metric_row(metrics, "hard", "avg_union_f1")

        # Delta vs baseline
        if metrics and baseline_overall > 0:
            val = metrics.get("overall", {}).get("avg_union_f1", 0.0)
            delta = val - baseline_overall
            delta_str = f"{delta:+.4f}"
        else:
            delta_str = "N/A"

        # Source short name
        src_short = Path(source).name if source else "?"

        lines.append(
            f"| {label} | {desc} | {easy_str} | {medium_str} | {hard_str} | "
            f"**{overall_str}** | {delta_str} | {src_short} |"
        )

    lines.append("")
    lines.append("## Macro F1 Score (Per-Layer Quality)")
    lines.append("")
    lines.append("| Strategy | Easy | Medium | Hard | **Overall** |")
    lines.append("|---|---|---|---|---|")

    for strategy_key, result in sorted_strategies:
        info = STRATEGIES.get(strategy_key, {})
        label = info.get("label", strategy_key)
        metrics = result.get("metrics")

        overall_str = _overall_metric(metrics, "avg_macro_f1")
        easy_str = _metric_row(metrics, "easy", "avg_macro_f1")
        medium_str = _metric_row(metrics, "medium", "avg_macro_f1")
        hard_str = _metric_row(metrics, "hard", "avg_macro_f1")

        lines.append(
            f"| {label} | {easy_str} | {medium_str} | {hard_str} | **{overall_str}** |"
        )

    lines.append("")
    lines.append("## Direct Dependency F1 (Easiest Layer)")
    lines.append("")
    lines.append("| Strategy | Easy | Medium | Hard | **Overall** |")
    lines.append("|---|---|---|---|---|")

    for strategy_key, result in sorted_strategies:
        info = STRATEGIES.get(strategy_key, {})
        label = info.get("label", strategy_key)
        metrics = result.get("metrics")

        overall_str = _overall_metric(metrics, "avg_direct_f1")
        easy_str = _metric_row(metrics, "easy", "avg_direct_f1")
        medium_str = _metric_row(metrics, "medium", "avg_direct_f1")
        hard_str = _metric_row(metrics, "hard", "avg_direct_f1")

        lines.append(
            f"| {label} | {easy_str} | {medium_str} | {hard_str} | **{overall_str}** |"
        )

    lines.append("")
    lines.append("## Per-Failure-Type Breakdown (Overall Union F1)")
    lines.append("")

    # 获取所有 failure_type
    all_ft: set[str] = set()
    for result in results.values():
        m = result.get("metrics")
        if m:
            all_ft.update(m.get("by_failure_type", {}).keys())

    if all_ft:
        lines.append("| Strategy | " + " | ".join(all_ft) + " |")
        ft_header = "|---|" + "|".join(["---"] * len(all_ft)) + "|"
        lines.append(ft_header)

        for strategy_key, result in sorted_strategies:
            info = STRATEGIES.get(strategy_key, {})
            label = info.get("label", strategy_key)
            metrics = result.get("metrics")
            by_ft = {}
            if metrics:
                by_ft = metrics.get("by_failure_type", {})

            cells = []
            for ft in sorted(all_ft):
                bucket = by_ft.get(ft, {})
                val = bucket.get("avg_union_f1", None)
                cells.append(f"{val:.4f}" if val is not None else "N/A")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Mislayer Rate (Lower is Better)")
    lines.append("")
    lines.append("| Strategy | Easy | Medium | Hard | **Overall** |")
    lines.append("|---|---|---|---|---|")

    for strategy_key, result in sorted_strategies:
        info = STRATEGIES.get(strategy_key, {})
        label = info.get("label", strategy_key)
        metrics = result.get("metrics")

        def _mis(bucket: dict) -> str:
            v = bucket.get("avg_mislayer_rate", None)
            return f"{v:.1%}" if v is not None else "N/A"

        by_diff = {}
        if metrics:
            by_diff = metrics.get("by_difficulty", {})

        overall_mis = "N/A"
        if metrics:
            ov = metrics.get("overall", {}).get("avg_mislayer_rate", None)
            overall_mis = f"{ov:.1%}" if ov is not None else "N/A"

        easy_m = _mis(by_diff.get("easy", {}))
        medium_m = _mis(by_diff.get("medium", {}))
        hard_m = _mis(by_diff.get("hard", {}))

        lines.append(f"| {label} | {easy_m} | {medium_m} | {hard_m} | **{overall_mis}** |")

    lines.append("")
    lines.append("## 评测结论")
    lines.append("")
    lines.append("### 最佳策略")
    best = sorted_strategies[0]
    best_key = best[0]
    best_info = STRATEGIES.get(best_key, {})
    best_metrics = best[1].get("metrics")
    if best_metrics:
        best_overall = best_metrics.get("overall", {}).get("avg_union_f1", 0.0)
        best_macro = best_metrics.get("overall", {}).get("avg_macro_f1", 0.0)
        best_hard = best_metrics.get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0)
        lines.append(f"- **{best_info.get('label', best_key)}**: Overall={best_overall:.4f}, Macro={best_macro:.4f}, Hard={best_hard:.4f}")

    lines.append("")
    lines.append("### Hard 场景瓶颈")
    hard_ranked = sorted(
        [(k, v) for k, v in results.items() if v.get("metrics")],
        key=lambda x: x[1]["metrics"].get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0),
        reverse=True,
    )
    for strategy_key, result in hard_ranked[:3]:
        info = STRATEGIES.get(strategy_key, {})
        hard_f1 = result["metrics"].get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0)
        lines.append(f"- {info.get('label', strategy_key)}: Hard F1={hard_f1:.4f}")

    lines.append("")
    lines.append("### 下一步行动建议")
    if hard_ranked:
        worst_hard = hard_ranked[-1][1]["metrics"].get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0)
        best_hard_val = hard_ranked[0][1]["metrics"].get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0)
        if worst_hard < 0.1:
            lines.append("1. **Hard 场景严重不足**（多数策略 F1<0.1），Type E 是核心瓶颈")
            lines.append("2. 建议: 增加 RAG Type E 专项优化 + 增强微调数据覆盖")
        elif best_hard_val < 0.4:
            lines.append("1. Hard 场景有改善空间（最佳 Hard F1<0.4）")
            lines.append("2. 建议: 继续优化 RRF 权重 + DependencyPathIndexer")
        else:
            lines.append("1. Hard 场景已接近可用水平")
            lines.append("2. 建议: 端到端验证 + 扩大评测集规模")

    return "\n".join(lines)


# ─── 评测运行 ──────────────────────────────────────────────────────────────

def run_strategy(
    strategy_key: str,
    info: dict[str, Any],
    api_key: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """运行单个策略评测。"""
    print(f"\n{'='*60}")
    print(f"Strategy: {info.get('label', strategy_key)}")
    print(f"Description: {info.get('description', '')}")
    print(f"API Type: {info.get('api_type', 'N/A')}")
    print(f"Requires API: {info.get('requires_api', False)}")
    print(f"Dry run: {dry_run}")
    print("=" * 60)

    if dry_run:
        return {
            "strategy_key": strategy_key,
            "status": "skipped_dry_run",
            "metrics": None,
            "source": info.get("result_path", ""),
        }

    # 检查是否有现成结果
    result_path = info.get("result_path")
    result_key = info.get("result_key")
    if result_path and result_path.exists():
        existing = extract_strategy_metrics(result_path, result_key)
        if existing:
            return {
                "strategy_key": strategy_key,
                "status": "loaded_existing",
                "metrics": existing,
                "source": str(result_path),
            }

    # 根据策略类型运行评测
    api_type = info.get("api_type", "")
    if api_type == "openai":
        return _run_openai_eval(strategy_key, info, api_key)
    elif api_type == "vllm":
        return _run_vllm_eval(strategy_key, info)
    else:
        return {
            "strategy_key": strategy_key,
            "status": "unknown_api_type",
            "metrics": None,
            "source": "",
        }


def _run_openai_eval(
    strategy_key: str,
    info: dict[str, Any],
    api_key: str | None,
) -> dict[str, Any]:
    """运行 OpenAI API 评测（GPT/GLM）。"""
    if not api_key:
        return {
            "strategy_key": strategy_key,
            "status": "no_api_key",
            "metrics": None,
            "source": "",
        }

    # 选择评测脚本
    if "gpt" in strategy_key:
        script = _ROOT / "evaluation" / "run_gpt_eval.py"
    else:
        script = _ROOT / "evaluation" / "run_glm_eval.py"

    if not script.exists():
        return {
            "strategy_key": strategy_key,
            "status": "script_not_found",
            "metrics": None,
            "source": "",
        }

    output_path = RESULTS_DIR / f"{strategy_key}_new.json"

    print(f"Running: python {script} --api-key *** --output {output_path}")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--api-key", api_key,
                "--cases", str(_ROOT / "data" / "eval_cases.json"),
                "--output", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            # 提取指标
            if output_path.exists():
                raw = json.load(open(output_path, encoding="utf-8"))
                metrics = _extract_from_list(raw, strategy_key, str(output_path))
                return {
                    "strategy_key": strategy_key,
                    "status": "run_success",
                    "metrics": metrics,
                    "source": str(output_path),
                }
        else:
            print(f"STDOUT: {result.stdout[:500]}")
            print(f"STDERR: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("Evaluation timed out")
    except Exception as e:
        print(f"Error: {e}")

    return {
        "strategy_key": strategy_key,
        "status": "run_failed",
        "metrics": None,
        "source": "",
    }


def _run_vllm_eval(
    strategy_key: str,
    info: dict[str, Any],
) -> dict[str, Any]:
    """运行 vLLM 本地评测（Qwen）。"""
    script = _ROOT / "evaluation" / "run_qwen_eval.py"
    if not script.exists():
        return {
            "strategy_key": strategy_key,
            "status": "script_not_found",
            "metrics": None,
            "source": "",
        }

    output_path = RESULTS_DIR / f"{strategy_key}_new.json"
    print(f"Running: python {script} --output {output_path}")
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--cases", str(_ROOT / "data" / "eval_cases.json"),
                "--output", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0 and output_path.exists():
            raw = json.load(open(output_path, encoding="utf-8"))
            metrics = _extract_from_list(raw, strategy_key, str(output_path))
            return {
                "strategy_key": strategy_key,
                "status": "run_success",
                "metrics": metrics,
                "source": str(output_path),
            }
    except subprocess.TimeoutExpired:
        print("Evaluation timed out")
    except Exception as e:
        print(f"Error: {e}")

    return {
        "strategy_key": strategy_key,
        "status": "run_failed",
        "metrics": None,
        "source": "",
    }


# ─── CLI ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="完整评测对比脚本：一键运行/汇总所有策略评测结果，输出 Markdown 表格。",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=list(STRATEGIES.keys()),
        default=None,
        help="指定要评测的策略（默认全部）",
    )
    parser.add_argument(
        "--run-all",
        action="store_true",
        help="实际运行评测（默认只生成表格，基于已有结果）",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="OpenAI API Key（用于 GPT/GLM 评测）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅分析，不写入文件",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=REPORTS_DIR / "full_benchmark_results.md",
        help="Markdown 输出路径",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=REPORTS_DIR / "full_benchmark_results.json",
        help="JSON 输出路径",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    strategies_to_run = args.strategies or list(STRATEGIES.keys())

    print(f"评测策略: {', '.join(strategies_to_run)}")
    print(f"运行模式: {'实际运行' if args.run_all else '仅汇总已有结果'}")

    # ── Phase 1: 收集/运行评测结果 ────────────────────────────────────
    results: dict[str, dict[str, Any]] = {}

    for strategy_key in strategies_to_run:
        info = STRATEGIES.get(strategy_key, {})
        result = run_strategy(
            strategy_key=strategy_key,
            info=info,
            api_key=args.api_key,
            dry_run=args.dry_run,
        )
        results[strategy_key] = result

        status = result.get("status", "unknown")
        if status == "loaded_existing":
            m = result.get("metrics", {})
            overall = m.get("overall", {}) if m else {}
            f1 = overall.get("avg_union_f1", "N/A")
            print(f"  -> Loaded existing: Overall F1={f1}")
        elif status == "skipped_dry_run":
            print(f"  -> Skipped (dry run)")
        else:
            print(f"  -> {status}")

    # ── Phase 2: 生成表格 ───────────────────────────────────────────────
    table_md = build_comparison_table(results)

    if not args.dry_run:
        # 写入 Markdown
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(table_md + "\n", encoding="utf-8")
        print(f"\n表格写入: {args.output_md}")

        # 写入 JSON
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        # Convert Path objects to strings for JSON serialization
        def _to_serializable(obj):
            if isinstance(obj, Path):
                return str(obj)
            if isinstance(obj, dict):
                return {kk: _to_serializable(vv) for kk, vv in obj.items()}
            if isinstance(obj, list):
                return [_to_serializable(i) for i in obj]
            return obj

        json_output = {
            "generated_at": datetime.now().isoformat(),
            "strategies": {
                k: _to_serializable({**v, "info": _to_serializable(STRATEGIES.get(k, {}))})
                for k, v in results.items()
            },
        }
        args.output_json.write_text(
            json.dumps(json_output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON 写入: {args.output_json}")
    else:
        print("\n[DRY RUN] 文件未写入")
        print(table_md)

    # ── Phase 3: 打印摘要 ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("评测摘要")
    print("=" * 60)

    for strategy_key, result in sorted(
        results.items(),
        key=lambda x: (
            x[1].get("metrics", {}).get("overall", {}).get("avg_union_f1", 0.0)
            if x[1].get("metrics") else -1.0
        ),
        reverse=True,
    ):
        info = STRATEGIES.get(strategy_key, {})
        label = info.get("label", strategy_key)
        metrics = result.get("metrics")
        status = result.get("status", "")

        if metrics:
            overall = metrics.get("overall", {})
            f1 = overall.get("avg_union_f1", 0.0)
            macro = overall.get("avg_macro_f1", 0.0)
            hard = metrics.get("by_difficulty", {}).get("hard", {}).get("avg_union_f1", 0.0)
            print(f"  {label:30s} F1={f1:.4f} Macro={macro:.4f} Hard={hard:.4f} [{status}]")
        else:
            print(f"  {label:30s} N/A [{status}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
