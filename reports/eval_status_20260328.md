# 评测状态报告（2026-03-28）

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
- 原始 thinking 文件：`results/glm_eval_raw_official_20260328.json`
- 当前已落盘 case：`54`
- 平均 F1：`0.0666`
- Pass Rate：`13.0%`
- F1=0 数量：`47`
- 请求模型：`glm-5`
- 响应模型：`glm-5`
- 原始 thinking 平均长度：`7113.4` 字符
- 原始 finish_reason：`{'length': 49, 'stop': 5}`

## RAG

- 检索报告：`artifacts/rag/eval_google_54cases_20260328.json`
- Embedding 缓存：`artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`
- 缓存覆盖：`8086/8086` (`100.0%`)
- Embedding Provider：`google / gemini-embedding-001`
- Query mode：`question_plus_entry`
- RRF k：`30`

| View | Recall@5 | MRR |
|------|----------|-----|
| fused chunk_symbols | 0.4305 | 0.5292 |
| fused expanded_fqns | 0.4502 | 0.5596 |

| Source | Chunk Recall@5 | Chunk MRR | Expanded Recall@5 | Expanded MRR |
|--------|----------------|-----------|--------------------|--------------|
| bm25 | 0.2569 | 0.3827 | 0.4345 | 0.5321 |
| semantic | 0.1767 | 0.1714 | 0.1377 | 0.2141 |
| graph | 0.3772 | 0.4522 | 0.3596 | 0.4782 |
| fused | 0.4305 | 0.5292 | 0.4502 | 0.5596 |
