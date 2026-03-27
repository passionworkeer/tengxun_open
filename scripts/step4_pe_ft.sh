#!/bin/bash
# Step 4: PE+FT评测

set -e

MODEL_PATH=${1:-"$(dirname "$0")/../saves/qwen3.5-9b/lora/finetune_dep"}

echo "============================================================"
echo "🚀 Step 4: PE+FT评测"
echo "============================================================"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ 模型未找到: $MODEL_PATH"
    exit 1
fi

# 检查vLLM服务
echo ""
echo "📡 检查vLLM服务..."
if ! curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo "❌ vLLM服务未运行"
    exit 1
fi
echo "✅ vLLM服务运行中"

# 运行PE+FT评测
echo ""
echo "⏳ 运行PE+FT评测..."
echo "============================================================"

cd "$PROJECT_DIR"

python evaluation/run_qwen_eval.py \
    --cases data/eval_cases_final_v1.json \
    --base-url http://localhost:8000/v1 \
    --model Qwen3.5-9B-Instruct-FT \
    --output results/qwen_pe_ft_results.json

echo ""
echo "📊 结果保存在: results/qwen_pe_ft_results.json"
echo "============================================================"