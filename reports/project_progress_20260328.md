# 项目最终进度整理（2026-03-29）

## 一句话结论

- 当前默认交付口径已经切到 strict-clean：few-shot / finetune 默认资产分别是 `data/fewshot_examples_20_strict.json` 与 `data/finetune_dataset_500_strict.jsonl`。
- 商业模型最强路线是 GPT-5.4 的 strict `postprocess_targeted`：`union 0.6338 / macro 0.4757 / mislayer 0.1620`。
- 开源模型最强完整路线是 Qwen strict-clean `PE + RAG + FT = 0.5018`；`PE + FT = 0.3865` 是复杂度更低的备选。
- 历史正式 few-shot / finetune 资产继续保留，但仅作归档对照，不再作为当前正式默认数据入口。

## 数据集与资产边界

- 正式评测集：`54` 条，位于 `data/eval_cases.json`，全部手工标注。
- 当前默认 few-shot：`20` 条 strict-clean 资产。
- 当前默认微调集：`500` 条 strict-clean 资产。
- 历史正式 few-shot / finetune 仍在仓库中，但只用于演进对照与污染审计。

## 基线结果（54-case 正式口径）

| 模型 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 备注 |
|------|---------|-----------|---------|--------|------|
| GPT-5.4 | 0.4348 | 0.2188 | 0.2261 | 0.2815 | 官方 API |
| GLM-5 | 0.1048 | 0.0681 | 0.0367 | 0.0666 | 官方 API |
| Qwen3.5-9B | 0.0667 | 0.0526 | 0.0000 | 0.0370 | strict recovered baseline |

## Prompt Engineering

| Variant | Avg F1 | 备注 |
|---------|--------|------|
| baseline | 0.2745 | GPT-5.4 正式 54-case |
| system_prompt | 0.3138 | GPT-5.4 正式 54-case |
| cot | 0.4218 | GPT-5.4 正式 54-case |
| fewshot | 0.5733 | GPT-5.4 正式 54-case |
| postprocess | 0.6062 | GPT-5.4 正式 54-case |
| strict postprocess_targeted | 0.6338 | macro=0.4757, mislayer=0.1620 |

## RAG

- Google embedding 检索：Recall@5=`0.4502`，MRR=`0.5596`
- GPT 端到端：No-RAG=`0.2783` -> With-RAG=`0.2940`，Delta=`+0.0157`

## Qwen strict-clean FT family

| Strategy | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 口径 |
|----------|---------|-----------|---------|--------|------|
| FT only | 0.1556 | 0.0895 | 0.0500 | 0.0932 | strict-clean 54-case |
| PE + FT | 0.5307 | 0.4277 | 0.2393 | 0.3865 | strict-clean 54-case |
| PE + RAG + FT | 0.6168 | 0.5196 | 0.3986 | 0.5018 | strict-clean 54-case |

## 训练证据

- 当前权威训练日志：`logs/strict_clean_20260329.train.log`
- step-level train loss 点数：`33`
- step-level eval loss 点数：`7`
- best eval loss：`0.4661`
- final eval loss：`0.4661`
- checkpoint：`50, 100, 150, 200, 250, 300, 339`

## 当前答辩可成立的完成度表述

| 模块 | 当前状态 | 说明 |
|------|----------|------|
| 评测集 ≥50 条 | 完成 | 54 条、全部手工标注 |
| 瓶颈诊断 | 完成 | Type A-E 已覆盖并有错误样例支撑 |
| PE 四维优化 | 完成 | 正式 54-case + strict 搜索都已落盘 |
| RAG 检索与端到端评估 | 完成 | Google embedding 正式结果已落盘 |
| 微调数据集 ≥500 条 | 完成 | 当前默认 strict-clean 500 条；历史正式集仅归档 |
| LoRA 微调 | 完成 | strict-clean 训练日志、adapter handoff、FT family 结果均已落盘 |
| 完整消融矩阵 | 完成 | 当前对外交付默认使用 strict-clean FT family 结果 |

## 风险与边界

- 当前主评分指标仍是三层并集后的 FQN 精确匹配；严格分层判断需同时参考 strict `macro F1 / mislayer rate`。
- 历史正式 few-shot / finetune 资产存在 overlap 风险，因此已经从当前默认交付链路中降级为归档对照。
- strict-clean `PE + RAG + FT` 虽然总分最高，但 `mislayer` 仍高于更保守的 `PE + FT`，答辩时应明确“最强”与“最稳”不是同一件事。

