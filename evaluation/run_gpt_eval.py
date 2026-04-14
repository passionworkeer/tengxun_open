"""
GPT 系列模型评测脚本（OpenAI-compatible API）。

通过 OpenAI-compatible 接口对 Celery 代码仓库进行跨文件依赖分析任务评测，
计算分层依赖指标（F1、macro_f1、mislayer_rate）并支持断点续跑。

用法示例：
    python evaluation/run_gpt_eval.py \\
        --api-key <KEY> \\
        --model gpt-5.4 \\
        --cases data/eval_cases.json \\
        --output results/gpt_eval_results.json
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any

from openai import OpenAI

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_layered_dependency_metrics


def build_prompt_v2(case: EvalCase, context: str = "") -> str:
    """构建发送给 GPT 模型的评测 prompt。

    将评测案例的问题描述、入口文件锚点和入口符号组装为结构化 prompt，
    若提供额外上下文（如 RAG 检索结果）则附加在 prompt 末尾。

    Args:
        case: 评测案例对象。
        context: 可选附加上下文，默认空字符串。

    Returns:
        组装后的完整 prompt 字符串。
    """
    if case.entry_symbol:
        parts.append(f"Provided Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Provided Entry File: {case.entry_file.strip()}")
    if context:
        parts.append(f"Context:\n{context.strip()}")
    parts.append(
        "\nReturn only a JSON object with:\n"
        '{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'
    )
    return "\n\n".join(parts)


def parse_response(text: str) -> dict[str, list[str]] | None:
    """从模型原始输出中解析 ground_truth 分层依赖结果。

    优先用正则表达式匹配包含 ``"ground_truth"`` 的 JSON 子串，
    失败后尝试直接解析全文本。返回 direct_deps / indirect_deps /
    implicit_deps 三个层级的字符串列表。

    Args:
        text: 模型输出的原始文本。

    Returns:
        解析成功时返回 ``{"direct_deps": [...], "indirect_deps": [...],
        "implicit_deps": [...]}``；解析失败时返回 None。
    """
        text = text.strip()
        import re

        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
        else:
            data = json.loads(text.strip())
        gt = data.get("ground_truth", {})
        return {
            "direct_deps": gt.get("direct_deps", []),
            "indirect_deps": gt.get("indirect_deps", []),
            "implicit_deps": gt.get("implicit_deps", []),
        }
    except (json.JSONDecodeError, AttributeError, KeyError):
        return None


def compute_f1(pred: dict[str, list[str]], gt: dict[str, list[str]]) -> float:
    """计算预测结果相对于标准答案的并集 F1 分数。

    内部委托 ``compute_layered_dependency_metrics`` 对三层依赖统一评分，
    仅返回 union 级别的 F1 值。

    Args:
        pred: 模型预测结果，键为 "direct_deps" / "indirect_deps" / "implicit_deps"。
        gt: 标准答案，结构同 ``pred``。

    Returns:
        0.0 ~ 1.0 之间的 F1 分数。
    """


def run_gpt_eval(
    cases: list[EvalCase],
    api_key: str,
    base_url: str = "https://ai.td.ee/v1",
    model: str = "gpt-5.4",
    output_path: Path | None = None,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    """执行 GPT 模型评测的核心函数。

    遍历所有评测案例，对每个案例调用 OpenAI-compatible API 并计算分层
    依赖指标。每个案例最多重试 3 次，失败时记录错误信息并继续。
    结果实时写入 output_path（若提供）以支持断点续跑。

    Args:
        cases: 评测案例列表。
        api_key: API 认证密钥。
        base_url: API 基础地址，默认 "https://ai.td.ee/v1"。
        model: 模型名称，默认 "gpt-5.4"。
        output_path: 结果 JSON 文件路径，传入后自动持久化。
        max_cases: 最大评测案例数（用于快速测试）。

    Returns:
        所有评测案例的结果列表，每条记录包含 case_id、难度、预测值、
        ground_truth、F1、macro_f1、mislayer_rate 及 strict_scoring 等字段。
    """
    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    if max_cases is not None:
        cases = cases[:max_cases]

    results: list[dict[str, Any]] = []

    for i, case in enumerate(cases):
        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case, context="")
        prediction = None
        raw_output = None

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=False,
                    timeout=300,
                )
                msg = response.choices[0].message
                raw_output = msg.content if msg and msg.content else ""
                prediction = parse_response(raw_output)
                break
            except Exception as e:
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                import time

                time.sleep(5)
                raw_output = str(e)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) if case.direct_gold_fqns else [],
            "indirect_deps": list(case.indirect_gold_fqns)
            if case.indirect_gold_fqns
            else [],
            "implicit_deps": list(case.implicit_gold_fqns)
            if case.implicit_gold_fqns
            else [],
        }

        scoring = compute_layered_dependency_metrics(gt_dict, prediction or {})
        f1 = scoring.union.f1

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "model": model,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "f1": round(f1, 4),
            "macro_f1": round(scoring.macro_f1, 4),
            "mislayer_rate": round(scoring.mislayer_rate, 4),
            "strict_scoring": scoring.as_dict(),
        }
        results.append(result)
        print(f"  F1: {f1:.4f}", flush=True)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nAll {len(results)} cases completed. Results saved to {output_path}")
    return results


def main() -> int:
    """GPT 评测脚本的 CLI 入口。

    解析命令行参数，加载评测数据集，调用 ``run_gpt_eval`` 执行评测
    并持久化结果到 JSON 文件。

    Returns:
        成功时返回 0。
    """
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/eval_cases.json"),
        help="Path to evaluation dataset.",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        required=True,
        help="API key.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.4",
        help="Model name (default: gpt-5.4).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="https://ai.td.ee/v1",
        help="API base URL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/gpt5_eval_results.json"),
        help="Output path for results.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Limit number of cases (for testing).",
    )
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    run_gpt_eval(
        cases=cases,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        output_path=args.output,
        max_cases=args.max_cases,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
