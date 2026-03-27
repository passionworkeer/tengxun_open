#!/bin/bash
# Step 2: 启动微调训练

set -e

echo "============================================================"
echo "🚀 Step 2: 启动微调训练"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 检查数据
echo ""
echo "📋 检查微调数据..."
if [ ! -f "$PROJECT_DIR/data/finetune_dataset_500.jsonl" ]; then
    echo "❌ 数据未找到: data/finetune_dataset_500.jsonl"
    exit 1
fi
echo "✅ 数据存在"

# 检查模型
echo ""
echo "📋 检查模型缓存..."
if [ ! -d "$HOME/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B" ]; then
    echo "⚠️ 模型未下载，请先运行部署"
    exit 1
fi
echo "✅ 模型缓存存在"

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 启动训练
echo ""
echo "⏳ 启动训练..."
echo "============================================================"
cd "$PROJECT_DIR/LLaMA-Factory"

nohup llamafactory-cli train "$PROJECT_DIR/lora_config.yaml" \
    > "$PROJECT_DIR/logs/train.log" 2>&1 &

TRAIN_PID=$!
echo $TRAIN_PID > "$PROJECT_DIR/logs/train.pid"

echo "📝 训练进程: $TRAIN_PID"
echo "📄 日志: $PROJECT_DIR/logs/train.log"
echo ""
echo "查看进度: tail -f $PROJECT_DIR/logs/train.log"
echo "============================================================"