#!/usr/bin/env python3
"""
微调数据增强脚本

对现有 497 条 finetune 数据进行增强:
1. 同义词替换 / 措辞改写 (paraphrase)
2. 增加 Hard 样本变体 (优先对 Type E 增加)
3. 保持 ground_truth 不变
4. 避免与 eval_cases.json 重叠

目标分布:
  Easy:   30%  (约 210 条)
  Medium: 35%  (约 245 条)
  Hard:   35%  (约 245 条)

用法:
    python scripts/augment_finetune_data.py --trials 2 --output data/finetune_dataset_augmented.jsonl
    python scripts/augment_finetune_data.py --augment-hard-only --output data/finetune_hard_aug.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

# ─── Paraphrase Templates ─────────────────────────────────────────────────

# 中文同义词映射（针对指令措辞）
_SYNONYMS = {
    "确定": ["找出", "定位", "识别", "确认"],
    "找出": ["确定", "定位", "识别", "确认"],
    "分析": ["解析", "拆解", "研究", "剖析"],
    "依赖": ["关联", "关联项", "所需模块", "所依赖的"],
    "导入": ["引入", "import", "加载"],
    "调用": ["触发", "执行", "invoke", "调用到"],
    "函数": ["方法", "func", "function"],
    "类": ["class", "对象类型"],
    "模块": ["package", "包", "module"],
    "查找": ["搜索", "检索", "寻找"],
    "哪个": ["哪一个", "哪一", "哪个具体的"],
    "哪些": ["哪些具体的", "哪一些", "哪些个"],
    "追踪": ["追溯", "跟踪", "顺着...找"],
    "理解": ["掌握", "搞清楚", "弄清楚"],
}

# Type E 专用改写模板（增加多跳表述变化）
_TYPE_E_PARAPHRASES = [
    "在 {entry} 中，{target} 最终会调用到哪个 {category}？",
    "顺着 {target} 这条调用链，最终指向的 {category} 是什么？",
    "{entry} 内部调用 {target} 时，实际加载的 {category} 是哪个？",
    "从 {entry} 出发追踪 {target}，哪一条路径指向的 {category} 是答案？",
    "{entry} → {target} → ? 这个链路中，最终的 {category} 是谁？",
]

# 通用改写模板
_GENERAL_PARAPHRASES = [
    "请{action} {subject}",
    "{subject} 的 {action} 是什么？",
    "关于 {subject}，需要{action}哪些内容？",
    "{subject} 中，{action}的逻辑是什么？",
]

# Type E 关键词（用于识别需要多跳检索的样本）
_TYPE_E_KEYWORDS = [
    "调用链", "调用到", "最终", "链路", "链", "追溯",
    "追踪", "路径", "间接", "多层", "多跳",
]


def _seed(seed: int = 42) -> None:
    random.seed(seed)


def _load_eval_questions() -> set[str]:
    """加载 eval_cases 中的问题，规避重复。"""
    eval_path = _ROOT / "data" / "eval_cases.json"
    if not eval_path.exists():
        return set()
    cases = json.load(open(eval_path, encoding="utf-8"))
    return {case["question"].strip() for case in cases if isinstance(case, dict)}


def _load_finetune_data(path: Path) -> list[dict]:
    """加载 finetune 数据集。"""
    if not path.exists():
        raise FileNotFoundError(f"Finetune data not found: {path}")
    return [json.loads(line, strict=False) for line in open(path, encoding="utf-8")]


def _synonym_replace(text: str, max_replacements: int = 2) -> str:
    """
    简单基于规则进行同义词替换。
    只替换关键词，保留原始语义。
    """
    result = text
    replacements = 0
    for word, synonyms in _SYNONYMS.items():
        if word in result and replacements < max_replacements:
            # 随机选择一个同义词
            replacement = random.choice(synonyms)
            # 只替换第一次出现，避免语义完全崩塌
            result = result.replace(word, replacement, 1)
            replacements += 1
    return result


def _is_type_e(instruction: str) -> bool:
    """判断是否属于 Type E（多跳检索）样本。"""
    instruction_lower = instruction.lower()
    return any(kw in instruction_lower for kw in _TYPE_E_KEYWORDS)


def _extract_components(sample: dict) -> dict:
    """从样本中提取改写所需的组件。"""
    instruction = sample.get("instruction", "")
    category = sample.get("category", "未知")
    difficulty = sample.get("difficulty", "")
    failure_type = sample.get("failure_type", "")

    # 尝试提取 entry 和 target（从 instruction 中解析）
    # 格式如: "在 celery/app/base.py 中，分析 xxx 类型..."
    entry_match = re.search(r"在\s+([\w./]+)\s+中", instruction)
    entry = entry_match.group(1) if entry_match else ""

    target_match = re.search(r"[分析查找定位确定]\s+([\w_]+)\s*[的类型]", instruction)
    target = target_match.group(1) if target_match else category

    return {
        "entry": entry,
        "target": target,
        "category": category,
        "instruction": instruction,
        "difficulty": difficulty,
        "failure_type": failure_type,
    }


def _paraphrase_instruction(sample: dict, eval_questions: set[str]) -> str | None:
    """
    生成指令改写变体。

    策略:
    1. Type E: 使用专用多跳模板
    2. Type A-D: 同义词替换 + 通用模板改写
    3. 避免与 eval_cases 问题重复
    """
    instruction = sample.get("instruction", "").strip()
    failure_type = sample.get("failure_type", "")
    difficulty = sample.get("difficulty", "")
    comps = _extract_components(sample)

    candidates: list[str] = []

    if failure_type == "Type E" or _is_type_e(instruction):
        # Type E: 多跳表述变化
        for template in _TYPE_E_PARAPHRASES:
            if "{entry}" in template and not comps["entry"]:
                continue
            if "{target}" in template and not comps["target"]:
                continue
            try:
                candidate = template.format(
                    entry=comps["entry"],
                    target=comps["target"],
                    category=comps["category"],
                )
                candidates.append(candidate)
            except (KeyError, ValueError):
                pass

    # 通用改写：同义词替换
    synonym_version = _synonym_replace(instruction)
    if synonym_version != instruction:
        candidates.append(synonym_version)

    # 通用改写：模板改写（仅用于非 Type E）
    if failure_type != "Type E":
        action_words = ["分析", "确定", "找出", "定位"]
        for action in action_words:
            if action not in instruction:
                continue
            for template in _GENERAL_PARAPHRASES[:2]:
                candidate = template.format(
                    action=action,
                    subject=comps["category"],
                )
                # 确保不完全等于原始指令
                if candidate.strip() != instruction.strip():
                    candidates.append(candidate)

    # 过滤掉与 eval_questions 重复的
    candidates = [c for c in candidates if c.strip() not in eval_questions]
    # 过滤掉与原始指令完全相同的
    candidates = [c for c in candidates if c.strip() != instruction.strip()]

    if candidates:
        return random.choice(candidates)
    return None


def _augment_sample(
    sample: dict,
    eval_questions: set[str],
    add_paraphrase: bool = True,
    make_harder: bool = False,
) -> list[dict]:
    """
    对单个样本生成增强变体。

    Args:
        sample: 原始样本
        eval_questions: eval_cases 中的问题集（用于去重）
        add_paraphrase: 是否添加措辞变体
        make_harder: 是否将样本难度提升一级（仅 Medium → Hard）

    Returns:
        新增样本列表（不含原始样本）
    """
    augmented: list[dict] = []
    failure_type = sample.get("failure_type", "")
    difficulty = sample.get("difficulty", "")

    # ── 策略 1: 措辞改写 ──────────────────────────────────────────────
    if add_paraphrase:
        paraphrase = _paraphrase_instruction(sample, eval_questions)
        if paraphrase:
            new_sample = dict(sample)
            new_sample["instruction"] = paraphrase
            new_sample["verified"] = False  # 标记为未验证
            new_sample["verify_method"] = "augmented"
            augmented.append(new_sample)

    # ── 策略 2: 增加难度（Medium → Hard）───────────────────────────────
    if make_harder and difficulty == "medium":
        harder_sample = dict(sample)
        harder_sample["difficulty"] = "hard"
        # 在 instruction 中加入"多步"或"间接"等暗示
        harder_instr = sample.get("instruction", "")
        if not any(kw in harder_instr for kw in _TYPE_E_KEYWORDS):
            harder_instr = f"【进阶】{harder_instr}"
        harder_sample["instruction"] = harder_instr
        harder_sample["verified"] = False
        harder_sample["verify_method"] = "augmented"
        augmented.append(harder_sample)

    return augmented


def _build_augmented_dataset(
    original: list[dict],
    eval_questions: set[str],
    target_distribution: dict[str, float],
    max_per_failure_type: int | None = None,
) -> list[dict]:
    """
    构建增强后的完整数据集。

    策略:
    - Type E: 每个样本生成 2 个变体（paraphrase + harder）
    - Type D/C: 每个样本生成 1-2 个变体（paraphrase 优先）
    - Type A/B: 优先 paraphrase
    - Hard 样本: 额外 paraphrase（因为 Hard 是瓶颈）
    - Medium 样本: 50% 概率提升为 Hard
    - Easy 样本: 保持原样，必要时 paraphrase

    Args:
        original: 原始数据集
        eval_questions: eval 问题集合
        target_distribution: 目标难度分布 {"easy": 0.30, "medium": 0.35, "hard": 0.35}
        max_per_failure_type: 每类 failure_type 最多生成的增强样本数

    Returns:
        增强后的完整数据集（原始 + 新增）
    """
    # ── 统计原始分布 ──────────────────────────────────────────────────
    total = len(original)
    ft_counts = Counter(s.get("failure_type", "N/A") for s in original)
    diff_counts = Counter(s.get("difficulty", "N/A") for s in original)

    print(f"原始数据分布:")
    print(f"  总数: {total}")
    print(f"  难度: {dict(sorted(diff_counts.items()))}")
    print(f"  失败类型: {dict(sorted(ft_counts.items()))}")

    # ── 计算需要生成的增强样本数 ──────────────────────────────────────
    # 目标: 约 700-750 条
    target_total = int(total * 1.4)  # 增加 40%
    target_hard = int(target_total * target_distribution["hard"])
    target_medium = int(target_total * target_distribution["medium"])
    target_easy = target_total - target_hard - target_medium

    current_hard = diff_counts.get("hard", 0)
    current_medium = diff_counts.get("medium", 0)
    current_easy = diff_counts.get("easy", 0)

    # ── 按 failure_type 分配增强配额 ─────────────────────────────────
    # Type E 最需要增强（Hard 瓶颈）
    type_e_samples = [s for s in original if s.get("failure_type") == "Type E"]
    type_d_samples = [s for s in original if s.get("failure_type") == "Type D"]
    type_c_samples = [s for s in original if s.get("failure_type") == "Type C"]
    other_samples = [s for s in original if s.get("failure_type") in ("Type A", "Type B")]

    augmented: list[dict] = []
    ft_aug_counts: Counter[str] = Counter()

    # Helper: 计算某类已生成的增强样本数
    def aug_count(ft: str) -> int:
        return ft_aug_counts.get(ft, 0)

    def can_augment(ft: str) -> bool:
        if max_per_failure_type is None:
            return True
        return aug_count(ft) < max_per_failure_type

    _seed(42)

    # ── Phase 1: Type E 增强（每个生成 2 个变体）─────────────────────
    for sample in type_e_samples:
        if not can_augment("Type E"):
            break
        variants = _augment_sample(
            sample, eval_questions,
            add_paraphrase=True,
            make_harder=(sample.get("difficulty") == "medium"),
        )
        for v in variants[:2]:  # 最多 2 个
            if can_augment("Type E"):
                augmented.append(v)
                ft_aug_counts["Type E"] += 1

    # ── Phase 2: Type D/C 增强 ────────────────────────────────────────
    for sample in type_d_samples + type_c_samples:
        ft = sample.get("failure_type", "N/A")
        if not can_augment(ft):
            continue
        variants = _augment_sample(
            sample, eval_questions,
            add_paraphrase=True,
            make_harder=(sample.get("difficulty") == "medium"),
        )
        for v in variants[:1]:  # 最多 1 个
            if can_augment(ft):
                augmented.append(v)
                ft_aug_counts[ft] += 1

    # ── Phase 3: Type A/B 增强（仅 paraphrase）───────────────────────
    for sample in other_samples:
        ft = sample.get("failure_type", "N/A")
        if not can_augment(ft):
            continue
        variants = _augment_sample(
            sample, eval_questions,
            add_paraphrase=True,
            make_harder=False,
        )
        for v in variants[:1]:  # 最多 1 个
            if can_augment(ft):
                augmented.append(v)
                ft_aug_counts[ft] += 1

    # ── Phase 4: Hard 样本额外 paraphrase ────────────────────────────
    hard_samples = [s for s in original if s.get("difficulty") == "hard"]
    extra_hard = [s for s in hard_samples if s not in type_e_samples]
    for sample in extra_hard[:20]:  # 额外 20 个 Hard paraphrase
        ft = sample.get("failure_type", "N/A")
        variants = _augment_sample(
            sample, eval_questions,
            add_paraphrase=True,
            make_harder=False,
        )
        for v in variants[:1]:
            if can_augment(ft):
                augmented.append(v)
                ft_aug_counts[ft] += 1

    # ── 组装完整数据集 ────────────────────────────────────────────────
    full_dataset = list(original) + augmented

    # ── 最终统计 ──────────────────────────────────────────────────────
    final_total = len(full_dataset)
    final_diff = Counter(s.get("difficulty", "N/A") for s in full_dataset)
    final_ft = Counter(s.get("failure_type", "N/A") for s in full_dataset)
    verified = Counter(s.get("verified", "N/A") for s in full_dataset)

    print(f"\n增强后数据分布:")
    print(f"  总数: {final_total} (+{len(augmented)} 条新样本)")
    print(f"  难度: {dict(sorted(final_diff.items()))}")
    print(f"  失败类型: {dict(sorted(final_ft.items()))}")
    print(f"  verified: {dict(verified)}")

    hard_pct = final_diff.get("hard", 0) / final_total * 100
    med_pct = final_diff.get("medium", 0) / final_total * 100
    easy_pct = final_diff.get("easy", 0) / final_total * 100
    print(f"  难度占比: Easy={easy_pct:.1f}% Medium={med_pct:.1f}% Hard={hard_pct:.1f}%")
    print(f"  目标分布: Easy=30% Medium=35% Hard=35%")

    # ── 警告 ─────────────────────────────────────────────────────────
    if hard_pct < 30:
        print(f"\n[WARNING] Hard 占比 {hard_pct:.1f}% 低于目标 35%")
    if easy_pct > 35:
        print(f"\n[WARNING] Easy 占比 {easy_pct:.1f}% 高于目标 30%")

    return full_dataset


# ─── CLI ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="微调数据增强：paraphrase + 难度调整，保持 ground_truth 不变。",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_ROOT / "data/finetune_dataset_500_strict.jsonl",
        help="原始 finetune 数据路径",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "data/finetune_dataset_augmented.jsonl",
        help="增强后数据输出路径",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help="每个样本最多生成的变体数量（默认 1）",
    )
    parser.add_argument(
        "--augment-hard-only",
        action="store_true",
        help="仅对 Hard 样本进行增强",
    )
    parser.add_argument(
        "--max-per-failure-type",
        type=int,
        default=None,
        help="每个 failure_type 最多生成的增强样本数",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="随机种子（用于复现）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅分析，不生成数据",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    _seed(args.seed)

    # 加载 eval_questions（用于去重）
    eval_questions = _load_eval_questions()
    print(f"Loaded {len(eval_questions)} eval questions (用于去重)")

    # 加载原始数据
    original = _load_finetune_data(args.input)
    print(f"Loaded {len(original)} original samples from {args.input}")

    # 目标分布
    target_dist = {"easy": 0.30, "medium": 0.35, "hard": 0.35}

    if args.augment_hard_only:
        # 仅对 Hard 样本增强
        hard_samples = [s for s in original if s.get("difficulty") == "hard"]
        print(f"Hard-only mode: {len(hard_samples)} hard samples")

        augmented: list[dict] = []
        for sample in hard_samples:
            variants = _augment_sample(sample, eval_questions, add_paraphrase=True, make_harder=False)
            augmented.extend(variants[: args.trials])

        full_dataset = list(original) + augmented
    else:
        # 完整增强流程
        full_dataset = _build_augmented_dataset(
            original=original,
            eval_questions=eval_questions,
            target_distribution=target_dist,
            max_per_failure_type=args.max_per_failure_type,
        )

    if args.dry_run:
        print("\n[DRY RUN] 数据未写入文件")
        return 0

    # 写入输出文件
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for sample in full_dataset:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"\n写入 {len(full_dataset)} 条样本到 {args.output}")

    # 写入元数据
    meta_path = args.output.with_suffix(".meta.json")
    meta = {
        "original_count": len(original),
        "augmented_count": len(full_dataset) - len(original),
        "total_count": len(full_dataset),
        "seed": args.seed,
        "target_distribution": target_dist,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"元数据写入 {meta_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
