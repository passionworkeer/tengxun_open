# 答辩页图表挂载表（2026-03-29）

## 用途

这份文档用于把最终 PPT 的每一页和仓库里的正式图表、数字来源对齐，避免答辩时出现：

- 图表和正文口径不一致
- 数字来自不同版本结果
- 旧图被误挂到新结论上

## Slide Mapping

| Slide | 标题 | 图表 / 结果源 | 说明 |
|---|---|---|---|
| 1 | Title | 无 | 标题页，使用最终结论数字 |
| 2 | Dataset and Evaluation Design | `data/eval_cases.json` | 手工标注 54-case、20 strict few-shot、500 FT rows |
| 3 | Why This Task Is Hard | `img/final_delivery/03_bottleneck_heatmap_20260328.png` | 展示瓶颈类型分布与难点 |
| 4 | Baseline Models | `img/final_delivery/01_model_baselines_20260328.png` | GPT / GLM / Qwen baseline 对比 |
| 5 | Prompt Engineering Is The Strongest Single Lever | `img/final_delivery/02_pe_progression_20260328.png` | 正式 54-case progressive PE |
| 6 | Why Strict Metrics Matter | `results/pe_eval_strict_search_20260329/pe_postprocess_layered_strict.json` + `results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json` | old strict-best vs new strict-best |
| 7 | Strict PE Search | `reports/strict_pe_search_20260329.md` | 失败路线与最优路线对比 |
| 8 | RAG Helps Hard Cases | `img/final_delivery/04_rag_retrieval_20260328.png` + `img/final_delivery/05_rag_end_to_end_20260328.png` | 检索质量与端到端效果 |
| 9 | Open-Source Model Strategy | `img/final_delivery/06_qwen_strategies_20260328.png` | Qwen 消融矩阵核心结果 |
| 10 | Final Strategy Recommendation | `results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json` + `reports/ablation_study.md` | 商业模型与开源模型最终建议 |
| 11 | Appendix | `img/final_delivery/07_training_curve_20260328.png` | 微调训练曲线与边界说明 |

## 数字来源约束

### GPT strict PE 最优

统一使用：

- `results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json`

数字：

- `union 0.6338`
- `macro 0.4757`
- `mislayer 0.1620`
- `exact layer 0.1296`

### GPT 原始正式 PE progressive

统一使用：

- `results/pe_eval_54_20260328/pe_summary.json`

关键数字：

- baseline `0.2745`
- postprocess `0.6062`

### GPT RAG

统一使用：

- `results/gpt_rag_e2e_54cases_20260328_summary.json`

关键数字：

- no-rag `0.2783`
- with-rag `0.2940`
- hard `0.1980 -> 0.3372`

### Qwen 组合

统一使用：

- `results/qwen_ft_20260327_160136_stats.json`
- `results/qwen_pe_ft_20260327_162308_stats.json`
- `results/qwen_pe_rag_ft_google_20260328_stats.json`

关键数字：

- FT only `0.0932`
- PE + FT `0.4315`
- PE + RAG + FT `0.4435`
- 以上三项均属于历史正式 FT 线

## 最容易挂错的点

1. `0.6062` 是 GPT 原始正式 PE union 结果，不是 strict 最优。
2. strict GPT PE 最优必须写成 `0.6338 / 0.4757 / 0.1620`。
3. `GLM thinking` 不是正式主实验结果，不能出现在主表里。
4. `Qwen PE + FT` 是历史正式默认路线，`Qwen PE + RAG + FT` 才是历史正式开源最高分。
5. 如果导师按最严格口径追问，必须补一句：strict-clean FT rerun 已准备，结果待外部 CUDA 环境。
