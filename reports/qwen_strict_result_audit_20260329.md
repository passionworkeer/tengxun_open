# Qwen strict-clean 结果审计（2026-03-29）

这份审计只回答一个问题：

> 当前仓库里，Qwen strict-clean 微调线到底哪些结果已经完整落盘，哪些还只能算辅助结果？

## 1. 审计结论

- strict-clean LoRA 训练已完成，训练日志、配置、结果目录和 handoff 包都已落盘。
- `FT only` strict replay 已完整落盘：`54/54`，`avg_union_f1 = 0.0932`。
- `PE + RAG + FT` strict replay 已完整落盘：`54/54`，`avg_union_f1 = 0.5018`。
- `PE + FT` strict replay 目前只有 `48/54`，`avg_union_f1 = 0.3465`，不能当作完整 `54-case` 正式主结果。

## 2. 完整落盘的 strict 资产

训练资产：

- 配置：`configs/strict_clean_20260329.yaml`
- 日志：`logs/strict_clean_20260329.train.log`
- handoff 包：`artifacts/handoff/strict_clean_20260329_minimal.tar.gz`

结果资产：

- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_stats.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_stats.json`

## 3. 部分落盘的 strict 资产

当前只有一项需要单独标注：

- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_stats.json`

它们是有效结果，但只覆盖 `48/54` 条样本。

缺失的 `6` 条 case id：

- `celery_easy_020`
- `celery_easy_021`
- `celery_easy_022`
- `celery_easy_023`
- `celery_easy_024`
- `celery_medium_025`

因此当前最稳妥的说法是：

- `PE + FT strict replay` 可以作为辅助观察
- 不能直接替代原先的完整 `54-case` 历史正式 `PE + FT = 0.4315`

## 4. 当前可安全对外使用的结论

可以无保留使用：

- strict-clean 训练数据已完成去污染重训
- strict-clean 最强的**完整开源路线**是 `PE + RAG + FT = 0.5018`
- strict-clean `FT only = 0.0932`

需要保留条件地使用：

- `PE + FT strict replay = 0.3465` 目前只对应 `48/54`
- 如果要讲完整 `54-case` 的 `PE + FT`，当前仍应引用历史正式结果 `0.4315`

## 5. 推荐口径

答辩或最终 README 中，建议统一成下面这组表述：

- 开源模型 strict-clean 最优完整路线：`Qwen PE + RAG + FT = 0.5018`
- 开源模型 strict-clean `FT only`：`0.0932`
- 开源模型 `PE + FT`：
  - 历史正式完整 `54-case`：`0.4315`
  - strict replay 当前已落盘 `48/54`：`0.3465`

## 6. 相关文档

- 收口说明：`reports/qwen_strict_closeout_20260329.md`
- 训练证据：`reports/training_evidence_audit_20260329.md`
- CUDA runbook：`docs/qwen_strict_gpu_runbook_20260329.md`
