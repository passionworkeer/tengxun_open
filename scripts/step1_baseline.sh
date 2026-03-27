#!/bin/bash
# Step 1: Qwen基线推理（未微调版本）
# ============================================================
# 功能: 使用原始Qwen3.5-9B模型进行评测，获取基线分数
# 用法: bash scripts/step1_baseline.sh [模型路径]
# 示例: bash scripts/step1_baseline.sh ~/models/Qwen3.5-9B-Instruct
# ============================================================

set -e

# 默认模型路径
MODEL_PATH=${1:-"~/models/Qwen3.5-9B-Instruct"}

echo "============================================================"
echo "🚀 Step 1: Qwen基线推理（未微调）"
echo "============================================================"

# 检查模型目录是否存在
echo ""
echo "📋 检查模型文件..."
if [ ! -d "$MODEL_PATH" ]; then
    echo "❌ 模型目录未找到: $MODEL_PATH"
    echo ""
    echo "请先部署模型，运行:"
    echo "   python full_deploy_qwen35.py"
    exit 1
fi
echo "✅ 模型目录存在: $MODEL_PATH"

# 检查vLLM/AP服务是否运行
echo ""
echo "📡 检查推理服务..."
if ! curl -s http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo "⚠️ 推理服务未运行，请先启动服务:"
    echo "   python simple_qwen_server.py"
    echo ""
    echo "或者使用其他方式启动服务，确保API在 http://localhost:8000/v1"
    exit 1
fi
echo "✅ 推理服务运行中: http://localhost:8000/v1"

# 执行基线评测
echo ""
echo "⏳ 正在运行基线评测，请稍候..."
echo "============================================================"
echo ""

# 切换到项目根目录
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 运行评测脚本
python evaluation/run_qwen_eval.py \
    --cases data/eval_cases_final_v1.json \
    --base-url http://localhost:8000/v1 \
    --model Qwen3.5-9B-Instruct \
    --output results/qwen_baseline.json

echo ""
echo "============================================================"
echo "✅ 基线评测完成！"
echo "============================================================"
echo ""
echo "📊 结果文件: results/qwen_baseline.json"
echo ""
echo "📈 查看结果: python -c \"import json; d=json.load(open('results/qwen_baseline.json')); print(sum(r.get('f1',0) for r in d)/len(d))\""
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