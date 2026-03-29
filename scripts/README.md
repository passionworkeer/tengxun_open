# scripts 目录说明

> 最后更新：2026-03-29

## PE 评测（GPT/GLM，通过 API）

```bash
python scripts/run_pe_eval.py --api-key <key> --variants fewshot,postprocess
```

## Qwen 评测

```bash
# 需要先启动 vLLM 服务
bash scripts/run_qwen_strict_full.sh
```

## 数据与报告

| 脚本 | 用途 |
|------|------|
| `build_strict_datasets.py` | 生成 strict 去污染数据集 |
| `check_train_env.py` | 检查 CUDA / 训练环境是否就绪 |
| `generate_final_delivery_assets.py` | 生成最终图表（需要 matplotlib） |
| `generate_project_progress_report.py` | 生成项目进度报告 |
| `generate_defense_deck_20260329.py` | 生成答辩 PPT |
| `generate_eval_status_report.py` | 生成评测状态报告 |
| `precompute_embeddings.py` | 预计算 embedding 缓存 |
| `recover_qwen_baseline.py` | 恢复 Qwen strict baseline |
| `rescore_official_results.py` | 对正式结果做 strict 重评分 |
| `rescore_result_file.py` | 对单文件结果做 strict 重评分 |
| `analyze_glm5_official_results.py` | 分析 GLM5 官方评测结果 |
| `analyze_llm_eval_results.py` | 分析 LLM 评测结果 |
| `analyze_training_log.py` | 解析训练日志，输出结构化摘要 |
| `generate_finetune_data.py` | 生成正式微调数据 |
| `generate_targeted_badcase_finetune.py` | 针对 bad case 生成定向微调数据 |
| `finalize_official_datasets.py` | 整理最终数据集 |
| `run_pe_eval.py` | PE评测入口 |
| `run_qwen_strict_full.sh` | Qwen strict 评测完整跑线 |
| `package_qwen_strict_run.sh` | Qwen 评测打包脚本 |

## RAG 实验脚本

| 脚本 | 用途 |
|------|------|
| `run_conditional_rag_policy_experiment.py` | 条件RAG策略实验 |
| `run_conditional_rag_model_experiment.py` | 条件RAG模型实验 |
| `run_dynamic_typee_retrieval_experiment.py` | 动态类型检索实验 |

## 服务启动（用于 Qwen 评测）

启动 vLLM 服务后，用 `run_qwen_strict_full.sh` 评测：

```bash
# 手动启动 vLLM（参考 LLaMA-Factory 文档）
llamafactory-cli serve --config configs/llm.toml
```

## 输出结果

结果保存在 `results/`：
- `qwen_ft_*.json` — FT only 结果
- `qwen_pe_ft_*.json` — PE + FT 结果
- `qwen_pe_rag_ft_*.json` — 完整策略结果
- `strict_metrics_20260329/summary.json` — strict 口径权威汇总
