# 消融实验报告

这份报告只讨论“策略选择”问题：  
同一任务下，`PE / RAG / FT` 各自带来什么，组合后又意味着什么。

> 口径说明：当前仓库同时保留**历史正式完整 54-case 矩阵**和 **strict-clean replay**。  
> 现在 strict-clean 的 Qwen FT family 三条线都已完整落盘；主结论优先使用 strict-clean，历史正式结果保留为演进对照。

## 1. 实验口径

### 1.1 统一任务

- 任务：Celery 跨文件依赖分析
- 正式评测集：`data/eval_cases.json`
- 样本数：`54`
- 评分口径：FQN 级别精确匹配

### 1.2 说明

当前仓库已经具备完整的正式消融矩阵：

1. 商业模型基线与 GPT 侧 `PE / RAG`
2. 开源模型 Qwen 侧 `PE / RAG / FT / PE+RAG / PE+FT / All`

所以这份报告的重点不再是“还缺什么”，而是“完整矩阵说明了什么”。

## 2. 当前已完成的正式矩阵

| 策略 | Easy | Medium | Hard | Avg | 说明 |
|------|------:|------:|------:|------:|------|
| GPT-5.4 Baseline | 0.4348 | 0.2188 | 0.2261 | 0.2815 | 商业模型基线 |
| GLM-5 Baseline | 0.1048 | 0.0681 | 0.0367 | 0.0666 | 官方 API |
| Qwen3.5 Baseline | 0.0667 | 0.0526 | 0.0000 | 0.0370 | strict baseline recovered |
| GPT-5.4 PE only | 0.6651 | 0.6165 | 0.5522 | 0.6062 | 正式 54-case |
| GPT-5.4 RAG only | 0.2722 | 0.2656 | 0.3372 | 0.2940 | weighted RAG |
| Qwen PE only | 0.3167 | 0.2491 | 0.1323 | 0.2246 | 54-case 正式版 |
| Qwen RAG only | 0.0667 | 0.0000 | 0.0000 | 0.0185 | Google embedding |
| Qwen PE + RAG | 0.1514 | 0.2614 | 0.0523 | 0.1534 | Google embedding |
| Qwen FT only | 0.1556 | 0.0895 | 0.0500 | 0.0932 | strict-clean 54-case |
| Qwen PE + FT | 0.5307 | 0.4277 | 0.2393 | 0.3865 | strict-clean 54-case |
| Qwen PE + RAG + FT | 0.6168 | 0.5196 | 0.3986 | 0.5018 | strict-clean 54-case 最优 |

![模型基线对比](../img/final_delivery/01_model_baselines_20260328.png)

![Qwen 组合策略](../img/final_delivery/06_qwen_strategies_20260328.png)

### 2.1 跨模型口径说明

这份矩阵里有两种不同用途的对比：

1. `GPT-5.4` 与 `GLM-5` 的商业模型基线对比  
   这两者使用完全相同的 baseline prompt，都是单条 `user` 消息，因此横向比较是严格公平的。

2. `Qwen3.5-9B` 的内部消融矩阵  
   Qwen baseline 额外加入了一个最小化 `JSON-only system wrapper`，目的是让模型至少能输出可解析 JSON。即便在这个约束下，strict baseline 仍然只有 `0.0370`，且存在 `45/54` 的 parse failure。

因此：

- `Qwen` 的 baseline 更适合作为“开源模型在最低格式约束下的起点”
- `Qwen` 相关结论重点看同一模型内部的相对增益
- 不应把 `Qwen baseline` 与 `GPT/GLM baseline` 直接解释成完全同口径的绝对能力比较

## 3. 当前最重要的三条消融结论

### 3.1 PE 是最强的独立策略

在 GPT-5.4 上：

- `Baseline 0.2815`
- `PE only 0.6062`

这说明：

- 对强模型而言，Prompt 口径和输出约束就是第一生产力
- 如果预算有限，最先做的不是微调，也不是检索，而是把 PE 做对

### 3.2 Qwen 上 PE 是必要条件，RAG 单独几乎无效

在 Qwen 上：

- `Baseline 0.0370`
- `RAG only 0.0185`
- `PE only 0.2246`
- `FT only 0.0932`
- `PE + FT 0.3865`

这说明：

- `RAG only` 比 baseline 还差，说明检索上下文本身不会自动转化成正确 FQN 输出
- `PE only` 已经明显优于 `FT only`，说明输出约束与任务角色定义是开源模型的第一增益项
- 真正有生产价值的是 `PE + FT` 或 `PE + RAG + FT`，而不是单独 FT 或单独 RAG

