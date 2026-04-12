# 完整评测对比表格

生成时间: 2026-04-12 23:10
评测数据集: `data/eval_cases.json` (120 cases: 15 Easy, 23 Medium, 82 Hard, 40 Type E)

> **数据集更新 (2026-04-12)**: eval_cases 从 102 扩展至 120，新增 18 条 Hard 盲区用例。以下表格中历史策略数据仍基于 54-case strict run，新策略评测待重新运行后更新。

---

## 评测集结构 (120 cases)

### 按难度分布

| 难度 | 数量 | 占比 | 说明 |
|------|------|------|------|
| Easy | 15 | 12.5% | 基础 FQN 查找，单一跳转到明确 symbol |
| Medium | 23 | 19.2% | 简单多跳或 Type B/C 基础场景 |
| Hard | 82 | 68.3% | 复杂多跳、Type A 生命周期、Type E 运行时解析 |

### 按失败类型分布

| 失败类型 | 数量 | 占比 | 核心场景 |
|----------|------|------|----------|
| Type A | 19 | 15.8% | bootstep 生命周期 include_if / 条件初始化 |
| Type B | 19 | 15.8% | 注册链追踪、register_type 多态派发 |
| Type C | 18 | 15.0% | __all__ re-export 链追踪 |
| Type D | 24 | 20.0% | 参数/类 shadowing、crontab_parser 边界条件 |
| Type E | 40 | 33.3% | symbol_by_name 多跳运行时解析、字符串别名懒解析 |

### 新增 Hard 盲区用例 (18 条)

覆盖以下未被旧评测集覆盖的场景:

- `celery/bin/celery.py`: CLI entry_points autodiscover (Type E)
- `celery/canvas.py`: chain.__new__ reduce(operator.or_) 多态派发 (Type D)
- `celery/canvas.py`: group.__or__ chord 自动升级 + _chord.__init__ 反序列化 (Type D)
- `celery/schedules.py`: crontab_parser._expand_range wrap-around 跨天逻辑 (Type D)
- `celery/canvas.py`: _prepare_chain_from_options ChainMap 不可变保护 (Type D)
- `celery/result.py`: GroupResult 嵌套反序列化 + parent linking (Type C)
- `celery/canvas.py`: StampingVisitor 递归 stamp_links 遍历 (Type A)
- `celery/canvas.py`: Signature.flatten_links 递归回调收集 (Type B)
- `celery/canvas.py`: _chord.__init__ _maybe_group + maybe_signature 双重多态 (Type B)
- `celery/serialization.py`: UnpickleableExceptionWrapper roundtrip fidelity (Type E)
- `celery/utils/serialization.py`: raise_with_context 异常链保留 (Type C)

---

## HybridRetrieverWithPath Pattern Fix (102-case eval)

> 数据来源: `results/hybrid_with_path_metrics_v2.json`

| 失败类型 | 原正确率 | +Pattern Fix | 提升 | 样本数 |
|----------|----------|--------------|------|--------|
| Type A | 0.0% | **75.0%** | +75.0pp | 16 |
| Type B | 0.0% | **73.3%** | +73.3pp | 15 |
| Type C | 0.0% | **80.0%** | +80.0pp | 15 |
| Type D | 55.0% | **95.0%** | +40.0pp | 20 |
| Type E | 66.7% | **88.9%** | +22.2pp | 36 |
| **Overall** | **34.3%** | **84.3%** | **+50.0pp** | **102** |

### Top-5 检索 Recall 对比 (HybridRetrieverWithPath)

| 失败类型 | 原始 Recall | +Path Indexer | 样本数 |
|----------|-------------|---------------|--------|
| Type A | 0.3857 | 0.3857 | 16 |
| Type B | 0.1635 | 0.1635 | 15 |
| Type C | 0.5111 | 0.5111 | 15 |
| Type D | 0.4235 | 0.4235 | 20 |
| Type E | 0.2485 | **0.3230** | 36 |

> 检索权重: BM25=0.33, Semantic=0.33, Graph=0.34

---

## 微调数据集质量报告

> 数据来源: `scripts/rebuild_finetune_dataset.py` 输出 `data/finetune_dataset_120_strict.jsonl`

### 数据集规模

| 指标 | 值 | 质量门 |
|------|-----|--------|
| 总记录数 | **531** | >= 500 [OK] |
| 新增变体 | 33 | - |
| Type E 补充 | 5 | - |
| 移除重叠 | 4 | - |

### 难度分布

| 难度 | 数量 | 占比 | 目标 | 状态 |
|------|------|------|------|------|
| Easy | 168 | 31.6% | <= 35% | [OK] |
| Medium | 173 | 32.6% | - | - |
| Hard | 190 | **35.8%** | >= 35% | [OK] |

### 失败类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
| Type A | 107 | 20.2% |
| Type B | 122 | 23.0% |
| Type C | 94 | 17.7% |
| Type D | 95 | 17.9% |
| Type E | 113 | **21.3%** |

### FQN 验证

- 原始数据重叠 (exact GT): **0 条**
- 问句相似度重叠 (>80%): **4 条** (已过滤)
- FQN 验证错误: **0 条**

---

## 历史策略评测 (54-case strict run)

## Union F1 Score (Primary Metric)

