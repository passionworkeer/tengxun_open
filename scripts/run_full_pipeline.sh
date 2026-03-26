#!/bin/bash
#
# 完整微调流程脚本
#
# 用法:
#   ./scripts/run_full_pipeline.sh --step all
#
# Steps:
#   1. generate_data   - 从GPT结果生成微调数据
#   2. train           - 训练LoRA
#   3. evaluate        - 评测微调后模型
#   4. all             - 执行全部步骤
#

set -e

STEP="${1:-all}"

# 参数
GPT5_RESULTS="results/gpt5_eval_results.json"
FINETUNE_DATA="data/finetune_from_gpt5.jsonl"
LORA_OUTPUT="artifacts/lora/qwen3-finetuned"
BASE_MODEL="Qwen/Qwen2.5-7B-Instruct"  # 修改为你部署的模型路径

echo "=========================================="
echo "Qwen Fine-tuning Pipeline"
echo "=========================================="
echo "Step: $STEP"
echo "=========================================="

# Step 1: 生成微调数据
if [[ "$STEP" == "generate_data" ]] || [[ "$STEP" == "all" ]]; then
    echo ""
    echo "[Step 1/3] 生成微调数据..."
    echo "------------------------------------------"
    
    if [ ! -f "$GPT5_RESULTS" ]; then
        echo "ERROR: GPT5 results not found: $GPT5_RESULTS"
        echo "请先运行 GPT5 评测"
        exit 1
    fi
    
    python3 scripts/generate_finetune_data.py \
        --input "$GPT5_RESULTS" \
        --output "$FINETUNE_DATA" \
        --min-f1 0.5
    
    echo "[Step 1/3] 完成!"
fi

# Step 2: 训练LoRA
if [[ "$STEP" == "train" ]] || [[ "$STEP" == "all" ]]; then
    echo ""
    echo "[Step 2/3] 训练LoRA..."
    echo "------------------------------------------"
    
    if [ ! -f "$FINETUNE_DATA" ]; then
        echo "ERROR: Finetune data not found: $FINETUNE_DATA"
        echo "请先运行 Step 1 生成数据"
        exit 1
    fi
    
    DATA_PATH="$FINETUNE_DATA" \
    OUTPUT_DIR="$LORA_OUTPUT" \
    MODEL_NAME="$BASE_MODEL" \
    NUM_EPOCHS=3 \
    LORA_R=16 \
    BATCH_SIZE=2 \
    bash scripts/train_lora.sh
    
    echo "[Step 2/3] 完成!"
fi

# Step 3: 评测微调后模型
if [[ "$STEP" == "evaluate" ]] || [[ "$STEP" == "all" ]]; then
    echo ""
    echo "[Step 3/3] 评测微调后模型..."
    echo "------------------------------------------"
    
    if [ ! -d "$LORA_OUTPUT" ]; then
        echo "ERROR: LoRA output not found: $LORA_OUTPUT"
        echo "请先运行 Step 2 训练模型"
        exit 1
    fi
    
    python3 scripts/run_finetuned_eval.py \
        --base-model "$BASE_MODEL" \
        --lora-path "$LORA_OUTPUT/lora_adapter" \
        --output "results/finetuned_eval_results.json"
    
    # 生成对比报告
    echo ""
    echo "生成对比报告..."
    python3 scripts/compare_results.py \
        --baseline results/gpt5_eval_results.json \
        --finetuned results/finetuned_eval_results.json \
        --output reports/finetune_comparison.md
    
    echo "[Step 3/3] 完成!"
fi

echo ""
echo "=========================================="
echo "Pipeline 完成!"
echo "=========================================="