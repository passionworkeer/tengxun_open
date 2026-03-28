# 项目最终进度整理（2026-03-28）

## 一句话结论

- 数据集、GPT/GLM 基线、最新 Google embedding 的 RAG 检索、Qwen 完整消融矩阵都已有正式结果。
- 当前最强已落盘的 Qwen 组合是 `PE+RAG+FT = 0.4435`，当前高性价比开源路线是 `PE+FT = 0.4315`。
- 严格按当前正式口径，`GPT / GLM / Qwen / RAG / FT / 消融矩阵` 都已经收口。

## 数据集与任务覆盖

- 正式评测集：`54` 条，位于 `data/eval_cases.json`
- 微调数据集：`500` 条，位于 `data/finetune_dataset_500.jsonl`
- 任务方向：Celery 跨文件依赖分析 / 动态解析 / 再导出链 / 字符串符号解析
- 失效模式：Type A-E 五类均已定义并在评测集内覆盖

## 基线结果（54-case 正式口径）

| 模型 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 备注 |
|------|---------|-----------|---------|--------|------|
| GPT-5.4 | 0.4348 | 0.2188 | 0.2261 | 0.2815 | 官方 API，正式结果 |
| GLM-5 | 0.1048 | 0.0681 | 0.0367 | 0.0666 | 官方 API，正式结果 |
| Qwen3.5-9B | 0.0667 | 0.0526 | 0.0000 | 0.0370 | 旧 raw 输出恢复版，45/54 parse fail 记 0 |

- Qwen baseline 恢复率：`9/54`

## Prompt Engineering（GPT-5.4，54-case 正式重跑）

| Variant | Easy F1 | Medium F1 | Hard F1 | Avg F1 |
|---------|---------|-----------|---------|--------|
| baseline | 0.3907 | 0.2602 | 0.2010 | 0.2745 |
| system_prompt | 0.4306 | 0.3039 | 0.2356 | 0.3138 |
| cot | 0.4791 | 0.4170 | 0.3834 | 0.4218 |
| fewshot | 0.6492 | 0.5351 | 0.5525 | 0.5733 |
| postprocess | 0.6651 | 0.6165 | 0.5522 | 0.6062 |

- 口径说明：这是在 `data/eval_cases.json` 正式 54 条上的新版结果，优先级高于旧的 50-case `results/pe_eval/`。

## RAG 检索（最新 Google embedding）

- Embedding：`google / gemini-embedding-001`
- 缓存：完整 `8086/8086`

| View | Recall@5 | MRR |
|------|----------|-----|
| fused chunk_symbols | 0.4305 | 0.5292 |
| fused expanded_fqns | 0.4502 | 0.5596 |

## GPT 端到端 RAG 增益（54-case）

- No-RAG Avg F1：`0.2783`
- With-RAG Avg F1：`0.2940`
- Avg Delta：`+0.0157`

## Qwen 训练与组合策略（现有可用结果）

| Strategy | Easy F1 | Medium F1 | Hard F1 | Avg F1 | 备注 |
|----------|---------|-----------|---------|--------|------|
| PE only | 0.3167 | 0.2491 | 0.1323 | 0.2246 | 54-case，全量已跑 |
| RAG only | 0.0667 | 0.0000 | 0.0000 | 0.0185 | Google embedding |
| PE + RAG | 0.1514 | 0.2614 | 0.0523 | 0.1534 | Google embedding |
| FT only | 0.1556 | 0.0895 | 0.0500 | 0.0932 | 54-case，全量已跑 |
| PE + FT | 0.5233 | 0.5370 | 0.2624 | 0.4315 | 54-case，全量已跑 |
| PE + RAG + FT | 0.4985 | 0.4805 | 0.3672 | 0.4435 | Google embedding，当前开源最优 |

## 验收矩阵完成度

| 模块 | 当前状态 | 备注 |
|------|----------|------|
| 评测集 ≥50 条 | 完成 | 正式集 54 条 |
| 瓶颈诊断 | 完成 | Type A-E 已定义并有报告 |
| PE 四维优化 | 完成 | 旧 50-case 已有；54-case 新版以 `results/pe_eval_54_20260328/` 为准 |
| RAG 检索评测 | 完成 | 最新 Google embedding 已重跑 54-case |
| 微调数据集 ≥500 条 | 完成 | 正式集 500 条 |
| LoRA 微调 | 完成 | Qwen FT/PE+FT/PE+RAG+FT 已有结果 |
| 完整消融矩阵 | 完成 | `PE / RAG / FT / PE+RAG / PE+FT / All` 都已落盘 |

## Qwen 复现入口

当前没有必须补跑项。  
如果要在相同环境复现 Qwen 的正式实验，可以继续使用统一脚本：

```bash
uv run --with openai python run_qwen_ablation_eval.py --mode pe
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key
uv run --with openai python run_qwen_ablation_eval.py --mode rag --repo-root external/celery
uv run --with openai python run_qwen_ablation_eval.py --mode pe_rag --repo-root external/celery
```

## 当前最稳的对外结论

- 商业模型基线：`GPT-5.4` 明显强于 `GLM-5` 与 `Qwen3.5-9B`。
- PE 对 GPT 的提升非常显著，System Prompt / Few-shot / Post-process 是主要增益来源。
- 最新 Google embedding 下，RAG 检索层面已经收口，可作为正式方案。
- Qwen 的微调与组合策略已经形成完整矩阵，后续优化重点转向 hard case 和检索噪声控制。
