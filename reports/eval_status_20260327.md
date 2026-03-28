# 评测状态报告

## GPT-5.4

- 结果文件：`results/gpt5_eval_results.json`
- 样本数：`54`
- 平均 F1：`0.2815`
- Pass Rate：`55.6%`
- F1=0 数量：`24`

| Difficulty | Cases | Avg F1 |
|------------|-------|--------|
| easy | 15 | 0.4348 |
| medium | 19 | 0.2188 |
| hard | 20 | 0.2261 |

## GLM-5

- 结果文件：`results/glm_eval_results.json`
- 当前已落盘 case：`1`
- 响应模型：`ZhipuAI/GLM-5`
- 已验证 sample：`easy_001` / F1=`0.0000`
- 状态：`2026-03-27` 当天 ModelScope 对 `ZhipuAI/GLM-5` 返回日配额耗尽，无法继续完成 54 条正式重跑。

## RAG

- 检索报告：`artifacts/rag/eval_v2_54cases_20260327.json`
- Embedding 缓存：`artifacts/rag/embeddings_cache.json`
- 缓存覆盖：`6571/8086` (`81.3%`)
- Query mode：`question_plus_entry`
- RRF k：`30`

| View | Recall@5 | MRR |
|------|----------|-----|
| fused chunk_symbols | 0.3373 | 0.4983 |
| fused expanded_fqns | 0.4212 | 0.5255 |

| Source | Chunk Recall@5 | Chunk MRR | Expanded Recall@5 | Expanded MRR |
|--------|----------------|-----------|--------------------|--------------|
| bm25 | 0.2569 | 0.3827 | 0.4345 | 0.5321 |
| semantic | 0.0679 | 0.0576 | 0.1007 | 0.1763 |
| graph | 0.3810 | 0.4533 | 0.3596 | 0.4721 |
| fused | 0.3373 | 0.4983 | 0.4212 | 0.5255 |
