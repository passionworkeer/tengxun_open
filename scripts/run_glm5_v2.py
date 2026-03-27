"""GLM-5 cucloud 评测 v2 - 带 resume，保存全部原始输出"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from evaluation.baseline import load_eval_cases
from evaluation.metrics import compute_set_metrics

API_KEY = "sk-sp-oRAg9bMjrnEZjXpIW2NqXPeN6RtW3LpM"
BASE_URL = "https://aigw-gzgy2.cucloud.cn:8443"
MODEL = "glm-5"
CASES_PATH = Path("data/eval_cases_migrated_draft_round4.json")
OUTPUT_PATH = Path("results/glm5_cucloud_full.json")


def build_prompt(case):
    parts = [f"Question: {case.question.strip()}"]
    if case.entry_symbol:
        parts.append(f"Entry Symbol: {case.entry_symbol.strip()}")
    if case.entry_file:
        parts.append(f"Entry File: {case.entry_file.strip()}")
    parts.append(
        "\nRespond with ONLY a JSON object, no other text:\n"
        '{"ground_truth": {"direct_deps": ["..."], "indirect_deps": ["..."], "implicit_deps": ["..."]}}'
    )
    return "\n\n".join(parts)


def parse_json(text):
    if not text:
        return None
    try:
        m = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        # Try finding any JSON object
        m2 = re.search(r"\{.*\}", text, re.DOTALL)
        if m2:
            data = json.loads(m2.group(0))
            if "ground_truth" in data:
                return data
        return None
    except Exception:
        return None


def call_api(client, prompt, max_retries=5):
    """Call GLM-5 API with retries, return raw text or None"""
    for attempt in range(max_retries):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            # Extract text from response
            for block in resp.content:
                if hasattr(block, "type") and block.type == "text":
                    if block.text and block.text.strip():
                        return block.text.strip()
            # Fallback: check thinking blocks
            for block in resp.content:
                if hasattr(block, "type") and block.type == "thinking":
                    if hasattr(block, "thinking") and block.thinking:
                        return block.thinking.strip()
            return None
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower():
                wait = 10 * (attempt + 1)
                print(f"  rate limited, wait {wait}s", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"  err: {err_str[:80]}", end=" ", flush=True)
                time.sleep(3)
    return None


def compute_f1(pred, gt_dict):
    all_pred = set()
    if pred:
        for v in pred.values():
            if isinstance(v, list):
                all_pred.update(v)
    all_gt = set(
        gt_dict.get("direct_deps", [])
        + gt_dict.get("indirect_deps", [])
        + gt_dict.get("implicit_deps", [])
    )
    tp = len(all_pred & all_gt)
    p = tp / len(all_pred) if all_pred else 0
    r = tp / len(all_gt) if all_gt else 0
    return 2 * p * r / (p + r) if (p + r) > 0 else 0


def main():
    cases = load_eval_cases(CASES_PATH)
    print(f"Loaded {len(cases)} eval cases")

    existing = {}
    if OUTPUT_PATH.exists():
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8-sig"))
        existing = {r["case_id"]: r for r in data}
        print(f"Existing: {len(existing)} cases done")

    client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)

    results = list(existing.values())
    done_ids = set(existing.keys())
    new_count = 0

    for i, case in enumerate(cases):
        if case.case_id in done_ids:
            continue

        new_count += 1
        print(
            f"[{len(results) + 1}/{len(cases)}] {case.case_id}...", end=" ", flush=True
        )

        raw_output = call_api(client, build_prompt(case))
        prediction = parse_json(raw_output) if raw_output else None

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns),
            "indirect_deps": list(case.indirect_gold_fqns),
            "implicit_deps": list(case.implicit_gold_fqns),
        }

        f1 = compute_f1(prediction, gt_dict) if prediction else 0

        if prediction:
            gt = prediction.get("ground_truth", {})
            pred_clean = {
                "direct_deps": gt.get("direct_deps", []),
                "indirect_deps": gt.get("indirect_deps", []),
                "implicit_deps": gt.get("implicit_deps", []),
            }
        else:
            pred_clean = None

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "failure_type": case.failure_type,
            "model": MODEL,
            "prediction": pred_clean,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "f1": round(f1, 4),
        }
        results.append(result)
        done_ids.add(case.case_id)

        OUTPUT_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        tag = "parsed" if prediction else "raw"
        print(f"F1={f1:.4f} [{tag}]", flush=True)
        time.sleep(1)

    print(f"\nDone: {new_count} new cases, {len(results)} total -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
