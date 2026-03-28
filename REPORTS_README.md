# 报告与结果索引

## 导师优先阅读顺序

1. `README.md`
2. `reports/DELIVERY_REPORT.md`
3. `reports/ablation_study.md`
4. `reports/bottleneck_diagnosis.md`
5. `reports/pe_optimization.md`
6. `reports/rag_pipeline.md`

## 当前权威文档

- 总交付报告：`reports/DELIVERY_REPORT.md`
- 瓶颈诊断：`reports/bottleneck_diagnosis.md`
- PE 优化：`reports/pe_optimization.md`
- RAG 方案：`reports/rag_pipeline.md`
- 消融实验：`reports/ablation_study.md`
- 当前进度快照：`reports/project_progress_20260328.md`
- 图表指标快照：`reports/final_metrics_snapshot_20260328.json`
- Qwen 复现实验说明：`docs/qwen_remaining_runs_20260328.md`
- 仓库地图：`docs/repository_map_20260328.md`

## 当前正式图表

位于 `img/final_delivery/`：

- `01_model_baselines_20260328.png`
- `02_pe_progression_20260328.png`
- `03_bottleneck_heatmap_20260328.png`
- `04_rag_retrieval_20260328.png`
- `05_rag_end_to_end_20260328.png`
- `06_qwen_strategies_20260328.png`
- `07_training_curve_20260328.png`

## 当前最重要的正式结果

### 数据

- 评测集：`data/eval_cases.json`，`54` 条
- Few-shot：`data/fewshot_examples_20.json`，`20` 条
- 微调集：`data/finetune_dataset_500.jsonl`，`500` 条

### 基线

- GPT-5.4：`Avg F1 = 0.2815`
- GLM-5：`Avg F1 = 0.0666`
- Qwen3.5 baseline（strict recovered）：`Avg F1 = 0.0370`

### 优化结果

- GPT-5.4 `PE only`：`Avg F1 = 0.6062`
- GPT-5.4 `RAG only`：`Avg F1 = 0.2940`
- Qwen `PE only`：`Avg F1 = 0.2246`
- Qwen `RAG only`：`Avg F1 = 0.0185`
- Qwen `PE + RAG`：`Avg F1 = 0.1534`
- Qwen `FT only`：`Avg F1 = 0.0932`
- Qwen `PE + FT`：`Avg F1 = 0.4315`
- Qwen `PE + RAG + FT`：`Avg F1 = 0.4435`

### RAG 检索

- `fused chunk_symbols Recall@5 = 0.4305`
- `fused expanded_fqns Recall@5 = 0.4502`
- `fused expanded_fqns MRR = 0.5596`

## 当前矩阵状态

- 题目要求的 `PE / RAG / FT / PE+RAG / PE+FT / All` 已经补齐。
- `docs/qwen_remaining_runs_20260328.md` 现在用于复现这些结果，不再是待办清单。

## 旧文件怎么处理

仓库内仍保留若干历史中间结果：

- `results/qwen3_*`
- `results/pe_eval/`
- 旧版 `2026-03-27` 报告
- `results/glm5_*` 的早期实验文件

这些文件适合追溯过程，不应覆盖当前正式结论。
