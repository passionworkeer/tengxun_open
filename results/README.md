# results 目录说明

## 当前正式结果

以下为正式评测结果，用于对外汇报和答辩：

| 模型 | 文件 | 说明 |
|------|------|------|
| GPT-5.4 | `gpt5_eval_results.json` | Baseline + PE + RAG 端到端 |
| GLM-5 | `glm_eval_scored_20260328.json` | 官方 API 评测 |
| Qwen3.5-9B | `qwen_baseline_recovered_20260328.json` | 严格口径基线 |
| Qwen3.5-9B PE | `qwen_pe_only_20260328.json` | PE 策略 |
| Qwen3.5-9B RAG | `qwen_rag_only_google_20260328.json` | Google embedding RAG |
| Qwen3.5-9B PE+RAG | `qwen_pe_rag_google_20260328.json` | PE+RAG 组合 |
| Qwen3.5-9B FT | `qwen_ft_20260327_160136.json` | LoRA 微调（历史正式线）|
| Qwen3.5-9B PE+FT | `qwen_pe_ft_20260327_162308.json` | PE+FT（历史正式线）|
| Qwen3.5-9B PE+RAG+FT | `qwen_pe_rag_ft_google_20260328.json` | 完整组合（历史正式线最高分）|
| Qwen3.5-9B strict-clean FT | `qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json` | strict-clean 54-case |
| Qwen3.5-9B strict-clean PE+FT | `qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json` | strict-clean 54-case |
| Qwen3.5-9B strict-clean PE+RAG+FT | `qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json` | strict-clean 54-case 最优 |

## PE 分项结果

```
pe_eval_54_20260328/           # 54-case 正式 PE 分项（cot/fewshot/postprocess/system_prompt）
pe_eval_strict_replay_20260329/  # strict replay PE 结果
pe_eval_strict_search_20260329/  # strict PE 超参搜索
pe_targeted_full_20260329/      # targeted few-shot 全量结果
```

## Strict 口径结果（2026-03-29）

```
strict_metrics_20260329/       # 历史正式结果的 strict 重评分快照
  ├── summary.json             # 历史正式线 strict 汇总，不是 strict-clean FT family 的最新权威表
  ├── gpt_baseline.json
  ├── gpt_rag_e2e.json
  ├── pe_baseline.json
  ├── pe_cot.json
  ├── pe_fewshot.json
  ├── pe_postprocess.json
  ├── pe_system_prompt.json
  ├── glm_baseline.json
  ├── qwen_baseline_recovered.json
  ├── qwen_pe_only.json
  ├── qwen_rag_only.json
  ├── qwen_pe_rag.json
  ├── qwen_ft_only.json
  ├── qwen_pe_ft.json
  └── qwen_pe_rag_ft.json
```

另外，strict-clean GPU 运行的最终结果位于：

```text
qwen_strict_runs/strict_clean_20260329/
  ├── qwen_ft_strict.json
  ├── qwen_ft_strict_metrics.json
  ├── qwen_ft_strict_stats.json
  ├── qwen_pe_ft_strict.json
  ├── qwen_pe_ft_strict_metrics.json
  ├── qwen_pe_ft_strict_stats.json
  ├── qwen_pe_rag_ft_strict.json
  ├── qwen_pe_rag_ft_strict_metrics.json
  └── qwen_pe_rag_ft_strict_stats.json
```

注意：

- `qwen_ft_strict.* / qwen_pe_ft_strict.* / qwen_pe_rag_ft_strict.*` 现在都已覆盖 `54/54` 条样本。
- strict-clean FT family 的最终权威结果，请优先看 `qwen_strict_runs/strict_clean_20260329/` 目录和 `reports/qwen_strict_result_audit_20260329.md`。

## RAG 检索结果

- `rag_google_eval_54cases_20260328.json` — 54-case Google embedding 检索质量
- `gpt_rag_e2e_54cases_20260328.json` — GPT-5.4 端到端 RAG 结果

## 统计文件

各策略配有 `*_stats.json` 统计摘要文件，快速查看关键指标：
`qwen_pe_only_20260328_stats.json`、`qwen_pe_rag_ft_google_20260328_stats.json` 等。
