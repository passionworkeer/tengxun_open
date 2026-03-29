# Qwen strict-clean 收口说明（2026-03-29）

## 1. 当前状态

**已完成！** Qwen strict-clean 微调复验已在 CUDA GPU 环境上完成（2026-03-29）。

- 历史正式矩阵：`PE / RAG / FT / PE+FT / PE+RAG / PE+RAG+FT` 已全部落盘
- strict-clean 微调复验：已完成训练和评测

**strict-clean 最新结果：**

| 评测 | Union F1 | 用例数 | 备注 |
|------|----------|--------|------|
| FT only | 0.0932 | 54 | baseline |
| PE + FT | 0.3865 | 54/54 | 全部完成 |
| PE + RAG + FT | **0.5018** | 54 | 最优配置 |

**训练详情：**

- 训练数据：`data/finetune_dataset_500_strict.jsonl`（500 条）
- 训练时长：41分47秒
- 最终 eval_loss：0.4661
- LoRA adapter：`artifacts/lora/qwen3.5-9b/strict_clean_20260329/`

因此现在可以说：

- "Qwen strict-clean 最优已经是 `PE + RAG + FT = 0.5018`"
- "训练数据纯度问题已解决，strict-clean FT family 已完成重训和重评"
- "开源模型最优路线已经完成 strict-clean 闭环"

## 2. 已完成的工作

- ✅ strict 微调数据已生成：`data/finetune_dataset_500_strict.jsonl`
- ✅ strict 数据审计已完成：`reports/strict_data_audit_20260329.md`
- ✅ strict few-shot 与 strict finetune 的 overlap 三项都为 `0`
- ✅ strict-clean LoRA 训练完成（3 epochs, 339 steps）
- ✅ FT only 评测完成
- ✅ PE + FT 评测完成
- ✅ PE + RAG + FT 评测完成
- ✅ 结果已打包：`artifacts/handoff/strict_clean_20260329.tar.gz`

## 3. 结果文件

训练配置：`configs/strict_clean_20260329.yaml`

训练日志：`logs/strict_clean_20260329.train.log`

评测结果：
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json`

## 4. 执行记录

在 CUDA GPU 环境（A100 40GB）上执行：

```bash
cd /workspace/tengxun_open
export DISABLE_VERSION_CHECK=1

# 训练
llamafactory-cli train configs/strict_clean_20260329.yaml

# 评测
python3 run_ft_eval.py \
  --strategy ft \
  --cases data/eval_cases.json \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_clean_20260329 \
  --output results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict.json

FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 run_ft_eval.py \
  --strategy pe_ft \
  --cases data/eval_cases.json \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_clean_20260329 \
  --output results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict.json

GOOGLE_API_KEY=xxx FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 run_ft_eval.py \
  --strategy pe_rag_ft \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_clean_20260329 \
  --output results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict.json

# 打包
RUN_NAME=strict_clean_20260329 INCLUDE_ADAPTER=1 ./scripts/package_qwen_strict_run.sh
```

## 5. 结论

strict-clean 训练和三组评测都已落盘，下面三句话可以无保留对外使用：

- "FT 增益不依赖训练集 overlap"
- "Qwen strict-clean 默认最强路线是 `PE + RAG + FT`，低复杂度路线是 `PE + FT`"
- "开源模型最优路线已经完成 strict-clean 闭环"
