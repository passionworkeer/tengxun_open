"""GLM-5 cucloud 评测（带 resume，保存全部原始输出）"""

import json
import os
import re
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from evaluation.baseline import load_eval_cases

API_KEY = os.environ.get("CUCLOUD_API_KEY", "")
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
        "\nYou MUST respond with ONLY a JSON object in this exact format, no other text:\n"
        '{"ground_truth": {"direct_deps": ["fqn1", "fqn2"], '
        '"indirect_deps": ["fqn3"], '
        '"implicit_deps": ["fqn4"]}}'
    )
    return "\n\n".join(parts)


def parse_json(text):
    if not text:
        return None
    try:
        m = re.search(r'\{[^{]*"ground_truth"[^{]*\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        return json.loads(text.strip())
    except Exception:
        return None


def main():
    if not API_KEY:
        raise SystemExit("CUCLOUD_API_KEY is not set.")
    cases = load_eval_cases(CASES_PATH)
    print(f"Loaded {len(cases)} eval cases")

    # Load existing
    existing = {}
    if OUTPUT_PATH.exists():
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8-sig"))
        existing = {r["case_id"]: r for r in data}
        print(f"Existing: {len(existing)} cases done")

    client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)

    results = list(existing.values())
    done_ids = set(existing.keys())

    for i, case in enumerate(cases):
        if case.case_id in done_ids:
            continue

        print(
            f"[{len(results) + 1}/{len(cases)}] {case.case_id}...", end=" ", flush=True
        )

        prompt = build_prompt(case)
        raw_output = None
        prediction = None

        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                for block in resp.content:
                    if block.type == "text":
                        raw_output = block.text
                        break
                if raw_output:
                    parsed = parse_json(raw_output)
                    if parsed:
                        gt = parsed.get("ground_truth", {})
                        prediction = {
                            "direct_deps": gt.get("direct_deps", []),
                            "indirect_deps": gt.get("indirect_deps", []),
                            "implicit_deps": gt.get("implicit_deps", []),
                        }
                    break
                else:
                    print(f"  retry {attempt + 1}: empty", end=" ", flush=True)
                    time.sleep(3)
            except Exception as e:
                print(f"  retry {attempt + 1}: {e}", end=" ", flush=True)
                time.sleep(5)

        gt_dict = {
            "direct_deps": list(case.direct_gold_fqns),
            "indirect_deps": list(case.indirect_gold_fqns),
            "implicit_deps": list(case.implicit_gold_fqns),
        }

        all_pred = set()
        if prediction:
            for v in prediction.values():
                all_pred.update(v)
        all_gt = set(
            gt_dict["direct_deps"] + gt_dict["indirect_deps"] + gt_dict["implicit_deps"]
        )
        tp = len(all_pred & all_gt)
        prec = tp / len(all_pred) if all_pred else 0
        rec = tp / len(all_gt) if all_gt else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

        result = {
            "case_id": case.case_id,
            "difficulty": case.difficulty,
            "failure_type": case.failure_type,
            "model": MODEL,
            "prediction": prediction,
            "ground_truth": gt_dict,
            "raw_output": raw_output,
            "f1": round(f1, 4),
        }
        results.append(result)
        done_ids.add(case.case_id)

        # Save after each
        OUTPUT_PATH.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        status = "parsed" if prediction else "raw_only"
        print(f"F1={f1:.4f} [{status}]", flush=True)

        time.sleep(1)

    print(f"\nDone: {len(results)}/{len(cases)} cases saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
