# results 目录说明

## 当前正式结果

优先看这些文件：

- `gpt5_eval_results.json`
- `glm_eval_results.json`
- `glm_eval_scored_20260328.json`
- `qwen_baseline_recovered_20260328.json`
- `qwen_baseline_recovered_summary_20260328.json`
- `gpt_rag_e2e_54cases_20260328.json`
- `gpt_rag_e2e_54cases_20260328_summary.json`
- `rag_google_eval_54cases_20260328.json`
- `pe_eval_54_20260328/`
- `qwen_ft_20260327_160136.json`
- `qwen_ft_20260327_160136_stats.json`
- `qwen_pe_only_20260328.json`
- `qwen_pe_only_20260328_stats.json`
- `qwen_rag_only_google_20260328.json`
- `qwen_rag_only_google_20260328_stats.json`
- `qwen_pe_rag_google_20260328.json`
- `qwen_pe_rag_google_20260328_stats.json`
- `qwen_pe_ft_20260327_162308.json`
- `qwen_pe_ft_20260327_162308_stats.json`
- `qwen_pe_rag_ft_google_20260328.json`
- `qwen_pe_rag_ft_google_20260328_stats.json`

## 历史 / 调试结果

这些文件保留用于追溯，但不应覆盖正式结论：

- `qwen3_*`
- `glm5_*`
- `pe_eval/`（旧 50-case）
- `gpt_rag_e2e_10cases.json`
- 早期小样本测试 JSON

## 当前最重要的说明

- `qwen_pe_rag_ft_google_20260328*` 是当前完整矩阵里的最高开源结果。
- `qwen_baseline_recovered_20260328*` 是严格口径下的 baseline，不要再用旧的 `qwen_baseline_summary.json` 作为最终基线数字。
