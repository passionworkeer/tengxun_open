"""PE 增量评测深度分析脚本"""

import json
import sys
from pathlib import Path
from collections import Counter


def load(name):
    f = Path(f"results/pe_eval/pe_{name}.json")
    data = json.loads(f.read_text(encoding="utf-8-sig"))
    return {r["case_id"]: r for r in data}


V = ["baseline", "system_prompt", "cot", "fewshot", "postprocess"]
variants = {v: load(v) for v in V}
cids = list(variants["baseline"].keys())

# 加载 eval case 的 failure_type
eval_cases = json.loads(
    Path("data/eval_cases_migrated_draft_round4.json").read_text(encoding="utf-8-sig")
)
case_meta = {c["id"]: c for c in eval_cases}

print(f"Loaded {len(cids)} cases\n")

# ── 1. CoT 回归分析 ──
print("=" * 60)
print("1. CoT vs System Prompt 回归分析")
print("=" * 60)
regressed = []
improved = []
for cid in cids:
    sp = variants["system_prompt"][cid]["f1"]
    cot = variants["cot"][cid]["f1"]
    delta = cot - sp
    if delta < -0.05:
        regressed.append((cid, sp, cot, delta))
    elif delta > 0.05:
        improved.append((cid, sp, cot, delta))
regressed.sort(key=lambda x: x[3])
improved.sort(key=lambda x: -x[3])

print(f"\nCoT 导致下降的 case（{len(regressed)} 个）：")
for cid, sp, cot, d in regressed:
    diff = case_meta.get(cid, {}).get("difficulty", "?")
    ft = case_meta.get(cid, {}).get("failure_type", "?")
    print(f"  {cid} ({diff}, {ft}): SP={sp:.4f} -> CoT={cot:.4f} ({d:+.4f})")

print(f"\nCoT 有提升的 case（{len(improved)} 个）：")
for cid, sp, cot, d in improved[:5]:
    diff = case_meta.get(cid, {}).get("difficulty", "?")
    ft = case_meta.get(cid, {}).get("failure_type", "?")
    print(f"  {cid} ({diff}, {ft}): SP={sp:.4f} -> CoT={cot:.4f} ({d:+.4f})")

# ── 2. easy_012/easy_013 逐变体追踪 ──
print("\n" + "=" * 60)
print("2. easy_012 / easy_013 格式问题追踪")
print("=" * 60)
for cid in ["easy_012", "easy_013"]:
    gt = case_meta.get(cid, {}).get("ground_truth", {})
    print(f"\n--- {cid} ---")
    print(f"  Gold: {gt}")
    for v in V:
        r = variants[v][cid]
        pred = r.get("prediction")
        raw = r.get("raw_output", "")[:200]
        f1 = r["f1"]
        if pred:
            deps = (
                pred.get("direct_deps", [])
                + pred.get("indirect_deps", [])
                + pred.get("implicit_deps", [])
            )
            print(f"  {v:16s} F1={f1:.4f}  pred={deps}")
        else:
            print(f"  {v:16s} F1={f1:.4f}  pred=None  raw={raw}")

# ── 3. 全量 PE 对各 failure_type 的效果 ──
print("\n" + "=" * 60)
print("3. 各失效类型的 PE 逐步增益")
print("=" * 60)
ft_list = sorted(
    set(
        case_meta[c].get("failure_type", "")
        for c in cids
        if case_meta[c].get("failure_type")
    )
)

for ft in ft_list:
    ft_cids = [c for c in cids if case_meta[c].get("failure_type") == ft]
    if not ft_cids:
        continue
    print(f"\n{ft} ({len(ft_cids)} cases):")
    for v in V:
        avg = sum(variants[v][c]["f1"] for c in ft_cids) / len(ft_cids)
        print(f"  {v:16s} Avg F1 = {avg:.4f}")

# ── 4. 永远失败的 case ──
print("\n" + "=" * 60)
print("4. 所有变体 F1=0 的 case（PE 无法解决）")
print("=" * 60)
for cid in cids:
    if all(variants[v][cid]["f1"] == 0.0 for v in V):
        diff = case_meta[cid].get("difficulty", "?")
        ft = case_meta[cid].get("failure_type", "?")
        q = case_meta[cid].get("question", "")[:80]
        print(f"  {cid} ({diff}, {ft}): {q}...")

# ── 5. 最终全量 vs Baseline 提升最大的 case ──
print("\n" + "=" * 60)
print("5. 全量 PE 提升最大的 Top 10 Case")
print("=" * 60)
gains = []
for cid in cids:
    bl = variants["baseline"][cid]["f1"]
    pp = variants["postprocess"][cid]["f1"]
    gains.append((cid, bl, pp, pp - bl))
gains.sort(key=lambda x: -x[3])
for cid, bl, pp, d in gains[:10]:
    diff = case_meta[cid].get("difficulty", "?")
    ft = case_meta[cid].get("failure_type", "?")
    print(f"  {cid} ({diff}, {ft}): Baseline={bl:.4f} -> Full PE={pp:.4f} ({d:+.4f})")

# ── 6. 各难度的环比增益矩阵 ──
print("\n" + "=" * 60)
print("6. 逐步环比增益矩阵（按难度）")
print("=" * 60)
print(f"{'Step':<20} {'Easy':>8} {'Medium':>8} {'Hard':>8} {'Avg':>8}")
print("-" * 56)
prev = {d: {c: 0.0 for c in cids} for d in ["easy", "medium", "hard"]}
for i, v in enumerate(V):
    by_diff = {}
    for d in ["easy", "medium", "hard"]:
        dc = [c for c in cids if case_meta[c].get("difficulty") == d]
        by_diff[d] = sum(variants[v][c]["f1"] for c in dc) / len(dc) if dc else 0
    avg = sum(variants[v][c]["f1"] for c in cids) / len(cids)
    label = v
    if i > 0:
        pv = V[i - 1]
        delta_e = by_diff["easy"] - sum(
            variants[pv][c]["f1"]
            for c in [c for c in cids if case_meta[c].get("difficulty") == "easy"]
        ) / len([c for c in cids if case_meta[c].get("difficulty") == "easy"])
        delta_m = by_diff["medium"] - sum(
            variants[pv][c]["f1"]
            for c in [c for c in cids if case_meta[c].get("difficulty") == "medium"]
        ) / len([c for c in cids if case_meta[c].get("difficulty") == "medium"])
        delta_h = by_diff["hard"] - sum(
            variants[pv][c]["f1"]
            for c in [c for c in cids if case_meta[c].get("difficulty") == "hard"]
        ) / len([c for c in cids if case_meta[c].get("difficulty") == "hard"])
        prev_avg = sum(variants[pv][c]["f1"] for c in cids) / len(cids)
        delta_a = avg - prev_avg
        print(
            f"{label:<20} {by_diff['easy']:>8.4f} {by_diff['medium']:>8.4f} {by_diff['hard']:>8.4f} {avg:>8.4f}  (环比 {delta_a:+.4f})"
        )
    else:
        print(
            f"{label:<20} {by_diff['easy']:>8.4f} {by_diff['medium']:>8.4f} {by_diff['hard']:>8.4f} {avg:>8.4f}"
        )
