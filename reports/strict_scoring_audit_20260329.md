# 严格分层评分审计（2026-03-29）

## 总览

> 说明：下表的 `qwen_pe_ft / qwen_pe_rag_ft` 行是对**历史正式结果**做 strict 重评分后的快照，  
> 不是 2026-03-29 strict-clean 重训后的 FT family 最新结果。strict-clean 最终结果请优先看：
> - `reports/qwen_strict_closeout_20260329.md`
> - `reports/qwen_strict_result_audit_20260329.md`

| Experiment | Avg Union F1 | Avg Active-Layer Macro F1 | Avg Mislayer Rate | Exact Layer Match Rate |
|---|---:|---:|---:|---:|
| gpt_baseline | 0.2815 | 0.1652 | 0.1954 | 0.0741 |
| glm_baseline | 0.0666 | 0.0395 | 0.0556 | 0.0185 |
| qwen_baseline_recovered | 0.0370 | 0.0370 | 0.0000 | 0.0370 |
| pe_baseline | 0.2745 | 0.1958 | 0.1219 | 0.1111 |
| pe_system_prompt | 0.3138 | 0.2061 | 0.2065 | 0.0741 |
| pe_cot | 0.4218 | 0.2318 | 0.3179 | 0.0926 |
| pe_fewshot | 0.5732 | 0.4268 | 0.1694 | 0.1111 |
| pe_postprocess | 0.6062 | 0.3556 | 0.3037 | 0.0926 |
| qwen_pe_only | 0.2246 | 0.1702 | 0.0772 | 0.0741 |
| qwen_rag_only | 0.0185 | 0.0185 | 0.0000 | 0.0185 |
| qwen_pe_rag | 0.1534 | 0.1273 | 0.0370 | 0.0370 |
| qwen_ft_only | 0.0932 | 0.0833 | 0.0185 | 0.0556 |
| qwen_pe_ft | 0.4315 | 0.3404 | 0.1309 | 0.1111 |
| qwen_pe_rag_ft | 0.4435 | 0.3182 | 0.2204 | 0.0741 |

## GPT RAG Delta

- No-RAG avg union F1: `0.2783`
- With-RAG avg union F1: `0.2940`
- No-RAG avg active-layer macro F1: `0.1543`
- With-RAG avg active-layer macro F1: `0.1353`
- No-RAG avg mislayer rate: `0.2355`
- With-RAG avg mislayer rate: `0.2997`
- Avg union delta: `+0.0157`
- Avg macro delta: `-0.0189`

## 解释

- `union F1` 是旧口径，只看三层并集后的 FQN 命中。
- `macro F1` 是 strict 主口径，只对 gold 或 prediction 非空的 active layers 求平均。
- `mislayer rate` 衡量“FQN 命中了，但放错层”的比例；越高越差。
- `layer penalty = union - active-layer macro` 只作为辅助参考，不再单独作为主结论指标。
