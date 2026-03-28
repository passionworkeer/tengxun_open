# Strict PE Search Addendum (2026-03-29)

## Goal

在 strict 口径下继续搜索 GPT-5.4 的 PE 最优策略，目标不是只抬 `union F1`，而是同时抬 `active-layer macro F1` 并压低 `mislayer rate`。

本轮实验全部基于：

- `54` 条手工标注评测集：`data/eval_cases.json`
- `20` 条 strict few-shot：`data/fewshot_examples_20_strict.json`
- GPT-5.4，`https://ai.td.ee/v1`
- 分支：`codex/strict-pe-search`

## 先做的底座修复

在搜索新 prompt 之前，先修了两类会白白丢分的工程问题：

1. `canonicalization`
   - 统一 `: / :: .py` 等路径写法到 dotted FQN。
   - 相关代码：`evaluation/metrics.py`、`pe/post_processor.py`

2. `layer-preserving postprocess`
   - 优先解析模型原始 JSON 里的 `direct / indirect / implicit` 三层。
   - 只有解析失败时，才退回扁平抽取。
   - 相关代码：`scripts/run_pe_eval.py`、`pe/post_processor.py`

这两步修完后，历史 strict replay 已经从：

| Variant | Union | Macro | MisLayer | Exact Layer |
|---|---:|---:|---:|---:|
| `fewshot` | 0.5460 | 0.4035 | 0.1679 | 0.0741 |
| `fewshot + canonicalization` | 0.5722 | 0.4282 | 0.1667 | 0.0741 |
| `postprocess (layer-preserving)` | 0.6136 | 0.4372 | 0.2336 | 0.1111 |

结果文件：

- `results/pe_eval_strict_replay_20260329/pe_fewshot_strict.json`
- `results/pe_eval_strict_search_20260329/pe_fewshot_canonical_strict.json`
- `results/pe_eval_strict_search_20260329/pe_postprocess_layered_strict.json`

## Prompt Search Matrix

### Step 1: 12 条错层敏感 case smoke

先用 `12` 条最容易暴露错层问题的 case 做 smoke，避免把 API 浪费在明显退化的变体上。

Smoke 结果：

| Variant | Union | Macro | MisLayer | 结论 |
|---|---:|---:|---:|---|
| `fewshot` | 0.5667 | 0.2987 | 0.4167 | 基线 |
| `postprocess` | 0.5972 | 0.3441 | 0.4167 | 可继续 |
| `fewshot_layer_guard` | 0.5011 | 0.1579 | 0.5000 | 淘汰 |
| `fewshot_assistant` | 0.3553 | 0.1111 | 0.4583 | 淘汰 |
| `postprocess_layer_guard` | 0.4214 | 0.0960 | 0.4445 | 淘汰 |
| `postprocess_assistant` | 0.3847 | 0.1265 | 0.4028 | 淘汰 |
| `fewshot_targeted` | 0.5543 | 0.3602 | 0.3333 | 晋级 |
| `postprocess_targeted` | 0.5984 | 0.3163 | 0.3750 | 晋级，但优先级次于 `fewshot_targeted` |

结果文件：

- `results/pe_smoke_targeted_20260329/pe_summary.json`
- `results/pe_smoke_targeted2_20260329/pe_summary.json`

### Step 2: 54 条全量重跑

对通过 smoke 的 targeted 路线做 `54` 条全量重跑，并与已经存在的 full-run 变体一起比较。

| Variant | Union | Macro | MisLayer | Exact Layer |
|---|---:|---:|---:|---:|
| `fewshot + canonicalization` | 0.5722 | 0.4282 | 0.1667 | 0.0741 |
| `postprocess (layer-preserving)` | 0.6136 | 0.4372 | 0.2336 | 0.1111 |
| `fewshot_layer_guard` | 0.5910 | 0.3408 | 0.3889 | - |
| `fewshot_assistant` | 0.5696 | 0.2581 | 0.4938 | - |
| `postprocess_layer_guard` | 0.5882 | 0.3286 | 0.4256 | - |
| `postprocess_assistant` | 0.6093 | 0.3205 | 0.4611 | - |
| `fewshot_targeted` | 0.6061 | 0.4373 | 0.1873 | 0.0741 |
| `postprocess_targeted` | 0.6338 | 0.4757 | 0.1620 | 0.1296 |

对应结果文件：

- `results/pe_eval_strict_search_round2_20260329/pe_summary.json`
- `results/pe_targeted_full_20260329/pe_fewshot_targeted_strict.json`
- `results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json`

## What Actually Worked

### 1. 强规则 prompt 不是最优方向

