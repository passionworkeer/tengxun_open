"""补跑 GLM-5 评测缺失的 12 个 case。"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic

from evaluation.baseline import EvalCase, load_eval_cases
from evaluation.metrics import compute_set_metrics

BASE_URL = "https://aigw-gzgy2.cucloud.cn:8443"
API_KEY = os.environ.get("CUCLOUD_API_KEY", "")
MODEL = "glm-5"
MAX_TOKENS = 16384
CASES_PATH = Path("data/eval_cases.json")
OUTPUT_PATH = Path("results/glm5_cucloud_eval_results.json")
PROMPT_SUFFIX = '\nReturn only a JSON object with:\n{"ground_truth": {"direct_deps": [...], "indirect_deps": [...], "implicit_deps": [...]}}'

# 要补的 case_id
MISSING_IDS = [
    "easy_016", "medium_011", "medium_012", "medium_013", "medium_014",
    "medium_015", "medium_016", "medium_017", "medium_018", "medium_020",
    "hard_015", "medium_021",
]


def build_prompt(case: EvalCase) -> str:
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(PROMPT_SUFFIX)
    return "\n\n".join(parts)


def parse_response(text: str | None):
    if not text:
        return None
    try:
        text = text.strip()
        match = re.search(r"\{[^{]*\"ground_truth\"[^{]*\{.*\}", text, re.DOTALL)
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


def compute_f1(pred, gt):
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


def run():
    if not API_KEY:
        raise SystemExit("CUCLOUD_API_KEY is not set.")
    done = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    done_ids = {r["case_id"] for r in done}

    all_cases = load_eval_cases(CASES_PATH)
    case_map = {c.case_id: c for c in all_cases}

    to_fill = [case_map[cid] for cid in MISSING_IDS if cid in case_map and cid not in done_ids]
    print(f"需补: {len(to_fill)} 条")

    client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)
    results = list(done)

    for i, case in enumerate(to_fill):
        t0 = time.time()
        print(f"[{i + 1}/{len(to_fill)}] {case.case_id}...", flush=True)
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
                    print(f"  attempt {attempt + 1}: parse failed", flush=True)
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
        print(f"  F1={f1:.4f}  pred={status}  time={elapsed:.0f}s", flush=True)

        OUTPUT_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"\n完成。总结果数: {len(results)}")
    n_pred = sum(1 for r in results if r["prediction"] is not None)
    f1s = [r["f1"] for r in results]
    print(f"有预测: {n_pred}/{len(results)}  avg_f1: {sum(f1s)/len(f1s):.4f}")


if __name__ == "__main__":
    run()
