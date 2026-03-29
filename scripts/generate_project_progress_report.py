#!/usr/bin/env python3
"""
生成当前项目的权威进度报告。

目标：
- 把 54-case 正式集上的当前最终交付口径收敛到一份文档
- 明确区分：当前默认 strict-clean 资产、历史正式归档资产、商业模型结果
- 避免在自动报告里夸大“历史正式线”的完成度或数据纯度
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def avg_f1_from_list(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return round(sum(float(item.get("f1", 0.0)) for item in results) / len(results), 4)


def difficulty_avg_from_list(results: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for item in results:
        buckets.setdefault(item.get("difficulty", "unknown"), []).append(
            float(item.get("f1", 0.0))
        )
    return {
        name: round(sum(scores) / len(scores), 4) if scores else 0.0
        for name, scores in sorted(buckets.items())
    }


def load_qwen_stats(path: Path) -> dict[str, Any]:
    data = load_json(path)
    return {
        "avg_f1": round(float(data["overall"]["avg_f1"]), 4),
        "easy": round(float(data["by_difficulty"]["easy"]["avg_f1"]), 4),
        "medium": round(float(data["by_difficulty"]["medium"]["avg_f1"]), 4),
        "hard": round(float(data["by_difficulty"]["hard"]["avg_f1"]), 4),
    }


def build_report_lines(root: Path) -> list[str]:
    cases = load_json(root / "data/eval_cases.json")
    strict_data_audit = load_json(root / "results/training_log_summary_20260329.json")
    gpt_results = load_json(root / "results/gpt5_eval_results.json")
    glm_results = load_json(root / "results/glm_eval_results.json")
    qwen_recovered_summary = load_json(
        root / "results/qwen_baseline_recovered_summary_20260328.json"
    )
    rag_report = load_json(root / "results/rag_google_eval_54cases_20260328.json")
    gpt_rag = load_json(root / "results/gpt_rag_e2e_54cases_20260328_summary.json")
    pe_summary = load_json(root / "results/pe_eval_54_20260328/pe_summary.json")
    pe_strict_best = load_json(
        root / "results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json"
    )
    qwen_ft = load_qwen_stats(
        root / "results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_stats.json"
    )
    qwen_pe_ft = load_qwen_stats(
        root / "results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_stats.json"
    )
    qwen_all = load_qwen_stats(
        root / "results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_stats.json"
    )
    gpt_avg = avg_f1_from_list(gpt_results)
    glm_avg = avg_f1_from_list(glm_results)
    gpt_diff = difficulty_avg_from_list(gpt_results)
    glm_diff = difficulty_avg_from_list(glm_results)
    pe_map = {row["variant"]: row for row in pe_summary}

    lines: list[str] = [
        "# 项目最终进度整理（2026-03-29）",
        "",
        "## 一句话结论",
        "",
        "- 当前默认交付口径已经切到 strict-clean：few-shot / finetune 默认资产分别是 `data/fewshot_examples_20_strict.json` 与 `data/finetune_dataset_500_strict.jsonl`。",
        "- 商业模型最强路线是 GPT-5.4 的 strict `postprocess_targeted`：`union 0.6338 / macro 0.4757 / mislayer 0.1620`。",
        "- 开源模型最强完整路线是 Qwen strict-clean `PE + RAG + FT = 0.5018`；`PE + FT = 0.3865` 是复杂度更低的备选。",
        "- 历史正式 few-shot / finetune 资产继续保留，但仅作归档对照，不再作为当前正式默认数据入口。",
        "",
        "## 数据集与资产边界",
        "",
        f"- 正式评测集：`{len(cases)}` 条，位于 `data/eval_cases.json`，全部手工标注。",
        f"- 当前默认 few-shot：`{len(load_json(root / 'data/fewshot_examples_20_strict.json'))}` 条 strict-clean 资产。",
        f"- 当前默认微调集：`{load_jsonl_count(root / 'data/finetune_dataset_500_strict.jsonl')}` 条 strict-clean 资产。",
        "- 历史正式 few-shot / finetune 仍在仓库中，但只用于演进对照与污染审计。",
        "",
        "## 基线结果（54-case 正式口径）",
        "",
        "| 模型 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 备注 |",
        "|------|---------|-----------|---------|--------|------|",
        f"| GPT-5.4 | {gpt_diff.get('easy', 0):.4f} | {gpt_diff.get('medium', 0):.4f} | {gpt_diff.get('hard', 0):.4f} | {gpt_avg:.4f} | 官方 API |",
        f"| GLM-5 | {glm_diff.get('easy', 0):.4f} | {glm_diff.get('medium', 0):.4f} | {glm_diff.get('hard', 0):.4f} | {glm_avg:.4f} | 官方 API |",
        f"| Qwen3.5-9B | {float(qwen_recovered_summary['by_difficulty']['easy']['avg_f1']):.4f} | {float(qwen_recovered_summary['by_difficulty']['medium']['avg_f1']):.4f} | {float(qwen_recovered_summary['by_difficulty']['hard']['avg_f1']):.4f} | {float(qwen_recovered_summary['overall_avg_f1']):.4f} | strict recovered baseline |",
        "",
        "## Prompt Engineering",
        "",
        "| Variant | Avg F1 | 备注 |",
        "|---------|--------|------|",
        f"| baseline | {pe_map['baseline']['avg_f1']:.4f} | GPT-5.4 正式 54-case |",
        f"| system_prompt | {pe_map['system_prompt']['avg_f1']:.4f} | GPT-5.4 正式 54-case |",
        f"| cot | {pe_map['cot']['avg_f1']:.4f} | GPT-5.4 正式 54-case |",
        f"| fewshot | {pe_map['fewshot']['avg_f1']:.4f} | GPT-5.4 正式 54-case |",
        f"| postprocess | {pe_map['postprocess']['avg_f1']:.4f} | GPT-5.4 正式 54-case |",
        f"| strict postprocess_targeted | {pe_strict_best['overall']['avg_union_f1']:.4f} | macro={pe_strict_best['overall']['avg_macro_f1']:.4f}, mislayer={pe_strict_best['overall']['avg_mislayer_rate']:.4f} |",
        "",
        "## RAG",
        "",
        f"- Google embedding 检索：Recall@5=`{rag_report['retrieval']['fused_expanded_fqns']['avg_recall_at_k']:.4f}`，MRR=`{rag_report['retrieval']['fused_expanded_fqns']['mrr']:.4f}`",
        f"- GPT 端到端：No-RAG=`{gpt_rag['summary']['overall']['avg_f1_no_rag']:.4f}` -> With-RAG=`{gpt_rag['summary']['overall']['avg_f1_with_rag']:.4f}`，Delta=`{gpt_rag['summary']['overall']['avg_delta']:+.4f}`",
        "",
        "## Qwen strict-clean FT family",
        "",
        "| Strategy | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 口径 |",
        "|----------|---------|-----------|---------|--------|------|",
        f"| FT only | {qwen_ft['easy']:.4f} | {qwen_ft['medium']:.4f} | {qwen_ft['hard']:.4f} | {qwen_ft['avg_f1']:.4f} | strict-clean 54-case |",
        f"| PE + FT | {qwen_pe_ft['easy']:.4f} | {qwen_pe_ft['medium']:.4f} | {qwen_pe_ft['hard']:.4f} | {qwen_pe_ft['avg_f1']:.4f} | strict-clean 54-case |",
        f"| PE + RAG + FT | {qwen_all['easy']:.4f} | {qwen_all['medium']:.4f} | {qwen_all['hard']:.4f} | {qwen_all['avg_f1']:.4f} | strict-clean 54-case |",
        "",
        "## 训练证据",
        "",
        f"- 当前权威训练日志：`{strict_data_audit['log_path']}`",
        f"- step-level train loss 点数：`{strict_data_audit['train_loss_points']}`",
        f"- step-level eval loss 点数：`{strict_data_audit['eval_loss_points']}`",
        f"- best eval loss：`{strict_data_audit['best_eval_loss']}`",
        f"- final eval loss：`{strict_data_audit['final_eval_loss']}`",
        f"- checkpoint：`{', '.join(str(step) for step in strict_data_audit['checkpoint_steps'])}`",
        "",
        "## 当前答辩可成立的完成度表述",
        "",
        "| 模块 | 当前状态 | 说明 |",
        "|------|----------|------|",
        "| 评测集 ≥50 条 | 完成 | 54 条、全部手工标注 |",
        "| 瓶颈诊断 | 完成 | Type A-E 已覆盖并有错误样例支撑 |",
        "| PE 四维优化 | 完成 | 正式 54-case + strict 搜索都已落盘 |",
        "| RAG 检索与端到端评估 | 完成 | Google embedding 正式结果已落盘 |",
        "| 微调数据集 ≥500 条 | 完成 | 当前默认 strict-clean 500 条；历史正式集仅归档 |",
        "| LoRA 微调 | 完成 | strict-clean 训练日志、adapter handoff、FT family 结果均已落盘 |",
        "| 完整消融矩阵 | 完成 | 当前对外交付默认使用 strict-clean FT family 结果 |",
        "",
        "## 风险与边界",
        "",
        "- 当前主评分指标仍是三层并集后的 FQN 精确匹配；严格分层判断需同时参考 strict `macro F1 / mislayer rate`。",
        "- 历史正式 few-shot / finetune 资产存在 overlap 风险，因此已经从当前默认交付链路中降级为归档对照。",
        "- strict-clean `PE + RAG + FT` 虽然总分最高，但 `mislayer` 仍高于更保守的 `PE + FT`，答辩时应明确“最强”与“最稳”不是同一件事。",
        "",
    ]
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate project progress report.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/project_progress_20260328.md"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    lines = build_report_lines(root)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
