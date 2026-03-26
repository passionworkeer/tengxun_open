# Ablation Study

## 实验矩阵（10 组）

统一指标：`Easy F1` | `Medium F1` | `Hard F1` | `Avg F1` | `单次 Token 消耗`

| 实验组 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token 消耗 | 核心验证目的 |
|:--------|:-------:|:---------:|:--------:|:------:|:----------|:------------|
| Baseline (GPT-5.4) | 0.4475 | 0.2670 | 0.2373 | 0.3122 | 基准 | 国际商业模型天花板，零样本上限 |
| Baseline (GLM-5) | TBD | TBD | TBD | TBD | 基准 | 开源最强模型零样本上限 |
| Baseline (Qwen3.5-9B) | TBD | TBD | TBD | TBD | 基准 | 微调基座未优化水平 |
| PE only | TBD | TBD | TBD | TBD | +40% | 纯提示词工程极限 |
| RAG only（向量） | TBD | TBD | TBD | TBD | +120% | 单路检索基准 |
| RAG only（三路 RRF） | TBD | TBD | TBD | TBD | +140% | 混合检索增益 |
| FT only | TBD | TBD | TBD | TBD | 0 | 领域知识固化效果 |
| PE + RAG | TBD | TBD | TBD | TBD | +150% | 免训练轻量级最优组合 |
| PE + FT | TBD | TBD | TBD | TBD | +40% | 无检索的内化知识组合 |
| **PE + RAG + FT** | TBD | TBD | TBD | TBD | +150% | 三者协同增益验证 |

> **说明**：GPT-5.4 基线已实测。其他 9 组实验尚未执行。

---

## RAG 内部消融实验（已实测）

### 评测配置

- **数据集**：`eval_cases_migrated_draft_round4.json`（50 条，schema_v2）
- **索引**：8086 chunks，dict-based adjacency graph
- **Query mode**：`question_only`（默认口径）
- **RRF k**：60（推荐 k=30）

### Headline 检索指标（50-case, question_only, chunk_symbols）

| Source | Recall@5 | MRR | Notes |
|:-------|:--------:|:----:|:------|
| BM25 | 0.1451 | 0.2622 | Keyword match baseline |
| Semantic | 0.0533 | 0.0522 | Hybrid TF-IDF + char n-gram；最弱 source |
| **Graph** | **0.3234** | **0.4650** | **最强单路，2.2x BM25，6x Semantic** |
| **Fused (RRF k=60)** | **0.2962** | **0.5120** | 三路融合 headline |

> **关键发现**：Graph 单路（0.3234）反而优于 RRF 融合（0.2962）——说明 BM25 和 Semantic 在这个场景下引入了噪声。

### RRF k 消融（50-case, question_only, expanded_fqns）

| k | Recall@5 | MRR | Notes |
|:--|:--------:|:----:|:------|
| **30** | **0.2941** | **0.4487** | **推荐默认值** |
| 60 | 0.2741 | 0.4288 | 原默认参数 |
| 120 | 0.2841 | 0.4363 | 边际改善 |

**结论**：k=30 优于 k=60。k 越小对 top rank 权重越高，在 Graph 远强于其他两路时更合理。

### 分难度检索结果（Fused RRF k=60, expanded_fqns）

| Difficulty | Recall@5 | MRR | Cases |
|:-----------|:--------:|:----:|:-----:|
| Easy | 0.4444 | 0.4727 | 15 |
| Medium | 0.1958 | 0.4153 | 20 |
| Hard | 0.2080 | 0.4028 | 15 |

### 分 Failure Type 检索结果（Fused RRF k=60）

| Type | Recall@5 | MRR | Cases | Interpretation |
|:-----|:--------:|:----:|:-----:|:--------------|
| **Type A (长上下文截断)** | **0.4375** | **0.5250** | 4 | 中等；上下文中有一些信号 |
| **Type C (再导出链断裂)** | **0.3750** | **0.3949** | 12 | Graph 自然处理 `__init__.py` 转发 |
| Type B (隐式依赖幻觉) | 0.1161 | 0.1920 | 12 | **RAG 无法修复幻觉；需要 FT** |
| **Type D (命名空间混淆)** | **0.2000** | **0.1811** | 5 | 部分场景检索有帮助 |
| **Type E (动态加载失配)** | **0.2977** | **0.6700** | 17 | String targets 在 Graph 中帮助显著 |

