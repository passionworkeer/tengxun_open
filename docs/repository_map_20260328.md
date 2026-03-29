# 仓库结构与权威文件地图（2026-03-29）

## 使用方式

这份文档用于回答三个问题：

1. 现在仓库里哪些文件是正式结果
2. 哪些文件只是历史实验或中间产物
3. 导师或你自己应该先看哪里

## 推荐阅读顺序

1. [`README.md`](../README.md)
2. [`docs/official_asset_manifest.md`](./official_asset_manifest.md)
3. [`reports/DELIVERY_REPORT.md`](../reports/DELIVERY_REPORT.md)
4. [`reports/ablation_study.md`](../reports/ablation_study.md)
5. [`reports/bottleneck_diagnosis.md`](../reports/bottleneck_diagnosis.md)
6. [`reports/pe_optimization.md`](../reports/pe_optimization.md)
7. [`reports/rag_pipeline.md`](../reports/rag_pipeline.md)
8. [`reports/qwen_strict_result_audit_20260329.md`](../reports/qwen_strict_result_audit_20260329.md)
9. [`reports/defense_script_20260329.md`](../reports/defense_script_20260329.md)

## 当前正式仓库结构

交付时建议把项目名称表述为 `celery-dep-analysis`。  
仓库当前真实目录名仍然是 `tengxun`，两者对应的是同一套内容。

