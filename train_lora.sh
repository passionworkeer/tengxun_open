#!/bin/bash
# Qwen3.5-9B bf16-LoRA 微调启动脚本

set -e

echo "============================================================"
echo "🚀 开始 Qwen3.5-9B bf16-LoRA 微调"
echo "============================================================"

# 检查模型是否已下载
echo ""
echo "📋 检查模型缓存..."
if [ ! -d "$HOME/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B" ]; then
    echo "❌ 模型未下载，请先运行:"
    echo "   python /workspace/full_deploy_qwen35.py"
    exit 1
fi

echo "✅ 模型缓存存在"
echo ""

# 进入 LLaMA-Factory 目录
cd /workspace/LLaMA-Factory

# 开始训练
echo "============================================================"
echo "⏳ 开始训练..."
echo "============================================================"
echo ""

llamafactory-cli train /workspace/lora_config.yaml

echo ""
echo "============================================================"
echo "✅ 训练完成！"
echo "============================================================"
echo ""
echo "📁 模型保存在: ./saves/qwen3.5-9b/lora/sft"
echo ""
echo "🧪 测试微调后的模型:"
echo "   llamafactory-cli chat /workspace/lora_config.yaml"
echo ""
echo "📊 查看训练曲线:"
echo "   ls -la ./saves/qwen3.5-9b/lora/sft/training_loss.png"
