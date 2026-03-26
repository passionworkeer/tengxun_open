# Ablation Study

## 实验矩阵（10 组）

统一指标：`Easy F1` | `Medium F1` | `Hard F1` | `Avg F1` | `单次 Token 消耗`

| 实验组 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token 消耗 | 核心验证目的 |
|--------|---------|-----------|---------|--------|-----------|------------|
| Baseline (GPT-5.4) | TBD | TBD | TBD | TBD | 基准 | 国际商业模型天花板，零样本上限 |
| Baseline (GLM-5) | TBD | TBD | TBD | TBD | 基准 | 开源最强模型零样本上限 |
| Baseline (Qwen3.5-9B) | TBD | TBD | TBD | TBD | 基准 | 微调基座未优化水平 |
| PE only | TBD | TBD | TBD | TBD | +40% | 纯提示词工程极限 |
| RAG only（向量） | TBD | TBD | TBD | TBD | +120% | 单路检索基准 |
| RAG only（三路 RRF） | TBD | TBD | TBD | TBD | +140% | 混合检索增益 |
| FT only | TBD | TBD | TBD | TBD | 0 | 领域知识固化效果 |
| PE + RAG | TBD | TBD | TBD | TBD | +150% | 免训练轻量级最优组合 |
| PE + FT | TBD | TBD | TBD | TBD | +40% | 无检索的内化知识组合 |
| **PE + RAG + FT** | TBD | TBD | TBD | TBD | +150% | 三者协同增益验证 |

## RAG 内部消融实验

| 检索策略 | Recall@5 | MRR | 备注 |
|---------|---------|-----|------|
| 向量检索 only（`chunk_symbols`） | `0.1506` | `0.3131` | 32 条 round4 draft，`question_only` |
| BM25 only（`chunk_symbols`） | `0.1910` | `0.4143` | 32 条 round4 draft，`question_only` |
| 图索引 only（`chunk_symbols`） | `0.2823` | `0.5100` | 当前单路最强 |
| **三路 RRF（`chunk_symbols`, `question_only`）** | **`0.2962`** | **`0.5120`** | 当前 honest retrieval headline |
| 三路 RRF（`chunk_symbols`, `question_plus_entry`） | `0.2147` | `0.4969` | 对照实验；当前比 `question_only` 更差 |
| 三路 RRF（`expanded_fqns`） | `0.2140` | `0.4521` | 启发式扩展视图，不作为纯检索 headline |
| Text Chunking vs AST Chunking | TBD | TBD | 分块策略对比 |

> 注：当前 RAG 原型已把 `chunk_symbols` 与 `expanded_fqns` 两种口径拆开。后者会利用 imports / string targets / references 做候选扩展，因此不能再被写成“纯 retrieval”分数。
>
> 补充：`question_plus_entry` 在当前 round4 draft 上并没有带来 fused honest retrieval 增益，反而把 `chunk_symbols Recall@5` 从 `0.2962` 拉到 `0.2147`。现阶段默认口径仍应保持 `question_only`。

## 检索-生成四象限分析

| Quadrant | Count | Examples | Root Cause |
| :--- | :--- | :--- | :--- |
| Case A (R✓ G✓) | TBD | | 理想状态 |
| Case B (R✓ G✗) | TBD | | 融合策略瓶颈 ← 重点深挖 |
| Case C (R✗ G✓) | TBD | | 模型参数补偿（RAG 是否必要？） |
| Case D (R✗ G✗) | TBD | | 双重失效，分析根因 |

## 策略边界与落地结论

### 依赖深度 ≤ 2（Easy/Medium 场景）

- 推荐方案：
- F1 水平：
- Token 增量：
- FT 额外增益：

### 依赖深度 ≥ 3（Hard 场景，动态注入/字符串映射）

- 推荐方案：
- RAG 图索引在 Type E 场景表现：
- FT 的必要性：
- PE + RAG + FT 是 Type E 场景唯一有效策略：是/否

## 当前 RAG 快照

- 当前独立检索评测已能在 `32` 条 `schema_v2` round4 draft 上运行，见 `reports/rag_retrieval_eval_round4.md`。
- 当前 honest retrieval headline 是 `fused chunk_symbols Recall@5 = 0.2962 / MRR = 0.5120`。
- 当前 `question_plus_entry` 对照实验已补齐，但 fused `chunk_symbols` 下降到 `0.2147 / 0.4969`，因此不能当作默认查询口径。
- 当前最弱切片仍是 `Type D`；在 `fused chunk_symbols` 视图下，`Type D Recall@5 = 0.0000`。
- 这说明当前 RAG 原型最先补到的是结构链路型问题，而不是命名空间混淆问题。

### 最终工程建议

> （待从实验数据得出）

## Bad Case 专栏（必填 2-3 个典型案例）

### Bad Case 1: （待补充）

1. **原始问题**: （具体的依赖分析题目）
2. **Baseline 错误答案**: （模型给出了什么，含幻觉内容）
3. **失效归因**: 属于 Type A-E 中的哪一类，为什么会失败
4. **优化后答案**: （RAG / FT 如何纠正）
5. **纠正机理**: （为什么这个优化手段对这类失效有效）

### Bad Case 2: （待补充）

（同上格式）

### Bad Case 3: （待补充）

（同上格式）

## 可视化图表

（待补充：使用 matplotlib 生成）
- 雷达图：各策略在 Easy/Medium/Hard 上的表现
- 柱状图：10 组实验的 Avg F1 对比
- 热力图：失效类型 × 优化策略的增益矩阵
