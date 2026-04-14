"""
GLM（智谱）模型评测脚本。

通过 OpenAI-compatible API 或官方 bigmodel.cn HTTP 接口对 Celery
代码仓库进行跨文件依赖分析任务评测，支持流式推理输出收集、
断点续跑、配额错误检测和分层依赖指标计算。

用法示例：
    python evaluation/run_glm_eval.py \\
        --api-key <KEY> \\
        --model ZhipuAI/GLM-5 \\
        --cases data/eval_cases.json \\
        --output results/glm_eval_results.json
"""

from __future__ import annotations

import json
import argparse
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - official HTTP path does not need the SDK
    OpenAI = None

from evaluation.baseline import load_eval_cases, EvalCase
from evaluation.metrics import compute_layered_dependency_metrics


def build_prompt_v2(case: EvalCase, context: str = "") -> str:
    """构建发送给 GLM 模型的评测 prompt。

    将评测案例的问题描述、入口文件锚点和入口符号组装为结构化 prompt。
    若提供额外上下文（如 RAG 检索结果），会附加在 prompt 末尾。

    Args:
        case: 评测案例对象，包含 question、entry_file、entry_symbol 等字段。
        context: 可选附加上下文，默认空字符串。

    Returns:
        组装后的完整 prompt 字符串。
    """
    parts = [f"Question: {case.question.strip()}"]
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


def parse_response(text: str | None) -> dict[str, list[str]] | None:
    """从模型原始输出中解析 ground_truth 分层依赖结果。

    尝试两种提取策略：
    1. 先用正则表达式匹配最外层包含 ``"ground_truth"`` 的 JSON 对象；
    2. 若正则失败则直接 ``json.loads()`` 全文本。

    解析后对三个层级（direct_deps / indirect_deps / implicit_deps）分别
    归一化为去除首尾空格后的字符串列表，空列表或非 list 类型返回空列表。

    Args:
        text: 模型输出的原始文本，可为 None。

    Returns:
        解析成功时返回形如
        ``{"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}``
        的字典；解析失败时返回 None。
    """
        return None
    try:
        text = text.strip()
        import re

        match = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            data = json.loads(json_str)
        else:
            data = json.loads(text.strip())
        gt = data.get("ground_truth", {})

        def normalize_items(items: Any) -> list[str]:
            if not isinstance(items, list):
                return []
            result: list[str] = []
            for item in items:
                if isinstance(item, str):
                    value = item.strip()
                    if value:
                        result.append(value)
            return result

        return {
            "direct_deps": normalize_items(gt.get("direct_deps", [])),
            "indirect_deps": normalize_items(gt.get("indirect_deps", [])),
            "implicit_deps": normalize_items(gt.get("implicit_deps", [])),
        }
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
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


def _load_existing_results(output_path: Path | None) -> list[dict[str, Any]]:
    """加载已有的评测结果文件以支持断点续跑。

    Args:
        output_path: 结果 JSON 文件路径，为 None 或文件不存在时返回空列表。

    Returns:
        已保存的结果列表（非 list 格式或解析失败时返回空列表）。
    """
        return []
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _collect_stream_response(stream: Any) -> tuple[str, str, str | None, str | None]:
    """收集 OpenAI-compatible 流式响应的所有 chunks。

    将流式 SSE 数据块拆分为 ``reasoning_content``（思考过程）和
    ``content``（最终回答）两部分，并记录模型标识和 finish_reason。

    Args:
        stream: 由 ``client.chat.completions.create(stream=True)`` 返回的
           迭代器对象。

    Returns:
        四元组 ``(answer_text, reasoning_text, model_name, finish_reason)``。
        若流为空则各字段均为空字符串或 None。
    """
    answer_parts: list[str] = []
    response_model = None
    finish_reason = None

    for chunk in stream:
        if response_model is None:
            response_model = getattr(chunk, "model", None)

        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue

        choice = choices[0]
        delta = getattr(choice, "delta", None)
        if delta is None:
            continue

        reasoning_chunk = getattr(delta, "reasoning_content", None)
        answer_chunk = getattr(delta, "content", None)
        if reasoning_chunk:
            reasoning_parts.append(reasoning_chunk)
        if answer_chunk:
            answer_parts.append(answer_chunk)
        if getattr(choice, "finish_reason", None):
            finish_reason = choice.finish_reason

    return (
        "".join(answer_parts).strip(),
        "".join(reasoning_parts).strip(),
        response_model,
        finish_reason,
    )


def _use_official_http_api(base_url: str) -> bool:
    """判断是否应使用官方 bigmodel.cn HTTP API 而非 OpenAI-compatible SDK。

    Args:
        base_url: API 基础地址。

    Returns:
        若 base_url 包含 "open.bigmodel.cn" 则返回 True。
    """


