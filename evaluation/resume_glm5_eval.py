"""续跑 GLM-5 评测（补跑剩余 27 个 case）。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic

from evaluation.baseline import EvalCase, load_eval_cases
from evaluation.metrics import compute_set_metrics

BASE_URL = "https://aigw-gzgy2.cucloud.cn:8443"
API_KEY = "sk-sp-oRAg9bMjrnEZjXpIW2NqXPeN6RtW3LpM"
MODEL = "glm-5"
MAX_TOKENS = 16384  # 必须够大，thinking 会吃掉大量 token
CASES_PATH = Path("data/eval_cases_migrated_draft_round4.json")
OUTPUT_PATH = Path("results/glm5_cucloud_eval_results.json")
PROMPT_SUFFIX = '\nReturn only a JSON object with:\n{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'


def build_prompt(case: EvalCase) -> str:
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(PROMPT_SUFFIX)
    return "\n\n".join(parts)


def parse_response(text: str | None) -> dict[str, list[str]] | None:
    """从 text block 中抽取 JSON 预测结果。"""
    if not text:
        return None
    try:
        text = text.strip()
        # 优先找最外层 { ... "ground_truth" ... }
        match = re.search(
            r"\{[^{]*\"ground_truth\"[^{]*\{.*\}", text, re.DOTALL
        )
        json_str = match.group(0) if match else text
        data = json.loads(json_str)
        gt = data.get("ground_truth", {})
        return {
            "direct_deps": gt.get("direct_deps", []),
            "indirect_deps": gt.get("indirect_deps", []),
            "implicit_deps": gt.get("implicit_deps", []),
        }
    except Exception:
        return None


def compute_f1(pred: dict[str, list[str]], gt: dict[str, list[str]]) -> float:
    all_pred = set(
        pred.get("direct_deps", [])
        + pred.get("indirect_deps", [])
        + pred.get("implicit_deps", [])
    )
    all_gt = set(
        gt.get("direct_deps", [])
        + gt.get("indirect_deps", [])
        + gt.get("implicit_deps", [])
    )
    return compute_set_metrics(list(all_gt), list(all_pred)).f1


def run() -> None:
    # 加载已有结果
    done = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    done_ids = {r["case_id"] for r in done}

    cases = load_eval_cases(CASES_PATH)
    remaining = [c for c in cases if c.case_id not in done_ids]
    print(f"数据集: {len(cases)} / 已完成: {len(done_ids)} / 剩余: {len(remaining)}")

    client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)
    results = list(done)

    for i, case in enumerate(remaining):
        t0 = time.time()
        print(f"[{i + 1}/{len(remaining)}] {case.case_id}...", flush=True)
        prompt = build_prompt(case)
        prediction, raw_output = None, None

        for attempt in range(5):
            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw_output = None
                for block in resp.content:
                    if block.type == "text":
                        raw_output = block.text
                        break

                if raw_output:
                    prediction = parse_response(raw_output)
                    if prediction:
                        break
                    print(
                        f"  attempt {attempt + 1}: parse failed", flush=True
                    )
                else:
                    print(
                        f"  attempt {attempt + 1}: no text block (blocks={len(resp.content)})",
                        flush=True,
                    )
                time.sleep(3)

            except Exception as e:
                print(f"  attempt {attempt + 1} ERROR: {e}", flush=True)
                time.sleep(5)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns) or [],
            "indirect_deps": list(case.indirect_gold_fqns) or [],
            "implicit_deps": list(case.implicit_gold_fqns) or [],
        }
        f1 = compute_f1(prediction or {}, gt_dict) if prediction else 0.0

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "category": case.category,
            "model": MODEL,
            "question": case.question,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "f1": round(f1, 4),
        }
        results.append(result)
        elapsed = time.time() - t0
        status = "OK" if prediction else "MISS"
        print(
            f"  F1={f1:.4f}  pred={status}  time={elapsed:.0f}s",
            flush=True,
        )

        # checkpoint
        OUTPUT_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"\n完成。总结果数: {len(results)}")


if __name__ == "__main__":
    run()
