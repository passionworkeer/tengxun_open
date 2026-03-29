# 正式资产清单

这份清单只记录**当前正式对外交付口径**，用于避免把历史草稿、过渡结果和正式结果混在一起。

正式评分主指标：将 `direct_deps / indirect_deps / implicit_deps` 三层并集后做 FQN 精确匹配；三层标签仍保留在正式数据中，用于诊断和展示。

## 1. 正式数据资产

| 资产 | 路径 | 说明 |
|------|------|------|
| 正式评测集 | `data/eval_cases.json` | 54 条，全部手工标注 |
| 正式 few-shot | `data/fewshot_examples_20.json` | 20 条 |
| 正式微调集 | `data/finetune_dataset_500.jsonl` | 500 条 |

## 2. 正式结果资产

| 模块 | 路径 | 说明 |
|------|------|------|
| GPT 基线 | `results/gpt5_eval_results.json` | 正式 54-case |
| GLM 基线 | `results/glm_eval_scored_20260328.json` | 正式 54-case |
| Qwen baseline | `results/qwen_baseline_recovered_summary_20260328.json` | strict recovered |
| GPT PE 四阶段 | `results/pe_eval_54_20260328/` | 正式 54-case |
| RAG 检索 | `results/rag_google_eval_54cases_20260328.json` | Google embedding 正式口径 |
| GPT RAG 端到端 | `results/gpt_rag_e2e_54cases_20260328_summary.json` | 正式 54-case |
| Qwen PE only | `results/qwen_pe_only_20260328_stats.json` | 正式结果 |
| Qwen RAG only | `results/qwen_rag_only_google_20260328_stats.json` | 正式结果 |
| Qwen PE + RAG | `results/qwen_pe_rag_google_20260328_stats.json` | 正式结果 |
| Qwen FT only | `results/qwen_ft_20260327_160136_stats.json` | 历史正式 FT 结果（与 strict-clean FT only 一致） |
| Qwen PE + FT | `results/qwen_pe_ft_20260327_162308_stats.json` | 历史正式 FT 结果 |
| Qwen PE + RAG + FT | `results/qwen_pe_rag_ft_google_20260328_stats.json` | 历史正式 FT 结果 |
| Qwen strict-clean FT only | `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json` | strict-clean 54-case |
| Qwen strict-clean PE + RAG + FT | `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json` | strict-clean 54-case 最优 |
| Qwen strict-clean PE + FT | `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json` | strict-clean 54-case |

## 3. 正式报告资产

| 报告 | 路径 |
|------|------|
| 总交付报告 | `reports/DELIVERY_REPORT.md` |
| 瓶颈诊断 | `reports/bottleneck_diagnosis.md` |
| PE 优化 | `reports/pe_optimization.md` |
| RAG 方案 | `reports/rag_pipeline.md` |
| 消融实验 | `reports/ablation_study.md` |
| 当前进度 | `reports/project_progress_20260328.md` |

## 4. 正式图表资产

位于 `img/final_delivery/`：

- `01_model_baselines_20260328.png`
- `02_pe_progression_20260328.png`
- `03_bottleneck_heatmap_20260328.png`
- `04_rag_retrieval_20260328.png`
- `05_rag_end_to_end_20260328.png`
- `06_qwen_strategies_20260328.png`
- `07_training_curve_20260328.png`

## 5. 正式训练证据

| 资产 | 路径 | 说明 |
|------|------|------|
| 训练配置 | `configs/train_config_20260327_143745.yaml` | 正式 LoRA 配置 |
| 数据映射 | `dataset_info.json` | `fintune_qwen_dep` -> `finetune_dataset_500.jsonl` |
| 训练日志 | `logs/train_20260327_143745.log` | 正式训练运行日志 |
| 训练曲线 | `img/final_delivery/07_training_curve_20260328.png` | 基于正式日志导出 |

## 6. 大体积本地资产

这些资产可以复现，但默认不进 git：

| 资产 | 路径 | 说明 |
|------|------|------|
| Google embedding cache | `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json` | 当前机器已有完整 cache |
| LoRA adapter weights | 本地训练输出目录 | 评测脚本支持 `--adapter-path` 显式指定 |

## 7. 历史归档

以下内容保留用于追踪演进过程，但**不是当前正式口径**：

- `results/pe_eval/` 下的旧 50-case PE 结果
- `reports/rag_retrieval_eval_round4.md`
- 其他明显以 50-case / draft 命名的历史文件

## 8. strict 复验与执行状态

这些文件用于回答“评分是否过宽松”“few-shot / finetune 是否污染”“Qwen strict-clean 到底完成到什么程度”：

| 资产 | 路径 | 说明 |
|------|------|------|
| strict 数据审计 | `reports/strict_data_audit_20260329.md` | exact GT / question overlap 清理结论 |
| strict 评分审计 | `reports/strict_scoring_audit_20260329.md` | union / macro / mislayer |
| strict PE 搜索 | `reports/strict_pe_search_20260329.md` | GPT strict 最优路线 |
| strict FT 执行状态 | `reports/strict_ft_execution_status_20260329.md` | GPU 执行前的本机 preflight 历史记录 |
| strict FT 结果审计 | `reports/qwen_strict_result_audit_20260329.md` | strict-clean 结果完整度说明 |
| 训练证据审计 | `reports/training_evidence_audit_20260329.md` | 现有训练证据强度说明 |
| strict replay 训练环境检查 | `results/strict_replay_train_env_20260329.json` | strict-clean replay preflight |
| 正式训练环境检查 | `results/formal_train_env_20260329.json` | 历史正式配置 preflight |
| 训练日志结构化摘要 | `results/training_log_summary_20260329.json` | train/eval 摘要 |

说明：

- GPT strict PE 结果已落盘，可直接用于答辩。
- Qwen strict-clean 训练已经完成，`FT only / PE + FT / PE + RAG + FT` 已完整落盘。
- 历史正式 `Qwen PE + FT = 0.4315` 与 strict-clean `Qwen PE + FT = 0.3865` 应明确区分；当前主汇报优先使用 strict-clean 结果。
