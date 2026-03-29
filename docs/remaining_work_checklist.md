# Remaining Work Checklist

> 历史清单说明：这份文件记录的是 `2026-03-28` 收口前的待办快照，不代表当前正式状态。
> 当前正式完成度与对外交付口径以 `reports/project_progress_20260328.md` 和 `docs/official_asset_manifest.md` 为准。
> 更新日期：2026-03-28
> 所有历史草稿已归档至 `docs/drafts_archived_20260326/`

---

## 历史快照

| 模块 | 状态 | 关键产物 |
|------|------|---------|
| 评测集（50条） | ✅ 完成 | `data/eval_cases_migrated_draft_round4.json` |
| Few-shot（20条） | ✅ 完成 | `pe/prompt_templates_v2.py`, `data/fewshot_examples_20.json` |
| GPT-5.4 Baseline | ✅ 完成 | `results/gpt5_results_archived/` |
| PE 增量实验 | ✅ 完成 | Avg F1: 0.27→0.62（+131%），`results/pe_eval/` |
| GLM-5 Baseline | 🚧 官方接口重跑中 | `evaluation/run_glm_eval.py`, `results/glm_eval_raw_official_20260328.json` |
| Qwen3.5-9B Baseline | ⚠️ 待跑 | — |
| RAG v2 检索 | ✅ 完成 | Graph 单路 R@5=0.331，RRF k=30 最优 |
| Qwen3 Embedding 集成 | ⚠️ 非默认 | ModelScope 历史缓存 6571/8086，保留为 fallback |
| Google Embedding 集成 | 🚧 进行中 | `gemini-embedding-001` 已接入，Google 缓存 4360/8086 |
| LoRA 微调 | ⚠️ 待跑 | `finetune/train_lora.py`, `configs/lora_9b.toml` |

---

## 当前 P0 清单

### P0-01：GLM-5 基线评估 / 原始响应采集
- 状态：官方 `open.bigmodel.cn` 已验证可用；稳定评测走 `thinking=disabled`，原始数据采集走 `thinking=enabled + save_raw_response`
- 当前原始文件：`results/glm_eval_raw_official_20260328.json`
- 目标：先完整保存 54 条 raw response（含 `reasoning_content` / `usage`），后续再整理成正式评测分析

### P0-02：Qwen3.5-9B 基线评估
- 状态：待执行
- 目标：拿到 Qwen3.5-9B 在 50-case 上的真实 Recall/F1（作为 FT 前对照）

### P0-03：Embedding 缓存补全
- 状态：已切换优先路线为 Google embedding，ModelScope 保留为 fallback
- Google 当前进度：`4360/8086`
- ModelScope 历史进度：`6571/8086`
- 参考文档：`docs/embedding_strategy_20260327.md`
- 已落地报告：`artifacts/rag/eval_google_54cases_20260328.json`
- 待执行：继续 `uv run python scripts/precompute_embeddings.py`
- 目标：补齐 Google 独立缓存，并以此作为正式 semantic 路径

### P0-04：RAG Embedding 效果验证
- 状态：已拿到一版 Google provider 正式结果，待和 ModelScope / TF-IDF 做并排分析
- 目标：对比 TF-IDF vs ModelScope vs Google 的 RAG 效果提升

### P0-05：Graph-Weighted Fusion
- 状态：发现 graph 单路 > fused 的问题
- 待执行：调整 RRF 权重，graph × 2-3，BM25/Semantic 作为 tiebreaker
- 目标：融合效果超过 graph 单路

### P0-06：RRF k=30 确认
- 状态：已在 50-case 上验证 k=30 > k=60 > k=120
- 待执行：更新 `--rrf-k` 默认值为 30

### P0-07：GLM-5 → Qwen FT 数据生成
- 状态：`data/finetune_dataset_500.jsonl` 是旧版（基于 GPT-5 结果），需用 GLM-5 重跑
- 目标：500 条高质量微调数据，通过 `data_guard.py` 校验

### P0-08：LoRA 训练
- 状态：`finetune/train_lora.py` scaffold 就绪，未接真实 trainer backend
- 目标：接入真实 trainer，跑通 500 条数据的 LoRA 训练

### P0-09：完整消融矩阵
- 待执行：10 组实验（3 baseline + 7 叠加方案）
- 目标：填满 ablation_study.md 的所有 TBD 格子

---

## 模型基线（最终配置）

| 角色 | 模型 | Benchmark | 来源 |
|------|------|-----------|------|
| Baseline A | GPT-5.4 | SWE-Bench Pro 57.7% | 闭源商业 |
| Baseline B | GLM-5 | SWE-Bench Verified 77.8% | 开源 MIT，ModelScope API |
| Baseline C | Qwen3.5-9B | —（待测） | 开源本地，未微调 |
| FT 目标 | Qwen3.5-9B + LoRA | —（待测） | 端侧微调 |

> 注：SWE-Bench Pro 与 Verified 是不同测试集，不可直接对比大小。

---

## 评测集状态

- 文件：`data/eval_cases_migrated_draft_round4.json`
- 数量：50 条（Easy 15 / Medium 20 / Hard 15）
- Schema：schema_v2
- 源码绑定：`external/celery@b8f85213`

---

## 下一阶段里程碑

1. ✅ 评测集 50 条完成
2. ✅ Few-shot 20 条正式池稳定
3. ✅ RAG v2 检索评测完成（Graph 单路 R@5=0.331）
4. ⬜ GLM-5 / Qwen3.5-9B Baseline 实测
5. 🚧 Google embedding cache 补齐 + 正式 RAG 评测
6. ⬜ 完整消融矩阵（10 组实验）
7. ⬜ LoRA 微调训练 + 端到端评测
