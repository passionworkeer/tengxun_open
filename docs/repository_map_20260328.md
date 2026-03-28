# 仓库结构与权威文件地图（2026-03-28）

## 使用方式

这份文档用于回答三个问题：

1. 现在仓库里哪些文件是正式结果
2. 哪些文件只是历史实验或中间产物
3. 导师或你自己应该先看哪里

## 推荐阅读顺序

1. [`README.md`](../README.md)
2. [`reports/DELIVERY_REPORT.md`](../reports/DELIVERY_REPORT.md)
3. [`reports/ablation_study.md`](../reports/ablation_study.md)
4. [`reports/bottleneck_diagnosis.md`](../reports/bottleneck_diagnosis.md)
5. [`reports/pe_optimization.md`](../reports/pe_optimization.md)
6. [`reports/rag_pipeline.md`](../reports/rag_pipeline.md)
7. [`docs/qwen_remaining_runs_20260328.md`](./qwen_remaining_runs_20260328.md)

## 当前正式仓库结构

```text
tengxun_open/
├── README.md
├── Makefile
├── requirements.txt
│
├── data/
│   ├── eval_cases.json
│   ├── finetune_dataset_500.jsonl
│   └── fewshot_examples_20.json
│
├── evaluation/
│   ├── baseline.py
│   ├── metrics.py
│   ├── run_gpt_eval.py
│   ├── run_glm_eval.py
│   ├── run_gpt_rag_eval.py
│   └── run_qwen_eval.py
│
├── pe/
│   └── prompt_templates_v2.py
│
├── rag/
│   ├── ast_chunker.py
│   ├── embedding_provider.py
│   └── rrf_retriever.py
│
├── finetune/
│   ├── data_guard.py
│   └── train_lora.py
│
├── configs/
│   ├── lora_9b.toml
│   ├── qlora_9b.toml
│   └── train_config_20260327_143745.yaml
│
├── scripts/
│   ├── generate_final_delivery_assets.py
│   ├── generate_project_progress_report.py
│   ├── recover_qwen_baseline.py
│   └── ...
│
├── results/
│   ├── gpt5_eval_results.json
│   ├── glm_eval_results.json
│   ├── glm_eval_scored_20260328.json
│   ├── qwen_baseline_recovered_20260328.json
│   ├── pe_eval_54_20260328/
│   ├── gpt_rag_e2e_54cases_20260328.json
│   ├── qwen_ft_20260327_160136*.json
│   ├── qwen_pe_ft_20260327_162308*.json
│   └── qwen_pe_rag_ft_20260327_163613*.json
│
├── reports/
│   ├── DELIVERY_REPORT.md
│   ├── bottleneck_diagnosis.md
│   ├── pe_optimization.md
│   ├── rag_pipeline.md
│   ├── ablation_study.md
│   ├── project_progress_20260328.md
│   └── final_metrics_snapshot_20260328.json
│
├── docs/
│   ├── repository_map_20260328.md
│   └── qwen_remaining_runs_20260328.md
│
└── img/final_delivery/
    ├── 01_model_baselines_20260328.png
    ├── 02_pe_progression_20260328.png
    ├── 03_bottleneck_heatmap_20260328.png
    ├── 04_rag_retrieval_20260328.png
    ├── 05_rag_end_to_end_20260328.png
    ├── 06_qwen_strategies_20260328.png
    └── 07_training_curve_20260328.png
```

## 各目录的正式职责

### `data/`

正式数据入口：

- [`data/eval_cases.json`](../data/eval_cases.json)：正式 54-case 评测集
- [`data/finetune_dataset_500.jsonl`](../data/finetune_dataset_500.jsonl)：正式 500 条微调集
- [`data/fewshot_examples_20.json`](../data/fewshot_examples_20.json)：正式 20 条 few-shot 库

### `results/`

这里只放原始结果 JSON，不放长篇分析。

正式结果优先看：

- [`results/gpt5_eval_results.json`](../results/gpt5_eval_results.json)
- [`results/glm_eval_results.json`](../results/glm_eval_results.json)
- [`results/glm_eval_scored_20260328.json`](../results/glm_eval_scored_20260328.json)
- [`results/qwen_baseline_recovered_summary_20260328.json`](../results/qwen_baseline_recovered_summary_20260328.json)
- [`results/pe_eval_54_20260328/pe_summary.json`](../results/pe_eval_54_20260328/pe_summary.json)
- [`results/gpt_rag_e2e_54cases_20260328_summary.json`](../results/gpt_rag_e2e_54cases_20260328_summary.json)
- [`results/qwen_ft_20260327_160136_stats.json`](../results/qwen_ft_20260327_160136_stats.json)
- [`results/qwen_pe_ft_20260327_162308_stats.json`](../results/qwen_pe_ft_20260327_162308_stats.json)
- [`results/qwen_pe_rag_ft_20260327_163613_stats.json`](../results/qwen_pe_rag_ft_20260327_163613_stats.json)

### `reports/`

这里放“导师可直接阅读”的报告：

- [`reports/DELIVERY_REPORT.md`](../reports/DELIVERY_REPORT.md)：总体交付报告
- [`reports/bottleneck_diagnosis.md`](../reports/bottleneck_diagnosis.md)：瓶颈诊断
- [`reports/pe_optimization.md`](../reports/pe_optimization.md)：PE 四维优化
- [`reports/rag_pipeline.md`](../reports/rag_pipeline.md)：RAG 技术与效果
- [`reports/ablation_study.md`](../reports/ablation_study.md)：当前消融矩阵

### `img/final_delivery/`

这里放当前正式版图表，供 README 与各报告引用。

### `docs/`

这里放“继续开发 / 继续补跑”用的操作说明：

- [`docs/qwen_remaining_runs_20260328.md`](./qwen_remaining_runs_20260328.md)：Qwen 剩余实验怎么跑
- [`docs/repository_map_20260328.md`](./repository_map_20260328.md)：这份文件

## 哪些文件不要当正式版

以下内容保留是为了追溯实验过程，不应覆盖正式结论：

- `results/qwen3_*`：早期 Qwen 测试产物
- `results/pe_eval/`：旧 50-case PE 结果
- `reports/eval_status_20260327.*`：旧一轮状态快照
- 较早的 `2026-03-27` 报告和 50-case 草稿若与当前 `2026-03-28` 正式报告冲突，以当前正式报告为准
- `artifacts/rag/` 下的大缓存文件：属于运行时资产，不属于 git 正式仓库内容

## 关于 Google embedding cache

当前正式 Google embedding cache 文件是：

- `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`

说明：

- 当前机器上可以直接复用，不需要重新切片或重新 embedding
- 这个文件没有进入 git，因为 `artifacts/` 被忽略且文件过大
- 如果你在另一台机器重新拉仓库，只会拿到代码和正式报告，不会自动拿到这个 326MB 缓存文件
- 若要跨机器复用，需手动复制该文件；否则重新运行 embedding 预计算
