# 报告文档说明

## 当前权威入口

- 总进度与完成度：`reports/project_progress_20260328.md`
- GPT / GLM / Google RAG 总状态：`reports/eval_status_20260328.md`
- GLM-5 专项分析：`reports/glm5_eval_analysis_20260328.md`
- GPT vs GLM 对比：`reports/llm_eval_comparison_20260328.md`

如果仓库内较早的 `2026-03-27` 文档、50-case 报告、过程性总结和以上文件冲突，以这里列出的 `2026-03-28` 文档为准。

## 当前正式结果速览

### 1. 数据与任务

- 正式评测集：`54` 条，`data/eval_cases.json`
- 微调集：`500` 条，`data/finetune_dataset_500.jsonl`
- 任务：Celery 跨文件依赖分析 / 再导出链 / 动态解析 / 字符串符号解析

### 2. 基线结果

- GPT-5.4：`Avg F1 = 0.2815`
- GLM-5：`Avg F1 = 0.0666`
- Qwen3.5-9B baseline 恢复版：`Avg F1 = 0.0370`

### 3. Prompt Engineering

正式 54-case GPT PE 结果位于 `results/pe_eval_54_20260328/`，最终 `postprocess` 版：

- `Avg F1 = 0.6062`
- 相对 baseline `0.2745` 明显提升

### 4. RAG

最新正式 embedding 方案为 `google / gemini-embedding-001`。

- 检索结果：`results/rag_google_eval_54cases_20260328.json`
- `fused chunk_symbols Recall@5 = 0.4305`, `MRR = 0.5292`
- `fused expanded_fqns Recall@5 = 0.4502`, `MRR = 0.5596`

### 5. 微调与组合策略

- FT only：`Avg F1 = 0.0932`
- PE + FT：`Avg F1 = 0.4315`
- PE + RAG + FT：`Avg F1 = 0.4435`

注意：现有 `PE + RAG + FT` 结果早于 `2026-03-28` 的 Google embedding 最终管线，若要形成严格最终版消融矩阵，建议按最新 embedding 重跑。

## 仍需补跑的最小实验

若目标是“严格完整的消融矩阵”，当前只剩 Qwen 相关少数项：

- `Qwen PE only`
- `Qwen RAG only`
- `Qwen PE + RAG`
- 建议重跑 `Qwen PE + RAG + FT` 以对齐最新 Google embedding

`GPT` 与 `GLM` 当前正式基线已经收口，不是主要缺口。

## 旧报告如何看

- `reports/DELIVERY_REPORT.md`
- `reports/bottleneck_diagnosis.md`
- `reports/pe_optimization.md`
- `reports/ablation_study.md`

这些文档仍有参考价值，但部分结论建立在旧 50-case 口径或中间实验上，适合做背景材料，不应覆盖当前正式结果。
