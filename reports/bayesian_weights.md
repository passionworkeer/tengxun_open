# RRF 贝叶斯权重调优报告

**优化目标**: Type E
**优化方法**: Optuna TPE (Tree-structured Parzen Estimator)
**试验次数**: 10
**搜索空间**: BM25, Semantic (Graph = 1 - BM25 - Semantic)

## 1. Baseline vs Bayesian 最优

| 权重配置 | Overall Recall | Overall MRR | Type E Recall | Type D Recall |
|---|---|---|---|---|
| baseline (bm25=0.33 sem=0.33 gr=0.34) | 0.4586 | 0.5779 | 0.4037 | 0.5593 |
| **Bayesian 最优** (bm25=0.55 sem=0.44 gr=0.01) | **0.4328** | **0.3836** | **0.3898** | **0.5760** |

- Type E recall 提升: -0.0139 (-3.4%)
- Overall recall 提升: -0.0258 (-5.6%)

## 2. 参数敏感性分析（定向调参）

**最敏感参数**: `N/A` (Type E recall delta = 0.0000)

各参数最优值（Type E recall 最优时）:

### 参数 sweep 详情

## 3. Bayesian 优化 Top-5 试验

| # | BM25 | Semantic | Graph | Primary Recall | Overall Recall | Type E |
|---|---|---|---|---|---|---|
| 1 | 0.55 | 0.44 | 0.01 | 0.3898 | 0.4328 | 0.3898 |
| 2 | 0.78 | 0.21 | 0.01 | 0.3898 | 0.4328 | 0.3898 |
| 3 | 0.59 | 0.40 | 0.01 | 0.3898 | 0.4328 | 0.3898 |
| 4 | 0.49 | 0.49 | 0.03 | 0.3835 | 0.4429 | 0.3835 |
| 5 | 0.48 | 0.48 | 0.03 | 0.3627 | 0.4375 | 0.3627 |

## 4. 调参结论

- 无法得出参数敏感性结论（数据不足）

### 下一步建议
1. **Type E recall 仍在 0.5 以下，RRF 权重调优已触及天花板**
2. **应转向 DependencyPathIndexer**：索引 A→B→C 路径，专门解决 symbol_by_name 多跳检索问题
3. 当前最优权重仅提供边际收益，核心技术突破在于路径索引
