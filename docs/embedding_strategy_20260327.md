# Embedding Strategy Decision

> 日期：2026-03-27  
> 结论：当前项目的正式 embedding 路径应优先切到 Google `gemini-embedding-001`，ModelScope / Qwen 作为保留分支，不再作为默认执行路径。

---

## 1. 决策背景

本项目的 RAG semantic 检索最初基于：

- Provider: ModelScope
- Model: `Qwen/Qwen3-Embedding-8B`
- 维度：`4096`
- 历史缓存：`artifacts/rag/embeddings_cache.json`

在 2026-03-27 的正式排查中，ModelScope 路径虽然能产出有效结果，但存在两个工程问题：

1. 补缓存过程长期受限流影响，无法稳定补齐。
2. 某些源码 chunk 会触发内容拦截，导致批次中断，需要额外拆批逻辑。

因此，ModelScope 路径可以作为 baseline / fallback，但不适合作为当前默认执行方案。

---

## 2. 两条路线的实测结果

### 2.1 ModelScope / Qwen3-Embedding-8B

- Provider 可用，但速率和配额稳定性不足。
- 补缓存过程中需要：
  - 小批量
  - 重试
  - 拆批定位内容安全样本
- 当前历史缓存进度：
  - `artifacts/rag/embeddings_cache.json`
  - `6571 / 8086`

结论：

- 能用
- 但没有彻底收口
- 不适合作为当前默认 embedding 方案

### 2.2 Google / Gemini Embedding

使用 key：

- `GOOGLE_API_KEY` 已实测可用

验证结果：

- `ListModels` 成功
- `models/gemini-embedding-001:embedContent` 成功
- `models/gemini-embedding-001:batchEmbedContents` 成功
- 默认维度：`3072`
- 可显式降维：如 `768`
- `text-embedding-004` 在当前 `v1beta` 路径上返回 `404 NOT_FOUND`

Google 免费层实测限制：

- 分钟级速率限制存在，需要控速
- 日级配额也存在
- 2026-03-27 当天已验证到 `EmbedContentRequestsPerDay...FreeTier` 的日配额上限

当前 Google 缓存进度（2026-03-27 首轮）：

- `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`
- 当天已稳定跑到 `900 / 8086`

结论：

- 接口稳定
- 批量能力明确
- 工程接入可控
- 更适合作为当前正式路线

---

## 3. 为什么最终优先 Google

这不是“Google 模型名字更大”，而是工程选择：

1. 当前项目核心瓶颈不是模型名，而是 provider 稳定性、批量吞吐、缓存可恢复性。
2. 对 Celery 代码检索任务来说，英文代码符号、路径、docstring 才是主体，重点是 embedding 服务能否稳定支撑大规模预计算。
3. Google 的 `gemini-embedding-001` 已经证明：
   - 批量接口可用
   - provider 行为可预期
   - 可以通过速率控制稳定推进

因此，当前更合理的执行策略是：

- 默认：Google `gemini-embedding-001`
- 保留：ModelScope `Qwen/Qwen3-Embedding-8B`
- 通过 provider-aware 配置统一管理

---

## 4. 本次代码改造

### 4.1 新增 provider-aware embedding 层

新增：

- `rag/embedding_provider.py`

职责：

- 统一 provider 配置解析
- 统一 cache 文件选择
- 统一 batch/query embedding 调用
- 支持：
  - `modelscope`
  - `google`

### 4.2 在线检索改为 provider-aware

修改：

- `rag/rrf_retriever.py`

效果：

- semantic query embedding 与离线缓存使用同一 provider 配置
- 不再把 provider / model / cache 路径硬编码在检索器内部

### 4.3 离线预计算改为 provider-aware

修改：

- `scripts/precompute_embeddings.py`

效果：

- 可通过环境变量切换 provider
- Google 路径支持批量 embedding
- 会自动按 provider 选择缓存文件
- Google 路径会自动按免费层速率限制估算安全 delay
- 遇到日配额耗尽时会保存当前缓存并停机

---

## 5. 缓存策略

### 5.1 不能混用旧缓存

旧缓存：

- ModelScope / Qwen
- 维度 `4096`

Google 新缓存：

- Gemini
- 维度 `3072`

如果混用，会导致：

- 点积计算时静默截断
- 分数失真
- 结果不可信

### 5.2 当前缓存隔离方案

- ModelScope:
  - `artifacts/rag/embeddings_cache.json`
- Google:
  - `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`

Google 缓存格式包含：

- `provider`
- `model`
- `dimension`

这样后续不会再发生 provider / 维度污染。

---

## 6. 当前建议

### 正式执行建议

使用 Google 路径继续完成 RAG embedding：

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=YOUR_KEY
python3 scripts/precompute_embeddings.py
```

补缓存完成后运行正式评测：

```bash
python -m evaluation.baseline \
  --mode rag \
  --eval-cases data/eval_cases.json \
  --repo-root external/celery \
  --top-k 5 \
  --query-mode question_plus_entry \
  --rrf-k 30 \
  --report-path artifacts/rag/eval_google_54cases.json
```

### 面试叙事建议

不要讲成：

- “我觉得 Google 模型更强。”

而要讲成：

- “我先基于开源 embedding 建立 baseline；
- 然后发现瓶颈并不在模型名称，而在 provider 限流、缓存污染、批量吞吐和可恢复性；
- 所以我把 embedding 层抽象成 provider-aware，并完成了 Google / ModelScope 双路接入；
- 最终把默认执行路径切到更稳定、可持续补齐缓存的 provider。”

这个故事更能体现工程判断力。

---

## 7. 当日状态快照

截至 2026-03-27：

- ModelScope 历史缓存：`6571 / 8086`
- Google 新缓存：`900 / 8086`
- Google 当天免费层日额度已触发
- 下一步：待额度恢复后继续从 Google 缓存断点续跑

---

## 8. 2026-03-28 进展补记

- Google embedding 已续跑到 `4360 / 8086`
- Google provider 正式 RAG 报告已生成：
  - `artifacts/rag/eval_google_54cases_20260328.json`
- 当前关键指标：
  - fused `chunk_symbols`: `Recall@5 = 0.4598`, `MRR = 0.5468`
  - fused `expanded_fqns`: `Recall@5 = 0.4490`, `MRR = 0.5519`

GLM 官方接口也已确认可用，但应拆成两种模式：

1. 稳定评测模式：
   - `thinking=disabled`
   - 目标是稳定拿最终 JSON，便于计算 F1
2. 原始数据采集模式：
   - `thinking=enabled`
   - 配合 `save_raw_response`
   - 目标是保留 `reasoning_content`、`usage`、`finish_reason` 等原始字段，后续再单独整理

当前 GLM 原始响应文件：

- `results/glm_eval_raw_official_20260328.json`
