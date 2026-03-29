# Qwen 历史正式实验复现说明（2026-03-28）

> **⚠️ 历史文档（仅供参考）**：本文件只保留“历史正式矩阵”的存档入口。  
> 当前最终口径请优先参考：
> - [`../reports/qwen_strict_closeout_20260329.md`](../reports/qwen_strict_closeout_20260329.md)
> - [`../reports/qwen_strict_result_audit_20260329.md`](../reports/qwen_strict_result_audit_20260329.md)
> - [`../docs/FINETUNE_README.md`](../docs/FINETUNE_README.md)

## 当前用途

这份文档现在只记录两件事：

- 历史正式 `54-case` Qwen 矩阵有哪些结果文件
- strict-clean 最终结果应该去看哪几份更新后的文档

## 历史正式矩阵结果

以下结果仍可作为“完整历史正式 `54-case` 矩阵”引用：

- FT only：
  - [`../results/qwen_ft_20260327_160136.json`](../results/qwen_ft_20260327_160136.json)
  - [`../results/qwen_ft_20260327_160136_stats.json`](../results/qwen_ft_20260327_160136_stats.json)
- PE + FT：
  - [`../results/qwen_pe_ft_20260327_162308.json`](../results/qwen_pe_ft_20260327_162308.json)
  - [`../results/qwen_pe_ft_20260327_162308_stats.json`](../results/qwen_pe_ft_20260327_162308_stats.json)
- PE + RAG + FT：
  - [`../results/qwen_pe_rag_ft_google_20260328.json`](../results/qwen_pe_rag_ft_google_20260328.json)
  - [`../results/qwen_pe_rag_ft_google_20260328_stats.json`](../results/qwen_pe_rag_ft_google_20260328_stats.json)

## strict-clean 最终口径

如果你要引用当前最新的 strict-clean 结果，请不要再看本文件里的旧执行命令，直接看：

- 收口说明：[`../reports/qwen_strict_closeout_20260329.md`](../reports/qwen_strict_closeout_20260329.md)
- 结果审计：[`../reports/qwen_strict_result_audit_20260329.md`](../reports/qwen_strict_result_audit_20260329.md)
- 微调说明：[`../docs/FINETUNE_README.md`](../docs/FINETUNE_README.md)

## 一句话区分

- 如果你在讲“完整历史正式矩阵”，看本文件。
- 如果你在讲“当前最新 strict-clean 结果”，不要再用本文件，转看 `qwen_strict_closeout` 和 `qwen_strict_result_audit`。