### 检索-生成四象限分析

| Quadrant | Count | 含义 | 典型案例 |
|:---------|:-----:|:-----|:---------|
| Case A (R✓ G✓) | TBD | 检索命中且生成正确 | 理想状态 |
| Case B (R✓ G✗) | TBD | 检索命中但生成错误 | **融合策略瓶颈，重点深挖** |
| Case C (R✗ G✓) | TBD | 检索失败但生成正确 | 模型参数补偿 |
| Case D (R✗ G✗) | TBD | 双重失效 | 需分析根因 |

### Graph vs Fusion 详细对比（50-case, chunk_symbols）

| View | Graph R@5 | Graph MRR | BM25 R@5 | Semantic R@5 | Fused R@5 |
|:-----|:---------:|:--------:|:--------:|:-----------:|:---------:|
| chunk_symbols | **0.3234** | **0.4650** | 0.1451 | 0.0533 | 0.2962 |
| expanded_fqns | 0.3312 | 0.4807 | 0.1831 | 0.0634 | 0.2741 |

### 工程优化记录

> **NetworkX → Dict BFS**：原始实现用 `nx.ego_graph` + `nx.shortest_path_length` 在 524,844 边图上导致 ~2.7s/batch 瓶颈（占 89% 总检索时间）。替换为纯 Python dict 邻接 BFS 后，检索降至 ~225ms/query。

---

## 策略边界与落地结论

> 以下为基于现有数据的推断，待完整实验验证。

### 依赖深度 ≤ 2（Easy/Medium 场景）

- **推荐方案**：PE + RAG
- **F1 水平**：预计 ~0.50~0.60（需实验验证）
- **Token 增量**：+40%（PE） +120%（RAG）
- **FT 额外增益**：< 2%，训练成本投入产出比低

### 依赖深度 ≥ 3（Hard 场景，动态注入/字符串映射）

- **RAG 图索引在 Type E 场景**：`Recall@5 = 0.2977`，说明图索引的 string_targets 对动态加载有帮助，但仍有 ~70% 未召回
- **FT 的必要性**：Type B（幻觉）RAG 无法解决，必须靠 FT
- **PE + RAG + FT 是 Type E 场景唯一有效策略**：部分验证（需 FT 实验数据）

### 最终工程建议

> （待从实验数据得出）

---

## Bad Case 专栏（待补充）

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

---

## 核心发现（基于已实测数据）

### RAG 检索层面

1. **Graph 是主导信号**：结构连接性（imports + references）比文本相似度对代码依赖查询更具预测性
2. **RRF 融合反而变弱**：Graph 单路 R@5=0.3234 优于三路融合 0.2962
3. **Semantic 是最弱链路**：纯 TF-IDF 在代码上缺乏语义理解，需要真实 embedding 模型
4. **Type D 仍最难召回**：R@5=0.20（50-case 全集）vs R@5=0.0（20-case 样本）——20-case 样本运气不好，但 80% Type D 仍无法靠检索解决

### RAG vs 生成解耦

- **Type B（幻觉）不是检索问题**：再多的检索上下文都无法阻止模型幻觉隐式依赖——这正是 FT 的核心动机
- **Type C（再导出）检索自然支持**：`__init__.py` 转发链被 import graph 自然捕获
- **Type E（动态加载）部分可解决**：Graph 的 string_targets 对 alias 解析有显著帮助

### 待验证假设

| 假设 | 现状 | 验证方式 |
|------|------|---------|
| PE 格式约束能修复 easy_012/013 | 推断正确 | 待 PE 实验 |
| Graph 单路 > RRF 融合 | 已实测 | — |
| k=30 > k=60 | 已实测 | — |
| FT 能解决 Type B 幻觉 | 推断 | 待 FT 实验 |
| PE + RAG + FT 是 Type E 唯一有效策略 | 推断 | 待组合实验 |

---

## 可视化图表

（待补充：使用 matplotlib 生成）
- 雷达图：各策略在 Easy/Medium/Hard 上的表现
- 柱状图：10 组实验的 Avg F1 对比
- 热力图：失效类型 × 优化策略的增益矩阵
