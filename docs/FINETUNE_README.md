# Qwen Fine-tuning Pipeline

## 1. 正式口径

当前仓库中与微调相关的**正式资产**如下：

| 资产 | 路径 | 说明 |
|------|------|------|
| 正式微调数据集 | `data/finetune_dataset_500.jsonl` | 正式 500 条训练数据 |
| LLaMA-Factory 数据映射 | `dataset_info.json` | 数据集名 `fintune_qwen_dep` 对应正式 JSONL |
| 正式训练配置 | `configs/train_config_20260327_143745.yaml` | 本轮正式 LoRA 配置 |
| 正式输出目录 | `artifacts/lora/qwen3.5-9b/formal_20260327_143745` | 当前正式配置的 `output_dir` |
| 正式训练日志 | `logs/train_20260327_143745.log` | 训练时长、loss、最终 eval_loss |
| 正式训练曲线 | `img/final_delivery/07_training_curve_20260328.png` | 由正式训练日志导出的 train loss 曲线 |
| FT only 结果 | `results/qwen_ft_20260327_160136_stats.json` | 正式 54-case 结果 |
| PE + FT 结果 | `results/qwen_pe_ft_20260327_162308_stats.json` | 正式 54-case 结果 |
| PE + RAG + FT 结果 | `results/qwen_pe_rag_ft_google_20260328_stats.json` | 正式 54-case 结果 |

当前仓库中与微调相关的**strict 复验资产**如下：

| 资产 | 路径 | 说明 |
|------|------|------|
| strict 微调数据集 | `data/finetune_dataset_500_strict.jsonl` | 去除 exact GT / hard question overlap 的 500 条训练数据 |
| strict 数据映射 | `dataset_info.json` | 数据集名 `fintune_qwen_dep_strict` |
| strict 训练配置 | `configs/train_config_strict_20260329.yaml` | strict LoRA 配置 |
| strict 审计报告 | `reports/strict_data_audit_20260329.md` | 记录 exact GT 与题面级 overlap 清理结果 |
| strict 评分报告 | `reports/strict_scoring_audit_20260329.md` | 分层 strict 指标与 mislayer 诊断 |

历史说明：

- 仓库中保留了若干早期辅助脚本，例如 `scripts/generate_finetune_data.py`、`scripts/train_lora.sh`。
- 这些脚本仍可用于 bootstrap 或本地实验，但**不是当前正式 500 条数据集与正式训练结果的唯一权威来源**。
- 当前若要做严格答辩或去污染复验，请优先使用 strict 资产，而不是直接在历史正式资产上继续加实验。

## 2. 正式训练入口

推荐直接使用仓库里的正式入口：

```bash
export PYTHONPATH=.
make lint-data
make train
```

等价命令：

```bash
python3 -m finetune.data_guard data/finetune_dataset_500.jsonl
python3 finetune/train_lora.py --config configs/train_config_20260327_143745.yaml
```

strict 复验入口：

```bash
export PYTHONPATH=.
make train-strict
```

等价命令：

```bash
python3 -m finetune.data_guard data/finetune_dataset_500_strict.jsonl
python3 finetune/train_lora.py --config configs/train_config_strict_20260329.yaml
```

说明：

- `make train` 实际调用 `finetune/train_lora.py`，再由它启动 `llamafactory-cli train ...`。
- 当前正式配置依赖 `LLaMA-Factory` 训练环境；若 `llamafactory-cli` 不在 PATH 中，可通过 `LLAMAFACTORY_CLI` 指向可执行文件。

## 3. 正式评测入口

### FT only

```bash
python3 run_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path 你的_adapter_路径 \
  --output results/qwen_ft_reproduced.json
```

### PE + FT

```bash
python3 run_pe_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path 你的_adapter_路径 \
  --output results/qwen_pe_ft_reproduced.json
```

### PE + RAG + FT

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key

python3 run_pe_rag_ft_eval.py \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --adapter-path 你的_adapter_路径 \
  --output results/qwen_pe_rag_ft_reproduced.json
```

## 4. Adapter 路径说明

历史正式跑线使用的是外部训练目录中的 LoRA adapter，因此仓库里保留的是：

- 正式训练配置
- 正式训练日志
- 正式评测结果
- 正式训练曲线

而不是直接 versioned 的 adapter 权重。

这不影响复现流程：

- 你可以在本地按正式配置重新训练，得到新的 adapter。
- 评测脚本统一支持显式传入 `--adapter-path`。
- 如果你已有本地 adapter，也可以通过环境变量 `QWEN_LORA_ADAPTER_PATH` 统一指定。

## 5. 训练证据

当前仓库保留的训练证据包括：

- step-level train loss：来自 `logs/train_20260327_143745.log`
- final train loss：`0.572`
- final eval loss：`0.4779`
- train runtime：`0:37:12.92`
- 可视化曲线：`img/final_delivery/07_training_curve_20260328.png`
- `data_guard` 的校验范围：对 Celery 内部 FQN 做源码存在性校验，对白名单外部依赖包做显式放行

当前没有逐步 `eval_loss` 曲线，因此判断不过拟合的证据强度是中等，不是最强形式。

如果你在 strict 配置上重训，建议同时导出：

- step-level train loss 曲线
- step-level eval loss 曲线
- strict adapter 对应的 `FT only / PE + FT / PE + RAG + FT` 三组结果

## 6. 资产管理建议

若你在本仓库内重跑训练，建议统一使用以下目录约定：

- 训练输出：`artifacts/lora/qwen3.5-9b/<run_name>/`
- 训练日志：`logs/<run_name>.log`
- 评测结果：`results/<run_name>_stats.json`

当前正式配置默认写入：

- `artifacts/lora/qwen3.5-9b/formal_20260327_143745`

如果你不想覆盖这个正式目录，复制一份 YAML 配置并修改 `output_dir` 后再启动训练。

strict 配置默认写入：

- `artifacts/lora/qwen3.5-9b/strict_20260329`

这样可以把“历史正式结果”和“你本次复现结果”分开，避免覆盖。

## 7. 什么时候该用正式资产，什么时候该用 strict 资产

- 如果你是在复述历史正式交付结果，用正式资产。
- 如果你是在回答“有没有训练/评测泄漏”的追问，用 strict 资产。
- 如果你准备重训并更新最终答辩数字，优先走 strict 资产，然后重跑 `FT only / PE + FT / PE + RAG + FT`。

## 8. 历史辅助脚本

### `scripts/generate_finetune_data.py`

- 用途：把评测结果转成 bootstrapping 数据。
- 定位：历史辅助脚本，可继续保留用于派生实验。
- 备注：不是当前正式 `data/finetune_dataset_500.jsonl` 的权威来源说明。

### `scripts/train_lora.sh`

- 用途：本地直接用 `transformers + peft` 跑一个轻量 LoRA 流程。
- 定位：实验辅助入口，不替代正式 `make train` / `finetune/train_lora.py`。
- 备注：已调整为兼容当前正式数据集格式，可做快速本地实验。