`layer_guard` 系列看起来更“严谨”，但实际会把模型推向过度保守或过度模式化，导致：

- `macro` 明显下降
- `mislayer` 变高
- easy case 出现不必要的归零

也就是说，问题不是“规则写得不够狠”，而是“模型已经有基本层级能力，真正缺的是对易错 failure mode 的针对性示范”。

### 2. assistant few-shot 形式单独看也不够好

把 few-shot 改成 `user -> assistant JSON` 对话对，单独看没有带来增益，反而在本任务上明显退化。说明这里的关键不是消息角色本身，而是 few-shot 的内容选择。

### 3. 真正有效的是 targeted few-shot selection

`fewshot_targeted` 的做法不是改模型规则，而是改 few-shot 的召回策略：

- 对 `shared_task / finalize / proxy / pending` 一类问题，固定注入 `Type B` anchor
- 对 `symbol_by_name / loader / backend / fixup / string import` 一类问题，固定注入 `Type E` anchor
- 对 `worker / cli / current_app` 一类问题，补 `Type A` anchor
- 再用剩余槽位做动态相似 few-shot

这个策略直接解决了原始 few-shot 最大的问题：词面相似不等于 failure mode 相似。

### 4. 最优策略是 `targeted few-shot + layer-preserving postprocess`

最终最优是：

- `postprocess_targeted`
- `Union = 0.6338`
- `Macro = 0.4757`
- `MisLayer = 0.1620`

它同时超过了此前 strict-best 的 `postprocess (layer-preserving)`：

- `union: 0.6136 -> 0.6338` (`+0.0202`)
- `macro: 0.4372 -> 0.4757` (`+0.0385`)
- `mislayer: 0.2336 -> 0.1620` (`-0.0716`)
- `exact layer match: 0.1111 -> 0.1296`

这说明 targeted few-shot 不是只抬了并集命中，而是真的改善了层级归位。

## Recommendation

如果导师问“现在最推荐的 GPT PE 方案是什么”，回答应当是：

1. **Best overall**: `postprocess_targeted`
   - 适合追求最终分数
   - strict 三项都最好

2. **Best prompt-only**: `fewshot_targeted`
   - 如果想强调“即使不依赖后处理，也有强增益”
   - `macro` 已经追平旧 strict-best

3. **不推荐继续投入的方向**
   - 更强的 layer guard system prompt
   - assistant few-shot 改写
   - 这两条线都已经有 full-run 反证

## GLM Stability Note

这一轮也补测了 Zhipu 官方 `glm-5` 的 `thinking` 路线，结论是：

- 官方 `thinking + stream` smoke 在首个 case 长时间无结果落盘，最终手动中断
- 官方 `thinking + non-stream` smoke 同样在首个 case 阻塞，未形成可复验结果文件

因此正式口径里不建议把 GLM `thinking` 模式纳入主实验矩阵。更稳妥的写法是：

- 保留已有稳定 GLM strict baseline：`results/glm_eval_strict_replay_20260329_strict.json`
- 将 `thinking` 记为“已尝试但因 endpoint 稳定性不足未纳入正式对比”的探索路径

## Repro Commands

```bash
# 12-case smoke
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 scripts/run_pe_eval.py \
  --api-key "<api-key>" \
  --base-url https://ai.td.ee/v1 \
  --model gpt-5.4 \
  --variants fewshot,postprocess,fewshot_layer_guard,fewshot_assistant,postprocess_layer_guard,postprocess_assistant \
  --case-ids celery_hard_024,celery_hard_122,celery_type_d_005,celery_easy_021,celery_hard_025,celery_type_a_003,celery_medium_023,celery_medium_025,celery_hard_018,celery_hard_019,celery_type_d_006,celery_medium_021 \
  --output-dir results/pe_smoke_targeted_20260329

# targeted smoke
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 scripts/run_pe_eval.py \
  --api-key "<api-key>" \
  --base-url https://ai.td.ee/v1 \
  --model gpt-5.4 \
  --variants fewshot_targeted,postprocess_targeted \
  --case-ids celery_hard_024,celery_hard_122,celery_type_d_005,celery_easy_021,celery_hard_025,celery_type_a_003,celery_medium_023,celery_medium_025,celery_hard_018,celery_hard_019,celery_type_d_006,celery_medium_021 \
  --output-dir results/pe_smoke_targeted2_20260329

# 54-case full run
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 scripts/run_pe_eval.py \
  --api-key "<api-key>" \
  --base-url https://ai.td.ee/v1 \
  --model gpt-5.4 \
  --variants fewshot_targeted,postprocess_targeted \
  --output-dir results/pe_targeted_full_20260329
```