| Strategy | Description | Easy | Medium | Hard | **Overall** | Δ Baseline | Source |
|---|---|---|---|---|---|---|---|
| GPT-5.4 PE | GPT-5.4 + Fewshot + Postprocess | 0.6651 | 0.6165 | 0.5522 | **0.6062** | +0.5692 | summary.json |
| Qwen PE + RAG + FT | 完整策略：Qwen + PE + RAG + Fine-tuned | 0.4985 | 0.4805 | 0.3672 | **0.4435** | +0.4065 | summary.json |
| Qwen PE + FT | Qwen + PE + Fine-tuned | 0.5233 | 0.5370 | 0.2624 | **0.4315** | +0.3945 | summary.json |
| GPT-5.4 Baseline | GPT-5.4 无 PE 无 RAG | 0.4348 | 0.2188 | 0.2261 | **0.2815** | +0.2445 | summary.json |
| Qwen PE | Qwen + PE (Fewshot + Postprocess) | 0.3167 | 0.2491 | 0.1323 | **0.2246** | +0.1876 | summary.json |
| Qwen PE + RAG | Qwen + PE + RAG | 0.1514 | 0.2614 | 0.0523 | **0.1534** | +0.1164 | summary.json |
| GLM-5 Baseline | GLM-5 无 PE 无 RAG | 0.1048 | 0.0681 | 0.0367 | **0.0666** | +0.0296 | summary.json |
| Qwen Baseline | Qwen3-9B 无 PE 无 RAG | 0.0667 | 0.0526 | 0.0000 | **0.0370** | +0.0000 | summary.json |
| Qwen RAG | Qwen + RAG (无 PE) | 0.0667 | 0.0000 | 0.0000 | **0.0185** | -0.0185 | summary.json |

## Macro F1 Score (Per-Layer Quality)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 0.5670 | 0.3018 | 0.2482 | **0.3556** |
| Qwen PE + RAG + FT | 0.3648 | 0.3561 | 0.2473 | **0.3182** |
| Qwen PE + FT | 0.4141 | 0.4237 | 0.2059 | **0.3404** |
| GPT-5.4 Baseline | 0.2859 | 0.1316 | 0.1065 | **0.1652** |
| Qwen PE | 0.2185 | 0.2117 | 0.0944 | **0.1702** |
| Qwen PE + RAG | 0.1185 | 0.2281 | 0.0381 | **0.1273** |
| GLM-5 Baseline | 0.1000 | 0.0333 | 0.0000 | **0.0395** |
| Qwen Baseline | 0.0667 | 0.0526 | 0.0000 | **0.0370** |
| Qwen RAG | 0.0667 | 0.0000 | 0.0000 | **0.0185** |

## Direct Dependency F1 (Easiest Layer)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 0.6689 | 0.4579 | 0.3627 | **0.4812** |
| Qwen PE + RAG + FT | 0.7444 | 0.6491 | 0.4783 | **0.6123** |
| Qwen PE + FT | 0.6444 | 0.5877 | 0.3333 | **0.5093** |
| GPT-5.4 Baseline | 0.5578 | 0.2281 | 0.1779 | **0.3011** |
| Qwen PE | 0.3778 | 0.3509 | 0.1833 | **0.2963** |
| Qwen PE + RAG | 0.3111 | 0.3509 | 0.0500 | **0.2284** |
| GLM-5 Baseline | 0.1000 | 0.0526 | 0.0000 | **0.0463** |
| Qwen Baseline | 0.0667 | 0.0526 | 0.0000 | **0.0370** |
| Qwen RAG | 0.0667 | 0.0000 | 0.0000 | **0.0185** |

## Per-Failure-Type Breakdown (Overall Union F1)

| Strategy | Type A | Type C | Type E | Type D | Type B |
|---|---|---|---|---|---|
| GPT-5.4 PE | 0.5133 | 0.5502 | 0.7394 | 0.6159 | 0.5801 |
| Qwen PE + RAG + FT | 0.3391 | 0.2571 | 0.5424 | 0.5258 | 0.4695 |
| Qwen PE + FT | 0.0406 | 0.4361 | 0.6717 | 0.5579 | 0.3479 |
| GPT-5.4 Baseline | N/A | N/A | N/A | N/A | N/A |
| Qwen PE | 0.0000 | 0.1868 | 0.4394 | 0.3030 | 0.1425 |
| Qwen PE + RAG | 0.0714 | 0.0000 | 0.1792 | 0.1273 | 0.2758 |
| GLM-5 Baseline | N/A | N/A | N/A | N/A | N/A |
| Qwen Baseline | 0.0000 | 0.0000 | 0.0909 | 0.0000 | 0.0625 |
| Qwen RAG | 0.0000 | 0.0000 | 0.0909 | 0.0000 | 0.0000 |

## Mislayer Rate (Lower is Better)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 10.0% | 33.2% | 43.0% | **30.4%** |
| Qwen PE + RAG + FT | 10.0% | 20.5% | 32.5% | **22.0%** |
| Qwen PE + FT | 10.0% | 17.0% | 11.7% | **13.1%** |
| GPT-5.4 Baseline | 16.7% | 20.2% | 21.1% | **19.5%** |
| Qwen PE | 10.0% | 5.3% | 8.3% | **7.7%** |
| Qwen PE + RAG | 6.7% | 1.8% | 3.3% | **3.7%** |
| GLM-5 Baseline | 0.0% | 5.3% | 10.0% | **5.6%** |
| Qwen Baseline | 0.0% | 0.0% | 0.0% | **0.0%** |
| Qwen RAG | 0.0% | 0.0% | 0.0% | **0.0%** |

## 评测结论

### 最佳策略
- **GPT-5.4 PE**: Overall=0.6062, Macro=0.3556, Hard=0.5522

### Hard 场景瓶颈
- GPT-5.4 PE: Hard F1=0.5522
- Qwen PE + RAG + FT: Hard F1=0.3672
- Qwen PE + FT: Hard F1=0.2624

### 下一步行动建议
1. **Hard 场景严重不足**（多数策略 F1<0.1），Type E 是核心瓶颈
2. 建议: 增加 RAG Type E 专项优化 + 增强微调数据覆盖