def _official_chat_url(base_url: str) -> str:
    """将 base_url 补全为官方 bigmodel.cn 的 chat/completions 端点。

    Args:
        base_url: API 基础地址。

    Returns:
        以 ``/chat/completions`` 结尾的完整 URL。
    """
    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def _collect_http_response(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    thinking_mode: str | None = None,
) -> tuple[str, str, str | None, str | None, dict[str, Any]]:
    """通过官方 bigmodel.cn HTTP 接口发送非流式请求并收集响应。

    Args:
        base_url: API 基础地址。
        api_key: 认证密钥。
        model: 模型名称。
        prompt: 用户输入的 prompt。
        max_tokens: 最大生成 token 数。
        timeout: HTTP 请求超时时间（秒）。
        thinking_mode: 可选思考模式（"enabled" / "disabled"），会注入到请求体。

    Returns:
        五元组 ``(content, reasoning_content, model_name, finish_reason, raw_body)``。

    Raises:
        RuntimeError: HTTP 响应状态码非 2xx 时抛出。
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 1.0,
    }
    if thinking_mode:
        payload["thinking"] = {"type": thinking_mode}
    req = urllib.request.Request(
        _official_chat_url(base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Official GLM HTTP error {exc.code}: {body}") from exc

    choices = body.get("choices", [])
    if not choices:
        return "", "", body.get("model"), None, body

    choice = choices[0]
    message = choice.get("message", {}) or {}
    return (
        str(message.get("content", "")).strip(),
        str(message.get("reasoning_content", "")).strip(),
        body.get("model"),
        choice.get("finish_reason"),
        body,
    )


def _collect_http_stream_response(
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    thinking_mode: str | None = None,
) -> tuple[str, str, str | None, str | None, dict[str, Any]]:
    """通过官方 bigmodel.cn HTTP 接口发送流式请求并收集全部 SSE 数据块。

    Args:
        base_url: API 基础地址。
        api_key: 认证密钥。
        model: 模型名称。
        prompt: 用户输入的 prompt。
        max_tokens: 最大生成 token 数。
        timeout: HTTP 请求超时时间（秒）。
        thinking_mode: 可选思考模式，会注入到请求体。

    Returns:
        五元组 ``(content, reasoning_content, model_name, finish_reason, meta)``。
        ``meta`` 包含 ``stream_chunk_count`` 记录收流的 chunk 总数。
    """
    import requests

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": 1.0,
    }
    if thinking_mode:
        payload["thinking"] = {"type": thinking_mode}

    reasoning_parts: list[str] = []
    answer_parts: list[str] = []
    response_model = None
    finish_reason = None
    chunk_count = 0

    with requests.post(
        _official_chat_url(base_url),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        stream=True,
        timeout=timeout,
    ) as response:
        response.raise_for_status()
        for raw_line in response.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "):
                continue
            payload_text = raw_line[6:]
            if payload_text.strip() == "[DONE]":
                break
            body = json.loads(payload_text)
            if response_model is None:
                response_model = body.get("model")
            choices = body.get("choices", [])
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta", {}) or {}
            reasoning_chunk = delta.get("reasoning_content")
            answer_chunk = delta.get("content")
            if reasoning_chunk:
                reasoning_parts.append(str(reasoning_chunk))
            if answer_chunk:
                if isinstance(answer_chunk, list):
                    answer_parts.extend(str(item) for item in answer_chunk if item)
                else:
                    answer_parts.append(str(answer_chunk))
            if choice.get("finish_reason"):
                finish_reason = choice.get("finish_reason")
            chunk_count += 1

    return (
        "".join(answer_parts).strip(),
        "".join(reasoning_parts).strip(),
        response_model,
        finish_reason,
        {"stream_chunk_count": chunk_count},
    )


def _is_fatal_quota_error(exc: Exception) -> bool:
    """判断异常是否由服务商配额耗尽导致，属于不可重试的致命错误。

    检查错误信息中是否包含以下关键词：
    ``today's quota``、``insufficient_quota``、``exceeded your current quota``。

    Args:
        exc: 捕获的异常对象。

    Returns:
        若是配额类致命错误返回 True，否则返回 False。
    """
    return (
        "today's quota" in text
        or "insufficient_quota" in text
        or "exceeded your current quota" in text
    )


def run_eval(
    cases: list[EvalCase],
    api_key: str,
    model: str = "ZhipuAI/GLM-5",
    base_url: str = "https://api-inference.modelscope.cn/v1",
    max_tokens: int = 1024,
    timeout: int = 300,
    thinking_mode: str | None = None,
    save_raw_response: bool = False,
    output_path: Path | None = None,
    max_cases: int | None = None,
    official_stream: bool = False,
) -> list[dict[str, Any]]:
    """执行 GLM 模型评测的核心函数。

    遍历所有评测案例，对每个案例调用 GLM API 并计算分层依赖指标。
    支持断点续跑（自动跳过已完成案例）、配额错误快速终止、
    流式/非流式双路径收集推理内容。

    Args:
        cases: 评测案例列表。
        api_key: API 认证密钥。
        model: 模型名称，默认 "ZhipuAI/GLM-5"。
        base_url: API 基础地址。
        max_tokens: 单次生成的最大 token 数。
        timeout: HTTP 请求超时（秒）。
        thinking_mode: 思考模式（"enabled" / "disabled"），None 表示平台默认。
        save_raw_response: 是否在结果中保存服务商原始响应体。
        output_path: 结果 JSON 文件路径，传入后自动持久化（实时写入）。
        max_cases: 最大评测案例数（用于快速测试）。
        official_stream: 是否对官方 bigmodel.cn 接口使用流式收集。

    Returns:
        所有评测案例的结果列表，每条记录包含 case_id、难度、预测值、
        ground_truth、F1、macro_f1、mislayer_rate 及详细评分等字段。
    """
    use_official_http_api = _use_official_http_api(base_url)
    client = None
    if not use_official_http_api:
        if OpenAI is None:
            raise RuntimeError(
                "openai package is required for non-official GLM endpoints. "
                "Install it or use the official https://open.bigmodel.cn API."
            )
        client = OpenAI(base_url=base_url, api_key=api_key)

    if max_cases is not None:
        cases = cases[:max_cases]

    results = _load_existing_results(output_path)
    completed_case_ids = {item.get("case_id") for item in results}

    for i, case in enumerate(cases):
        if case.case_id in completed_case_ids:
            print(f"[{i + 1}/{len(cases)}] Skipping {case.case_id} (already done)", flush=True)
            continue

        print(f"[{i + 1}/{len(cases)}] Running {case.case_id}...", flush=True)

        prompt = build_prompt_v2(case, context="")
        prediction = None
        raw_output = None
        reasoning_output = None
        response_model = None
        finish_reason = None
        raw_response = None
        fatal_error = None

        for attempt in range(5):
            try:
                if use_official_http_api:
                    collector = (
                        _collect_http_stream_response
                        if official_stream
                        else _collect_http_response
                    )
                    (
                        raw_output,
                        reasoning_output,
                        response_model,
                        finish_reason,
                        raw_response,
                    ) = collector(
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        thinking_mode=thinking_mode,
                    )
                    prediction = parse_response(raw_output) if raw_output else None
                    if prediction:
                        break
                else:
                    stream = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        stream=True,
                        max_tokens=max_tokens,
                        timeout=timeout,
                        extra_body={"thinking": {"type": "enabled"}},
                    )
                    raw_output, reasoning_output, response_model, finish_reason = (
                        _collect_stream_response(stream)
                    )

                if raw_output:
                    prediction = parse_response(raw_output)
                    if prediction:
                        break
                    print(
                        f"  Attempt {attempt + 1}: parse failed, retrying...",
                        flush=True,
                    )
                else:
                    print(f"  Attempt {attempt + 1}: empty content", flush=True)

                time.sleep(3)

            except Exception as e:
                if _is_fatal_quota_error(e):
                    fatal_error = str(e)
                    print(f"  Fatal quota error: {fatal_error}", flush=True)
                    break
                print(f"  Attempt {attempt + 1} ERROR: {e}", flush=True)
                time.sleep(5)

        if fatal_error is not None:
            if output_path and results:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            raise RuntimeError(
                f"Stopped at {case.case_id} due to provider quota limit: {fatal_error}"
            )

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
            "base_url": base_url,
            "thinking_mode": thinking_mode or "provider_default",
            "response_model": response_model,
            "finish_reason": finish_reason,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "reasoning_output": reasoning_output,
            "f1": round(f1, 4),
            "macro_f1": round(scoring.macro_f1, 4),
            "mislayer_rate": round(scoring.mislayer_rate, 4),
            "strict_scoring": scoring.as_dict(),
        }
        if save_raw_response:
            result["raw_response"] = raw_response
        results.append(result)
        completed_case_ids.add(case.case_id)
        print(f"  F1: {f1:.4f}", flush=True)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    print(f"\nAll cases completed. Results saved to {output_path}")
    return results


def main() -> int:
    """GLM 评测脚本的 CLI 入口。

    解析命令行参数，加载评测数据集，调用 ``run_eval`` 执行评测并持久化结果。

    Returns:
        成功时返回 0，失败时抛出异常。
    """
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("MODELSCOPE_API_KEY", ""),
    )
    parser.add_argument("--model", type=str, default="ZhipuAI/GLM-5")
    parser.add_argument(
        "--base-url", type=str, default="https://api-inference.modelscope.cn/v1"
    )
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--thinking-mode",
        type=str,
        default="",
        help="Official GLM thinking mode: enabled / disabled. Empty means provider default.",
    )
    parser.add_argument(
        "--save-raw-response",
        action="store_true",
        help="Persist the provider's raw response body in each result record.",
    )
    parser.add_argument(
        "--official-stream",
        action="store_true",
        help="Use streaming collection for the official open.bigmodel.cn endpoint.",
    )
    parser.add_argument(
        "--cases", type=Path, default=Path("data/eval_cases.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/glm_eval_results.json")
    )
    parser.add_argument("--max-cases", type=int, default=None)
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("API key not provided. Pass --api-key or export the provider key env var.")

    cases = load_eval_cases(args.cases)
    print(f"Loaded {len(cases)} eval cases.")

    run_eval(
        cases=cases,
        api_key=args.api_key,
        model=args.model,
        base_url=args.base_url,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        thinking_mode=args.thinking_mode or None,
        save_raw_response=args.save_raw_response,
        output_path=args.output,
        max_cases=args.max_cases,
        official_stream=args.official_stream,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
