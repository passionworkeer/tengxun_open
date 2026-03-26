# Remaining Work Checklist

> 更新日期：2026-03-26
> 所有历史草稿已归档至 `docs/drafts_archived_20260326/`

---

## 项目当前状态

| 模块 | 状态 | 关键产物 |
|------|------|---------|
| 评测集（50条） | ✅ 完成 | `data/eval_cases_migrated_draft_round4.json` |
| Few-shot（20条） | ✅ 完成 | `pe/prompt_templates_v2.py`, `data/fewshot_examples_20.json` |
| GPT-5.4 Baseline | ✅ 完成 | `results/gpt5_results_archived/` |
| GLM-5 Baseline | ⚠️ 待跑 | `evaluation/run_glm_eval.py` |
| Qwen3.5-9B Baseline | ⚠️ 待跑 | — |
| RAG v2 检索 | ✅ 完成 | Graph 单路 R@5=0.331，RRF k=30 最优 |
| Qwen3 Embedding 集成 | ⚠️ 配额用尽 | 缓存 5825/8086 (72%)，明日继续 |
| LoRA 微调 | ⚠️ 待跑 | `finetune/train_lora.py`, `configs/lora_9b.toml` |

---

## 当前 P0 清单

### P0-01：GLM-5 基线评估
- 状态：API 已验证可用，接入 `evaluation/baseline.py`
- 待执行：`python3 -m evaluation.baseline --mode rag --eval-cases data/eval_cases_migrated_draft_round4.json --repo-root external/celery --top-k 5`
- 目标：拿到 GLM-5 在 50-case 上的真实 Recall/F1

### P0-02：Qwen3.5-9B 基线评估
- 状态：待执行
- 目标：拿到 Qwen3.5-9B 在 50-case 上的真实 Recall/F1（作为 FT 前对照）

### P0-03：Embedding 缓存补全
- 状态：5825/8086 完成，ModelScope 配额用尽
- 待执行（明日）：`python3 scripts/precompute_embeddings.py`
- 目标：8086 全部 embedding 缓存完成，RAG Semantic 源从 TF-IDF 升级到真实 Qwen3 Embedding

### P0-04：RAG Embedding 效果验证
- 前置：P0-03 完成
- 目标：对比 TF-IDF vs 真实 Embedding 的 RAG 效果提升

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
5. ⬜ 完整消融矩阵（10 组实验）
6. ⬜ LoRA 微调训练 + 端到端评测