### 3.3 strict-clean 最强完整路线已经变成 PE + RAG + FT，而 PE + FT 是低复杂度 strict-clean 路线

在 Qwen 上：

- strict-clean `PE + RAG + FT = 0.5018`
- strict-clean `PE + FT = 0.3865`
- 历史正式完整 `PE + FT = 0.4315`

这说明：

- strict-clean `PE + RAG + FT` 已经给出当前最强的完整开源结果
- strict-clean `PE + FT` 已经形成较低复杂度的完整路线
- 历史正式完整 `PE + FT` 仍可保留作演进对照，但不再是主表默认口径

还有一个必须解释的异常点：

- `Qwen PE + RAG = 0.1534`，反而低于 `Qwen PE only = 0.2246`
- 这说明未微调 Qwen 对检索上下文的利用能力不足，额外上下文更像噪声而不是增益
- 只有在加入 FT 后，模型才真正学会把检索到的跨文件线索转成稳定的 FQN 输出，因此 `PE + RAG + FT` 才成为完整矩阵里的最优解

## 4. 现阶段可以确认的策略边界

### 4.1 商业模型

当前最优路线非常明确：

- **GPT-5.4 + PE**

原因：

- 它已经给出全仓库最强正式分数 `0.6062`
- 成本远低于“全量 RAG + 更长上下文”
- 结论稳定、没有旧 embedding 版本依赖

### 4.2 开源模型

如果看当前仓库里的开源结果：

- **strict-clean 最强完整路线**：`Qwen PE + RAG + FT = 0.5018`
- **strict-clean 低复杂度路线**：`Qwen PE + FT = 0.3865`
- **历史正式完整高性价比参考**：`Qwen PE + FT = 0.4315`
- **PE 单独贡献**：`Qwen PE only = 0.2246`
- **RAG 单独贡献**：`Qwen RAG only = 0.0185`

### 4.3 策略适用边界

| 场景 | 推荐策略 | 原因 |
|------|------|------|
| easy / 简单 alias / 普通 re-export | PE | 收益最大、成本最低 |
| medium / 命名空间混淆 / 动态字符串 | PE + FT | 领域模式和输出约束更关键 |
| hard / bootstep / finalize / fixup | PE + RAG + FT | 需要检索和内化知识同时存在 |

## 5. 完整矩阵给出的策略排序

### 5.1 按平均分排序

Qwen 侧当前**完整结果**从高到低是：

1. `PE + RAG + FT = 0.5018`（strict-clean）
2. `PE + FT = 0.3865`（strict-clean）
3. `PE only = 0.2246`
4. `PE + RAG = 0.1534`
5. `FT only = 0.0932`（strict-clean）
6. `Baseline = 0.0370`
7. `RAG only = 0.0185`

### 5.2 这个排序说明了什么

- `PE` 是真正把模型拉出低分区的第一杠杆
- `FT` 没有 PE 时提升有限，但和 PE 组合后收益巨大
- `RAG` 对 Qwen 不是“可单独工作的模块”，而是需要和 `PE + FT` 协同

## 6. 当前最稳的项目级结论

### 6.1 如果导师现在就看结果

最稳的说法是：

1. 商业模型上界：`GPT-5.4 + PE = 0.6062`
2. 当前 strict-clean 开源最强完整路线：`Qwen PE + RAG + FT = 0.5018`
3. 当前 strict-clean 低复杂度路线：`Qwen PE + FT = 0.3865`
4. RAG 的主要价值：修 `hard / Type A / Type E`

### 6.2 现在已经能完整回答题目要求的策略矩阵

这份消融矩阵已经覆盖：

- `PE only / RAG only / FT only / PE+RAG / PE+FT / All`

也就是题目要求的完整策略组合。

## 7. 最终建议

### 7.1 现在就能落地的结论

- **默认商业模型方案**：`GPT-5.4 + PE`
- **默认开源模型方案**：strict-clean `Qwen PE + RAG + FT`
- **低复杂度参考方案**：strict-clean `Qwen PE + FT`
- **历史正式 `Qwen PE + FT = 0.4315`**：仅作演进对照

复现说明见：

- [`./qwen_strict_result_audit_20260329.md`](./qwen_strict_result_audit_20260329.md)

## 8. 结论

这轮消融已经足够明确三件事：

1. **PE 是最大贡献者**
2. **FT 的价值需要通过 PE 才能稳定释放**
3. **RAG 的价值是“选择性修复复杂场景”而不是“平均分万能药”**

当前矩阵已经闭环，后续工作重点不再是“补齐缺项”，而是围绕 hard case 做进一步优化。
