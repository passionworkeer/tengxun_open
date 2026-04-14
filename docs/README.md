# 文档索引

> 本目录包含 tengxun_open 项目所有文档，按类别整理。

---

## 核心资产（正式交付口径）

| 文档 | 说明 |
|------|------|
| `official_asset_manifest.md` | **正式资产清单** — 当前唯一权威口径，避免历史草稿混淆 |
| `SERVER_DATA_GUIDE.md` | **数据说明** — `data/eval_cases.json`（54条）是唯一正式评测入口 |
| `eval_case_annotation_template.md` | **评测标注模板** — 如何标注新的评测 case |
| `dataset_schema.md` | **数据集 Schema** — 评测集的数据结构定义 |

---

## 评测与分析

| 文档 | 说明 |
|------|------|
| `data-quality-report.md` | **数据质检报告** — 评测集质量核验 |
| `fqn-accuracy-report.md` | **FQN 可溯源性核验报告** —  Fully Qualified Name 准确性 |
| `celery_case_mining.md` | **Celery Case Mining Guide** — 如何从 Celery 仓库挖掘评测 case |

---

## Prompt Engineering

| 文档 | 说明 |
|------|------|
| `ai_prompt_templates.md` | **AI Prompt 模板库** — 各任务的 Prompt 模板 |
| `ai_task_breakdown.md` | **AI Task Breakdown** — 任务拆解 |
| `ai_task_cards.md` | **AI Task Cards** — 任务卡片定义 |
| `ai_work_batches.md` | **AI Work Batches** — 工作批次规划 |
| `fewshot_examples.md` | **Few-shot Examples Pool** — 小样本示例库 |
| `embedding_strategy_20260327.md` | **Embedding Strategy Decision** — 嵌入策略决策文档 |

---

## 微调（Fine-tuning）

| 文档 | 说明 |
|------|------|
| `FINETUNE_README.md` | **Qwen Fine-tuning Pipeline** — 微调完整流程说明 |
| `HYPERPARAMS_REASONING.md` | **Qwen3.5-9B LoRA 微调配置说明** — 超参数设计理由 |
| `Qwen3.5_DEPLOY_GUIDE.md` | **Qwen3.5-9B 本地部署指南** — 环境准备与部署 |
| `qwen_strict_gpu_runbook_20260329.md` | **Qwen Strict-Clean CUDA 执行手册** — GPU 复现实验操作指南 |

---

## 候选人/任务分发

| 文档 | 说明 |
|------|------|
| `candidate_dispatch_prompts.md` | **Candidate Dispatch Prompts** — 分发给候选人的 Prompt |
| `candidate_task_packets.md` | **Candidate Task Packets** — 候选人任务包 |
| `first_batch_candidates.md` | **First Batch Candidates** — 第一批候选人 |
| `candidate_dispatch_prompts.md` | — |

---

## 项目管理

| 文档 | 说明 |
|------|------|
| `execution_roadmap.md` | **Execution Roadmap** — 执行路线图（历史快照） |
| `detailed_stage_playbook.md` | **Detailed Stage Playbook** — 详细阶段操作手册 |
| `experiment_log_template.md` | **Experiment Log Template** — 实验日志模板 |
| `remaining_work_checklist.md` | **Remaining Work Checklist** — 待办清单（历史快照） |

---

## 仓库分析

| 文档 | 说明 |
|------|------|
| `repo_snapshot.md` | **Repo Snapshot** — 外部分析对象快照 |
| `repository_map_20260328.md` | **仓库结构与权威文件地图** — 目录结构与文件归属 |
| `qwen_remaining_runs_20260328.md` | **Qwen 历史正式实验复现说明** — 历史实验存档 |

---

## 文档状态说明

```
[正式]  = 当前正式交付/使用
[历史]  = 历史快照，仅供参考，不代表当前状态
[归档]  = 已归档，功能已被新方案替代
```

---

## 快速入口

- **开始新实验** → `experiment_log_template.md`
- **查看正式数据** → `SERVER_DATA_GUIDE.md`
- **添加新评测 case** → `celery_case_mining.md` + `eval_case_annotation_template.md`
- **Qwen 微调** → `FINETUNE_README.md`
- **Prompt 优化** → `ai_prompt_templates.md`
