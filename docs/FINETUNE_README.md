# Qwen Fine-tuning Pipeline

## 1. 当前默认口径

当前仓库里与微调相关的**默认交付资产**已经统一切到 strict-clean：

| 资产 | 路径 | 说明 |
|------|------|------|
| 当前默认微调数据集 | `data/finetune_dataset_500_strict.jsonl` | strict-clean 500 条训练数据 |
| 数据映射 | `dataset_info.json` | 数据集名 `fintune_qwen_dep_strict` |
| 当前默认训练配置 | `configs/strict_clean_20260329.yaml` | 当前正式 strict-clean LoRA 配置 |
| 当前默认训练日志 | `logs/strict_clean_20260329.train.log` | 含 step-level train/eval loss |
| 当前默认 adapter handoff | `artifacts/handoff/strict_clean_20260329_minimal.tar.gz` | 训练/打包脚本产出的 handoff 包，需 materialize 后使用 |
| 当前默认 FT only | `results/qwen_strict_runs/strict_clean_20260329/qwen_ft_strict_metrics.json` | strict-clean 54-case |
| 当前默认 PE + FT | `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_ft_strict_metrics.json` | strict-clean 54-case |
| 当前默认 PE + RAG + FT | `results/qwen_strict_runs/strict_clean_20260329/qwen_pe_rag_ft_strict_metrics.json` | strict-clean 54-case |
| 当前默认训练曲线 | `img/final_delivery/07_training_curve_20260328.png` | 基于 strict-clean 日志导出 |

当前默认结论：

- `FT only = 0.0932`
- `PE + FT = 0.3865`
- `PE + RAG + FT = 0.5018`

## 2. 历史正式归档口径

历史正式微调资产仍然保留，但只作归档对照，不再作为当前默认训练 / 评测入口：

| 资产 | 路径 | 说明 |
|------|------|------|
| 历史正式微调数据集 | `data/finetune_dataset_500.jsonl` | 历史正式 500 条训练数据 |
| 历史数据映射 | `dataset_info.json` | 数据集名 `fintune_qwen_dep` |
| 历史正式训练配置 | `configs/train_config_20260327_143745.yaml` | 早期正式 LoRA 配置 |
| 历史正式训练日志 | `logs/train_20260327_143745.log` | 只有最终 eval_loss |
| 历史正式 FT only | `results/qwen_ft_20260327_160136_stats.json` | 历史 54-case 结果 |
| 历史正式 PE + FT | `results/qwen_pe_ft_20260327_162308_stats.json` | 历史 54-case 结果 |
| 历史正式 PE + RAG + FT | `results/qwen_pe_rag_ft_google_20260328_stats.json` | 历史 54-case 结果 |

补充说明：

- 历史正式 few-shot / finetune 与 eval 存在 overlap 风险，详见 `reports/strict_data_audit_20260329.md`。
- `make lint-data` 当前默认已经不再校验这套历史训练集；如需查看，使用 `make lint-data-historical`。

## 3. 当前默认训练入口

推荐直接使用仓库里的当前默认 strict-clean 入口：

```bash
export PYTHONPATH=.
make lint-data
make train
```

等价命令：

```bash
python3 -m finetune.data_guard data/finetune_dataset_500_strict.jsonl
python3 finetune/train_lora.py --config configs/strict_clean_20260329.yaml
```

如果你要先确认机器能不能承担训练，先执行：

```bash
make check-train-env
```

如果你要重放严格复现实验流程，保留了 strict replay 入口：

```bash
make train-strict-dry-run
make qwen-strict-rerun
```

相关文档：

- `reports/qwen_strict_closeout_20260329.md`
- `reports/qwen_strict_result_audit_20260329.md`
- `docs/qwen_strict_gpu_runbook_20260329.md`

## 4. 当前默认评测入口

### 先 materialize adapter

```bash
make materialize-strict-adapter
```

这会把 handoff 包提取到：

```text
artifacts/lora/qwen3.5-9b/strict_clean_20260329/
```

### FT only

```bash
make eval-ft
```

### PE + FT

```bash
make eval-ft FT_STRATEGY=pe_ft
```

### PE + RAG + FT

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key
make eval-ft FT_STRATEGY=pe_rag_ft
```

如果你已有其他 adapter，也可以显式指定：

```bash
QWEN_LORA_ADAPTER_PATH=/path/to/adapter python3 run_ft_eval.py --strategy pe_ft
```

## 5. 训练证据

当前默认训练证据来自 `logs/strict_clean_20260329.train.log`，不是历史正式日志。

当前已经落盘的硬证据包括：

- step-level train loss
- step-level eval loss
- 中间 checkpoint：`50 / 100 / 150 / 200 / 250 / 300 / 339`
- best eval loss：`0.4661`
- 最后一次 logged eval loss：`0.4664`
- 训练曲线：`img/final_delivery/07_training_curve_20260328.png`
- 结构化摘要：`results/training_log_summary_20260329.json`

因此当前默认训练线已经满足：

- 有逐步 train / eval 曲线
- 有中间 checkpoint
- 有完整 `FT only / PE + FT / PE + RAG + FT` 三组结果

历史正式训练线仍保留，但只用于演进对照。它的问题是：

- `eval_steps=500`
- `save_steps=500`
- 估算总步数只有约 `339`

所以历史正式训练线不会产生 step-level eval，也不再作为默认答辩证据。

## 6. 数据守卫与污染审计

当前 `data_guard` 默认会做两层检查：

1. 记录格式、difficulty、FQN 合法性、Celery 内部源码存在性
2. 与 `data/eval_cases.json` 的 overlap 审计

默认命令：

```bash
python3 -m finetune.data_guard data/finetune_dataset_500_strict.jsonl
```

它会拒绝：

- exact GT overlap
- normalized exact question overlap
- hard question overlap

因此：

- strict-clean 训练集会通过 gate
- 历史正式训练集会报告 overlap 风险并 fail gate

## 7. 资产管理建议

建议统一按下面的目录约定管理新的训练产物：

- 训练输出：`artifacts/lora/qwen3.5-9b/<run_name>/`
- 训练日志：`logs/<run_name>.train.log`
- 评测结果：`results/qwen_strict_runs/<run_name>/`

当前默认 adapter 目录约定为：

- `artifacts/lora/qwen3.5-9b/strict_clean_20260329`

历史正式目录保留为约定的历史输出路径：

- `artifacts/lora/qwen3.5-9b/formal_20260327_143745`

## 8. 什么时候该引用哪套资产

- 如果你是在复述当前最终交付结果，用 strict-clean 资产。
- 如果你是在解释演进过程或对照历史分数，再引用历史正式资产。
- 如果你是在回答“有没有训练/评测泄漏”的追问，优先看 strict 审计和 strict-clean 结果。
- 如果你准备在另一台 GPU 机器上重现这次流程，优先走 strict-clean 资产。

## 9. 相关文档

- `reports/strict_data_audit_20260329.md`
- `reports/strict_scoring_audit_20260329.md`
- `reports/qwen_strict_closeout_20260329.md`
- `reports/qwen_strict_result_audit_20260329.md`
- `reports/training_evidence_audit_20260329.md`
- `docs/qwen_strict_gpu_runbook_20260329.md`
