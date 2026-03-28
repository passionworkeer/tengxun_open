# Qwen Fine-tuning Pipeline

## 概述

本工具链用于对 Qwen 模型进行微调，以提升 Celery 依赖分析的准确率。

## 流程图

```
GPT-5.4 评测结果
      │
      ▼
┌─────────────────┐
│ 生成微调数据    │  scripts/generate_finetune_data.py
│ (F1>=0.5样本)  │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ LoRA 微调训练   │  scripts/train_lora.sh
│ Qwen3.5-9B     │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ 微调后模型评测  │  scripts/run_finetuned_eval.py
│                 │
└─────────────────┘
      │
      ▼
┌─────────────────┐
│ 对比报告        │  scripts/compare_results.py
│ GPT5 vs FT     │
└─────────────────┘
```

## 脚本列表

| 脚本 | 功能 |
|------|------|
| `scripts/generate_finetune_data.py` | 从评测结果生成微调数据 |
| `scripts/train_lora.sh` | LoRA 微调训练 |
| `scripts/run_finetuned_eval.py` | 微调后模型评测 |
| `scripts/compare_results.py` | 对比 GPT5 和微调后结果 |
| `scripts/run_qwen_eval.sh` | Qwen3.5 本地部署评测 |

## 使用方法

### 方式1: 一键运行全部流程

当前没有单独的总控脚本，按下面 Step 1 到 Step 4 依次执行即可。

### 方式2: 分步运行

**Step 1: 生成微调数据**

```bash
python scripts/generate_finetune_data.py \
    --input results/gpt5_eval_results.json \
    --output data/finetune_from_gpt5.jsonl \
    --min-f1 0.5
```

**Step 2: 训练 LoRA**

```bash
# 设置模型路径（修改为你部署的模型）
export MODEL_NAME="/path/to/your/qwen/model"

DATA_PATH=data/finetune_from_gpt5.jsonl \
OUTPUT_DIR=artifacts/lora/qwen3-finetuned \
MODEL_NAME=$MODEL_NAME \
NUM_EPOCHS=3 \
LORA_R=16 \
BATCH_SIZE=2 \
bash scripts/train_lora.sh
```

**Step 3: 评测微调后模型**

```bash
python scripts/run_finetuned_eval.py \
    --base-model /path/to/base/model \
    --lora-path artifacts/lora/qwen3-finetuned/lora_adapter \
    --output results/finetuned_eval_results.json
```

**Step 4: 生成对比报告**

```bash
python scripts/compare_results.py \
    --baseline results/gpt5_eval_results.json \
    --finetuned results/finetuned_eval_results.json \
    --output reports/finetune_comparison.md
```

## Qwen3.5 本地部署评测

如果你已经在服务器上部署了 Qwen3.5-9B:

```bash
# 确认服务运行中
curl http://localhost:8000/v1/models

# 运行评测
./scripts/run_qwen_eval.sh --max-cases 50
```

## 依赖

```bash
pip install \
    transformers \
    peft \
    datasets \
    accelerate \
    bitsandbytes \
    scipy \
    numpy \
    matplotlib
```

## 注意事项

1. **GPU 显存**: 9B 模型 + LoRA 需要约 16GB 以上显存，建议使用 A100 或同等算力
2. **训练时间**: 3 epochs 约需 1-2 小时（取决于数据量和硬件）
3. **数据质量**: `--min-f1 0.5` 只选择高质量样本，避免学习错误模式
