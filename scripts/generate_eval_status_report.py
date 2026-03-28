#!/usr/bin/env python3
"""
生成当前评测状态报告：
- GPT-5.4 正式结果
- GLM-5 当前阻塞状态
- RAG 检索结果
- 总览图
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_gpt(results: list[dict[str, Any]]) -> dict[str, Any]:
    f1s = [float(item["f1"]) for item in results]
    by_diff: dict[str, list[float]] = {"easy": [], "medium": [], "hard": []}
    for item in results:
        by_diff.setdefault(item["difficulty"], []).append(float(item["f1"]))
    return {
        "total": len(results),
        "avg_f1": sum(f1s) / len(f1s) if f1s else 0.0,
        "pass_rate": sum(1 for x in f1s if x > 0) / len(f1s) if f1s else 0.0,
        "zero_count": sum(1 for x in f1s if x == 0),
        "difficulty": {
            diff: {
                "count": len(scores),
                "avg_f1": sum(scores) / len(scores) if scores else 0.0,
            }
            for diff, scores in by_diff.items()
        },
    }


def summarize_glm(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"count": 0, "response_models": []}
    return {
        "count": len(results),
        "response_models": sorted(
            {str(item.get("response_model")) for item in results if item.get("response_model")}
        ),
        "sample_case_id": results[0].get("case_id"),
        "sample_f1": float(results[0].get("f1", 0.0)),
    }


def summarize_rag(report: dict[str, Any]) -> dict[str, Any]:
    retrieval = report["retrieval"]
    source_rows = []
    for source in ["bm25", "semantic", "graph", "fused"]:
        row = retrieval["source_breakdown"][source]
        source_rows.append(
            {
                "source": source,
                "chunk_recall": row["chunk_symbols"]["avg_recall_at_k"],
                "chunk_mrr": row["chunk_symbols"]["mrr"],
                "expanded_recall": row["expanded_fqns"]["avg_recall_at_k"],
                "expanded_mrr": row["expanded_fqns"]["mrr"],
            }
        )
    return {
        "num_cases": retrieval["num_cases"],
        "top_k": retrieval["top_k"],
        "query_mode": retrieval["setting"]["query_mode"],
        "rrf_k": retrieval["setting"]["rrf_k"],
        "fused_chunk": retrieval["fused_chunk_symbols"],
        "fused_expanded": retrieval["fused_expanded_fqns"],
        "source_rows": source_rows,
    }


def write_report(
    *,
    output_path: Path,
    gpt_path: Path,
    glm_path: Path,
    rag_path: Path,
    cache_path: Path,
    gpt_summary: dict[str, Any],
    glm_summary: dict[str, Any],
    rag_summary: dict[str, Any],
    cache_count: int,
    total_chunks: int,
) -> None:
    lines = [
        "# 评测状态报告",
        "",
        "## GPT-5.4",
        "",
        f"- 结果文件：`{gpt_path}`",
        f"- 样本数：`{gpt_summary['total']}`",
        f"- 平均 F1：`{gpt_summary['avg_f1']:.4f}`",
        f"- Pass Rate：`{gpt_summary['pass_rate'] * 100:.1f}%`",
        f"- F1=0 数量：`{gpt_summary['zero_count']}`",
        "",
        "| Difficulty | Cases | Avg F1 |",
        "|------------|-------|--------|",
    ]
    for diff in ["easy", "medium", "hard"]:
        item = gpt_summary["difficulty"][diff]
        lines.append(f"| {diff} | {item['count']} | {item['avg_f1']:.4f} |")

    lines.extend(
        [
            "",
            "## GLM-5",
            "",
            f"- 结果文件：`{glm_path}`",
            f"- 当前已落盘 case：`{glm_summary['count']}`",
            f"- 响应模型：`{', '.join(glm_summary['response_models']) or 'N/A'}`",
            f"- 已验证 sample：`{glm_summary.get('sample_case_id', 'N/A')}` / F1=`{glm_summary.get('sample_f1', 0.0):.4f}`",
            "- 状态：`2026-03-27` 当天 ModelScope 对 `ZhipuAI/GLM-5` 返回日配额耗尽，无法继续完成 54 条正式重跑。",
            "",
            "## RAG",
            "",
            f"- 检索报告：`{rag_path}`",
            f"- Embedding 缓存：`{cache_path}`",
            f"- 缓存覆盖：`{cache_count}/{total_chunks}` (`{cache_count / total_chunks * 100:.1f}%`)",
            f"- Query mode：`{rag_summary['query_mode']}`",
            f"- RRF k：`{rag_summary['rrf_k']}`",
            "",
            "| View | Recall@5 | MRR |",
            "|------|----------|-----|",
            f"| fused chunk_symbols | {rag_summary['fused_chunk']['avg_recall_at_k']:.4f} | {rag_summary['fused_chunk']['mrr']:.4f} |",
            f"| fused expanded_fqns | {rag_summary['fused_expanded']['avg_recall_at_k']:.4f} | {rag_summary['fused_expanded']['mrr']:.4f} |",
            "",
            "| Source | Chunk Recall@5 | Chunk MRR | Expanded Recall@5 | Expanded MRR |",
            "|--------|----------------|-----------|--------------------|--------------|",
        ]
    )
    for row in rag_summary["source_rows"]:
        lines.append(
            f"| {row['source']} | {row['chunk_recall']:.4f} | {row['chunk_mrr']:.4f} | {row['expanded_recall']:.4f} | {row['expanded_mrr']:.4f} |"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_chart(
    *,
    output_path: Path,
    gpt_summary: dict[str, Any],
    rag_summary: dict[str, Any],
    cache_count: int,
    total_chunks: int,
) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Eval Status Snapshot (2026-03-27)", fontsize=16, fontweight="bold")

    ax1 = axes[0, 0]
    diffs = ["easy", "medium", "hard"]
    diff_vals = [gpt_summary["difficulty"][d]["avg_f1"] for d in diffs]
    bars = ax1.bar(diffs, diff_vals, color=["#4c78a8", "#72b7b2", "#f58518"])
    ax1.set_ylim(0, 1.0)
    ax1.set_title("GPT-5.4 Avg F1 by Difficulty")
    ax1.set_ylabel("F1")
    for bar, value in zip(bars, diff_vals):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center")

    ax2 = axes[0, 1]
    overall = [gpt_summary["avg_f1"], gpt_summary["pass_rate"]]
    labels = ["Avg F1", "Pass Rate"]
    bars = ax2.bar(labels, overall, color=["#4c78a8", "#54a24b"])
    ax2.set_ylim(0, 1.0)
    ax2.set_title("GPT-5.4 Overall")
    for bar, value in zip(bars, overall):
        ax2.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center")

    ax3 = axes[1, 0]
    sources = [row["source"] for row in rag_summary["source_rows"]]
    chunk_vals = [row["chunk_recall"] for row in rag_summary["source_rows"]]
    expanded_vals = [row["expanded_recall"] for row in rag_summary["source_rows"]]
    x = list(range(len(sources)))
    width = 0.35
    ax3.bar([i - width / 2 for i in x], chunk_vals, width=width, label="chunk_symbols", color="#9c755f")
    ax3.bar([i + width / 2 for i in x], expanded_vals, width=width, label="expanded_fqns", color="#bab0ab")
    ax3.set_xticks(x, [s.upper() for s in sources])
    ax3.set_ylim(0, 1.0)
    ax3.set_ylabel("Recall@5")
    ax3.set_title("RAG Recall@5 by Source")
    ax3.legend()

    ax4 = axes[1, 1]
    cache_ratio = cache_count / total_chunks if total_chunks else 0.0
    vals = [
        rag_summary["fused_chunk"]["avg_recall_at_k"],
        rag_summary["fused_expanded"]["avg_recall_at_k"],
        cache_ratio,
    ]
    labels = ["Fused Chunk", "Fused Expanded", "Cache Coverage"]
    bars = ax4.bar(labels, vals, color=["#e45756", "#72b7b2", "#54a24b"])
    ax4.set_ylim(0, 1.0)
    ax4.set_title("RAG Snapshot")
    for bar, value in zip(bars, vals):
        ax4.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.3f}", ha="center")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=160, bbox_inches="tight")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate evaluation status report.")
    parser.add_argument("--gpt-results", type=Path, default=Path("results/gpt5_eval_results.json"))
    parser.add_argument("--glm-results", type=Path, default=Path("results/glm_eval_results.json"))
    parser.add_argument(
        "--rag-report",
        type=Path,
        default=Path("artifacts/rag/eval_v2_54cases_20260327.json"),
    )
    parser.add_argument(
        "--cache-path",
        type=Path,
        default=Path("artifacts/rag/embeddings_cache.json"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/eval_status_20260327.md"),
    )
    parser.add_argument(
        "--chart-output",
        type=Path,
        default=Path("reports/eval_status_20260327.png"),
    )
    args = parser.parse_args()

    gpt_results = load_json(args.gpt_results)
    glm_results = load_json(args.glm_results) if args.glm_results.exists() else []
    rag_report = load_json(args.rag_report)
    cache = load_json(args.cache_path)

    gpt_summary = summarize_gpt(gpt_results)
    glm_summary = summarize_glm(glm_results)
    rag_summary = summarize_rag(rag_report)
    total_chunks = int(rag_report["rag_index"]["num_chunks"])
    cache_count = len(cache)

    write_report(
        output_path=args.report_output,
        gpt_path=args.gpt_results,
        glm_path=args.glm_results,
        rag_path=args.rag_report,
        cache_path=args.cache_path,
        gpt_summary=gpt_summary,
        glm_summary=glm_summary,
        rag_summary=rag_summary,
        cache_count=cache_count,
        total_chunks=total_chunks,
    )
    draw_chart(
        output_path=args.chart_output,
        gpt_summary=gpt_summary,
        rag_summary=rag_summary,
        cache_count=cache_count,
        total_chunks=total_chunks,
    )

    print(f"Saved report to {args.report_output}")
    print(f"Saved chart to {args.chart_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
