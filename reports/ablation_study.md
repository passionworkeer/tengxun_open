# Ablation Study

## 实验矩阵（10 组）

统一指标：`Easy F1` | `Medium F1` | `Hard F1` | `Avg F1` | `单次 Token 消耗`

| 实验组 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token 消耗 | 核心验证目的 |
|--------|---------|-----------|---------|--------|-----------|------------|
| Baseline (GPT-4o) | TBD | TBD | TBD | TBD | 基准 | 商业模型零样本上限 |
| Baseline (GLM-5) | TBD | TBD | TBD | TBD | 基准 | 开源最强模型零样本上限 |
| Baseline (Qwen2.5-Coder-7B) | TBD | TBD | TBD | TBD | 基准 | 微调基座未优化水平 |
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
| 向量检索 only | TBD | TBD | 基准 |
| BM25 only | TBD | TBD | 函数名精确匹配场景 |
| 图索引 only | TBD | TBD | 静态依赖覆盖范围 |
| 向量 + BM25 RRF | TBD | TBD | 双路融合 |
| **三路 RRF（本方案）** | TBD | TBD | 预期最优 |
| Text Chunking vs AST Chunking | TBD | TBD | 分块策略对比 |

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
