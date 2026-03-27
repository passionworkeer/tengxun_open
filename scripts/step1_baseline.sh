#!/bin/bash
# Step 1: Qwen基线推理

set -e

MODEL_PATH=${1:-"~/models/Qwen3.5-9B-Instruct"}

echo "============================================================"
echo "🚀 Step 1: Qwen基线推理"
echo "============================================================"

# 检查模型
echo ""
echo "📋 检查模型..."
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ 模型未找到: $MODEL_PATH"
    echo "请先部署模型"
    exit 1
fi
echo "✅ 模型存在: $MODEL_PATH"

# 检查vLLM服务是否运行
echo ""
echo "📡 检查vLLM服务..."
if ! curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo "❌ vLLM服务未运行，请先启动:"
    echo "   python simple_qwen_server.py"
    exit 1
fi
echo "✅ vLLM服务运行中"

# 运行基线推理
echo ""
echo "⏳ 运行基线推理..."
echo "============================================================"

cd "$(dirname "$0")/.."

python evaluation/run_qwen_eval.py \
    --cases data/eval_cases_final_v1.json \
    --base-url http://localhost:8000/v1 \
    --model Qwen3.5-9B-Instruct \
    --output results/qwen_baseline.json

echo ""
echo "📊 结果保存在: results/qwen_baseline.json"
echo "============================================================"