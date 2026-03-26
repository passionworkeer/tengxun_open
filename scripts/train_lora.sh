#!/bin/bash
# 
# Qwen3.5 LoRA 微调训练脚本
#
# 依赖:
#   pip install qwen_lora peft transformers datasets accelerate
#
# 用法:
#   ./scripts/train_lora.sh --data data/finetune_from_gpt5.jsonl --output artifacts/lora/qwen3-finetuned
#

set -e

# 默认参数
DATA_PATH="data/finetune_from_gpt5.jsonl"
OUTPUT_DIR="artifacts/lora/qwen3-finetuned"
MODEL_NAME="Qwen/Qwen2.5-7B-Instruct"  # 或本地路径
LORA_R=16
LORA_ALPHA=32
BATCH_SIZE=2
NUM_EPOCHS=3
LEARNING_RATE=2e-4
MAX_SEQ_LENGTH=2048

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --data)
            DATA_PATH="$2"
            shift 2
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --model)
            MODEL_NAME="$2"
            shift 2
            ;;
        --lora-r)
            LORA_R="$2"
            shift 2
            ;;
        --epochs)
            NUM_EPOCHS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Qwen LoRA Fine-tuning"
echo "=========================================="
echo "Model:       $MODEL_NAME"
echo "Data:        $DATA_PATH"
echo "Output:      $OUTPUT_DIR"
echo "LoRA R:      $LORA_R"
echo "Epochs:      $NUM_EPOCHS"
echo "=========================================="

# 检查数据文件
if [ ! -f "$DATA_PATH" ]; then
    echo "ERROR: Data file not found: $DATA_PATH"
    echo "生成数据: python scripts/generate_finetune_data.py ..."
    exit 1
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 使用 Python 运行训练
python3 << 'PYTHON_SCRIPT'
import json
import os
from dataclasses import dataclass, field
from typing import Optional

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
)

# 解析参数
DATA_PATH = os.environ.get("DATA_PATH", "data/finetune_from_gpt5.jsonl")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "artifacts/lora/qwen3-finetuned")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
LORA_R = int(os.environ.get("LORA_R", "16"))
LORA_ALPHA = int(os.environ.get("LORA_ALPHA", "32"))
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "2"))
NUM_EPOCHS = int(os.environ.get("NUM_EPOCHS", "3"))
LEARNING_RATE = float(os.environ.get("LEARNING_RATE", "2e-4"))
MAX_SEQ_LENGTH = int(os.environ.get("MAX_SEQ_LENGTH", "2048"))

def format_for_qwen(sample):
    """将sample格式化为Qwen训练格式"""
    messages = sample["messages"]
    text = ""
    for msg in messages:
        if msg["role"] == "system":
            text += f"<|im_start|>system\n{msg['content']}<|im_end|>\n"
        elif msg["role"] == "user":
            text += f"<|im_start|>user\n{msg['content']}<|im_end|>\n"
        elif msg["role"] == "assistant":
            text += f"<|im_start|>assistant\n{msg['content']}<|im_end|>\n"
    return {"text": text}

def main():
    print(f"Loading model: {MODEL_NAME}")
    
    # 加载模型和tokenizer
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        padding_side="right"
    )
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        torch_dtype=torch.float16,
        device_map="auto",
    )
    model.config.pad_token_id = tokenizer.pad_token_id
    
    # 加载数据
    print(f"Loading data from: {DATA_PATH}")
    dataset = load_dataset("json", data_files=DATA_PATH, split="train")
    
    # 格式化数据
    dataset = dataset.map(format_for_qwen, remove_columns=dataset.column_names)
    
    # 分割训练/验证集
    split = dataset.train_test_split(test_size=0.1)
    train_dataset = split["train"]
    eval_dataset = split["test"]
    
    print(f"Train samples: {len(train_dataset)}")
    print(f"Eval samples: {len(eval_dataset)}")
    
    # 配置 LoRA
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
    )
    
    # 应用 LoRA
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # 训练参数
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=8,
        learning_rate=LEARNING_RATE,
        weight_decay=0.01,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to=["tensorboard"],
        fp16=True,
        dataloader_num_workers=4,
        max_grad_norm=1.0,
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
    )
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )
    
    print("Starting training...")
    trainer.train()
    
    # 保存最终模型
    final_path = f"{OUTPUT_DIR}/final"
    trainer.save_model(final_path)
    tokenizer.save_pretrained(final_path)
    print(f"Model saved to: {final_path}")
    
    # 保存 LoRA adapter
    lora_path = f"{OUTPUT_DIR}/lora_adapter"
    model.save_pretrained(lora_path)
    print(f"LORA adapter saved to: {lora_path}")

if __name__ == "__main__":
    main()
PYTHON_SCRIPT

echo ""
echo "=========================================="
echo "Training completed!"
echo "Output: $OUTPUT_DIR"
echo "=========================================="