```text
celery-dep-analysis/
├── README.md                          # 项目总览、核心结论、复现入口
├── Makefile                           # 一键复现实验入口
├── requirements.txt                   # Python 依赖
├── Dockerfile                         # Docker 复现环境
│
├── data/                              # 正式数据资产
│   ├── eval_cases.json
│   ├── finetune_dataset_500.jsonl
│   └── fewshot_examples_20.json
│
├── evaluation/                        # 评测代码与指标计算
│   ├── baseline.py
│   ├── metrics.py
│   ├── run_gpt_eval.py
│   ├── run_glm_eval.py
│   ├── run_gpt_rag_eval.py
│   └── run_qwen_eval.py
│
├── pe/                                # Prompt Engineering 方案
│   ├── prompt_templates_v2.py
│   ├── prompt_templates.py
│   └── post_processor.py
│
├── rag/                               # RAG Pipeline
│   ├── ast_chunker.py
│   ├── embedding_provider.py
│   └── rrf_retriever.py
│
├── finetune/                          # 微调与数据校验
│   ├── data_guard.py
│   └── train_lora.py
│
├── configs/                           # 正式训练配置
│   ├── lora_9b.toml
│   ├── qlora_9b.toml
│   └── train_config_20260327_143745.yaml
│
├── experiments/                       # 实验组织层
│   └── README.md
│
├── scripts/                           # 数据、图表与结果整理脚本
│   ├── generate_final_delivery_assets.py
│   ├── generate_project_progress_report.py
│   ├── recover_qwen_baseline.py
│   ├── precompute_embeddings.py
│   └── ...
│
├── results/                           # 所有原始结果 JSON
│   ├── gpt5_eval_results.json
│   ├── glm_eval_results.json
│   ├── glm_eval_scored_20260328.json
│   ├── qwen_baseline_recovered_20260328.json
│   ├── pe_eval_54_20260328/
│   ├── gpt_rag_e2e_54cases_20260328.json
│   ├── qwen_ft_20260327_160136*.json
│   ├── qwen_pe_only_20260328*.json
│   ├── qwen_rag_only_google_20260328*.json
│   ├── qwen_pe_rag_google_20260328*.json
│   ├── qwen_pe_ft_20260327_162308*.json
│   └── qwen_pe_rag_ft_google_20260328*.json
│
├── reports/                           # 正式交付报告
│   ├── DELIVERY_REPORT.md
│   ├── bottleneck_diagnosis.md
│   ├── pe_optimization.md
│   ├── rag_pipeline.md
│   ├── ablation_study.md
│   ├── project_progress_20260328.md
│   └── final_metrics_snapshot_20260328.json
│
├── docs/                              # 结构文档与操作说明
│   ├── repository_map_20260328.md
│   ├── qwen_remaining_runs_20260328.md   # 历史执行记录
│   ├── official_asset_manifest.md
│   └── SERVER_DATA_GUIDE.md
│
└── img/final_delivery/                # 正式图表输出
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

这里只放原始结果 JSON 和统计摘要，不放长篇分析。

当前正式结果优先看：

- [`results/gpt5_eval_results.json`](../results/gpt5_eval_results.json)
- [`results/glm_eval_results.json`](../results/glm_eval_results.json)
- [`results/glm_eval_scored_20260328.json`](../results/glm_eval_scored_20260328.json)
- [`results/qwen_baseline_recovered_summary_20260328.json`](../results/qwen_baseline_recovered_summary_20260328.json)
- [`results/pe_eval_54_20260328/pe_summary.json`](../results/pe_eval_54_20260328/pe_summary.json)
- [`results/gpt_rag_e2e_54cases_20260328_summary.json`](../results/gpt_rag_e2e_54cases_20260328_summary.json)
- [`results/qwen_pe_only_20260328_stats.json`](../results/qwen_pe_only_20260328_stats.json)
- [`results/qwen_rag_only_google_20260328_stats.json`](../results/qwen_rag_only_google_20260328_stats.json)
- [`results/qwen_pe_rag_google_20260328_stats.json`](../results/qwen_pe_rag_google_20260328_stats.json)
- [`results/qwen_ft_20260327_160136_stats.json`](../results/qwen_ft_20260327_160136_stats.json)
- [`results/qwen_pe_ft_20260327_162308_stats.json`](../results/qwen_pe_ft_20260327_162308_stats.json)
- [`results/qwen_pe_rag_ft_google_20260328_stats.json`](../results/qwen_pe_rag_ft_google_20260328_stats.json)
- [`results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json`](../results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json)
- [`results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json`](../results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json)
- [`results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json`](../results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json)

分类原则：

- `results/qwen_strict_runs/strict_clean_20260329/`：Qwen strict-clean 最终结果，优先用于当前答辩
- `results/strict_metrics_20260329/`：历史正式结果的 strict 重评分快照，用于方法学解释
- `results/*_20260327_*`、`results/*_20260328_*`：历史正式结果与过程产物，保留作对照

### `reports/`

这里放“导师可直接阅读”的报告，可分三层理解：

第一层：总入口

- [`reports/DELIVERY_REPORT.md`](../reports/DELIVERY_REPORT.md)
- [`reports/final_numbers_cheatsheet_20260329.md`](../reports/final_numbers_cheatsheet_20260329.md)

第二层：五项题目要求对应报告

- [`reports/bottleneck_diagnosis.md`](../reports/bottleneck_diagnosis.md)：瓶颈诊断
- [`reports/pe_optimization.md`](../reports/pe_optimization.md)：PE 四维优化
- [`reports/rag_pipeline.md`](../reports/rag_pipeline.md)：RAG 技术与效果
- [`reports/ablation_study.md`](../reports/ablation_study.md)：当前消融矩阵

第三层：strict 防守与答辩材料

- [`reports/strict_data_audit_20260329.md`](../reports/strict_data_audit_20260329.md)
- [`reports/strict_scoring_audit_20260329.md`](../reports/strict_scoring_audit_20260329.md)
- [`reports/qwen_strict_result_audit_20260329.md`](../reports/qwen_strict_result_audit_20260329.md)
- [`reports/defense_script_20260329.md`](../reports/defense_script_20260329.md)
- [`reports/defense_qa_20260329.md`](../reports/defense_qa_20260329.md)

### `img/final_delivery/`

这里放当前正式版图表，供 README 与各报告引用。

### `docs/`

这里放“继续开发 / 继续复现 / 继续解释”用的操作说明：

- [`docs/official_asset_manifest.md`](./official_asset_manifest.md)：正式资产与历史归档边界
- [`docs/FINETUNE_README.md`](./FINETUNE_README.md)：微调资产与复现实验入口
- [`docs/qwen_strict_gpu_runbook_20260329.md`](./qwen_strict_gpu_runbook_20260329.md)：CUDA 训练执行手册
- [`docs/qwen_remaining_runs_20260328.md`](./qwen_remaining_runs_20260328.md)：历史执行记录，供追溯
- [`docs/repository_map_20260328.md`](./repository_map_20260328.md)：这份文件

## 哪些文件不要当“当前结论”

以下内容保留是为了追溯实验过程，不应覆盖正式结论：

- `results/qwen3_*`：早期 Qwen 测试产物
- `results/pe_eval/`：旧 50-case PE 结果
- `reports/eval_status_20260327.*`：旧一轮状态快照
- 较早的 `2026-03-27` 报告和 50-case 草稿若与当前 `2026-03-28` 正式报告冲突，以当前正式报告为准
- `artifacts/rag/` 下的大缓存文件：属于运行时资产，不属于 git 正式仓库内容
- `reports/strict_ft_execution_status_20260329.md`：GPU 执行前的历史状态记录，不是当前 strict-clean 最终状态
- `reports/strict_replay_guide_20260329.md`：strict 方法学构建说明，不是 Qwen FT family 的最终结果面板

## 当前最推荐的交付路径

如果导师只有 10 分钟，请按这个顺序打开：

1. [`README.md`](../README.md)
2. [`DELIVERY_CHECKLIST.md`](../DELIVERY_CHECKLIST.md)
3. [`reports/DELIVERY_REPORT.md`](../reports/DELIVERY_REPORT.md)
4. [`reports/final_numbers_cheatsheet_20260329.md`](../reports/final_numbers_cheatsheet_20260329.md)
5. [`reports/defense_deck_20260329.pptx`](../reports/defense_deck_20260329.pptx)

## 关于 Google embedding cache

当前正式 Google embedding cache 文件是：

- `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`

说明：

- 当前机器上可以直接复用，不需要重新切片或重新 embedding
- 这个文件没有进入 git，因为 `artifacts/` 被忽略且文件过大
- 如果你在另一台机器重新拉仓库，只会拿到代码和正式报告，不会自动拿到这个 326MB 缓存文件
- 若要跨机器复用，需手动复制该文件；否则运行 `scripts/precompute_embeddings.py` 重新生成
