# Qwen strict-clean 收口说明（2026-03-29）

## 1. 当前状态

Qwen strict-clean 这条线已经进入“结果落盘并可交付”的状态，但需要把**完整结果**和**部分结果**分开说。

- strict-clean LoRA 训练：已完成
- `FT only` strict replay：已完整落盘，`54/54`
- `PE + RAG + FT` strict replay：已完整落盘，`54/54`
- `PE + FT` strict replay：已产生有效结果，但当前只有 `48/54`

最新 strict-clean 结果：

| 评测 | Union F1 | 用例数 | 当前口径 |
|------|----------|--------|----------|
| FT only | 0.0932 | 54/54 | 可直接对外使用 |
| PE + FT | 0.3465 | 48/54 | 仅作辅助观察，不替代完整 `54-case` 主结果 |
| PE + RAG + FT | **0.5018** | 54/54 | 当前最强的完整开源 strict-clean 路线 |

训练详情：

- 训练数据：`data/finetune_dataset_500_strict.jsonl`（500 条）
- 训练时长：`0:41:47.32`
- 最终 train loss：`0.5776`
- 最终 eval loss：`0.4661`
- step-level eval loss：已保留，并生成 `training_eval_loss.png`

## 2. 当前可以成立的结论

现在可以无保留说：

- strict-clean 去污染训练已经落盘
- `Qwen PE + RAG + FT = 0.5018` 是当前最强的**完整**开源 strict-clean 路线
- strict-clean `FT only = 0.0932` 已完成全量 `54-case`
- strict 训练证据强度已经明显强于历史正式训练，因为这次保留了 step-level `eval_loss`

现在还不能讲太满的部分：

- 不能把 `PE + FT strict replay = 0.3465` 直接当作完整 `54-case` 最终数字
- 不能说 strict-clean 的所有 FT family 分支都已经“同口径闭环”

原因是：

- `PE + FT strict replay` 当前只覆盖 `48/54`
- 缺失 `6` 条 case，详见 `reports/qwen_strict_result_audit_20260329.md`

## 3. 结果文件

训练配置：

- `configs/strict_clean_20260329.yaml`

训练日志：

- `logs/strict_clean_20260329.train.log`

完整落盘的 strict 结果：

- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_stats.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_stats.json`

部分落盘的 strict 结果：

- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict.json`
- `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json`

handoff 产物：

- `artifacts/handoff/strict_clean_20260329_minimal.tar.gz`

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
RUN_NAME=strict_clean_20260329 ./scripts/package_qwen_strict_run.sh
```

## 5. 推荐口径

如果你现在写 README、答辩稿或总报告，建议统一成下面这组说法：

- 开源模型 strict-clean 最优完整路线：`Qwen PE + RAG + FT = 0.5018`
- 开源模型 strict-clean `FT only = 0.0932`
- `PE + FT`：
  - 历史正式完整 `54-case`：`0.4315`
  - strict replay 当前已落盘 `48/54`：`0.3465`

## 6. 关联文档

- `reports/qwen_strict_result_audit_20260329.md`
- `reports/training_evidence_audit_20260329.md`
- `docs/qwen_strict_gpu_runbook_20260329.md`
