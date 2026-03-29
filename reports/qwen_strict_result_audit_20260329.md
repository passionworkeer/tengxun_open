# Qwen strict-clean 结果审计（2026-03-29）

这份审计只回答一个问题：

> 当前仓库里，Qwen strict-clean 微调线到底哪些结果已经完整落盘，以及现在应该怎样对外汇报？

## 1. 审计结论

- strict-clean LoRA 训练已完成，训练日志、配置、结果目录和 handoff 包都已落盘。
- `FT only` strict replay 已完整落盘：`54/54`，`avg_union_f1 = 0.0932`。
- `PE + FT` strict replay 已完整落盘：`54/54`，`avg_union_f1 = 0.3865`。
- `PE + RAG + FT` strict replay 已完整落盘：`54/54`，`avg_union_f1 = 0.5018`。
- 因此，Qwen strict-clean FT family 现在已经形成完整闭环，可以直接作为开源模型主结论使用。

## 2. 完整落盘的 strict 资产

训练资产：

- 配置：`configs/strict_clean_20260329.yaml`
- 日志：`logs/strict_clean_20260329.train.log`
- handoff 包：`artifacts/handoff/strict_clean_20260329_minimal.tar.gz`

结果资产：

- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_stats.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_stats.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_stats.json`

## 3. 如何理解 strict-clean 与历史正式结果

- strict-clean `PE + FT = 0.3865` 低于历史正式 `PE + FT = 0.4315`，这并不矛盾。
- 两者的训练数据纯度和执行批次不同；strict-clean 的价值在于去污染、训练证据更完整、答辩时更能抗追问。
- 因此当前主汇报应优先使用 strict-clean 结果；历史正式结果保留为演进对照，而不是主结论。

## 4. 当前可安全对外使用的结论

可以无保留使用：

- strict-clean 训练数据已完成去污染重训
- strict-clean 最强的**完整开源路线**是 `PE + RAG + FT = 0.5018`
- strict-clean `FT only = 0.0932`
- strict-clean `PE + FT = 0.3865`

作为归档或对照使用：

- 历史正式 `PE + FT = 0.4315`
- 历史正式 `PE + RAG + FT = 0.4435`

## 5. 推荐口径

答辩或最终 README 中，建议统一成下面这组表述：

- 开源模型 strict-clean 最优完整路线：`Qwen PE + RAG + FT = 0.5018`
- 开源模型 strict-clean `FT only`：`0.0932`
- 开源模型 strict-clean `PE + FT`：`0.3865`
- 历史正式 `PE + FT = 0.4315` 只作为归档参考，不再作为 strict-clean 主表主列

## 6. 相关文档

- 收口说明：`reports/qwen_strict_closeout_20260329.md`
- 训练证据：`reports/training_evidence_audit_20260329.md`
- CUDA runbook：`docs/qwen_strict_gpu_runbook_20260329.md`
