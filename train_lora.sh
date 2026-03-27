#!/bin/bash
# Qwen3.5-9B bf16-LoRA 微调启动脚本
# 用法: bash train_lora.sh
# 说明: 自动检查模型是否存在，然后启动训练

set -e

echo "============================================================"
echo "🚀 开始 Qwen3.5-9B bf16-LoRA 微调训练"
echo "============================================================"

# 检查模型是否已下载
echo ""
echo "📋 检查模型缓存..."
# 模型默认下载到 HuggingFace 缓存目录
MODEL_CACHE_DIR="$HOME/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B"
if [ ! -d "$MODEL_CACHE_DIR" ]; then
    echo "❌ 模型未下载，请先运行部署脚本:"
    echo "   python full_deploy_qwen35.py"
    echo ""
    echo "或者手动下载模型到: $MODEL_CACHE_DIR"
    exit 1
fi

echo "✅ 模型缓存存在: $MODEL_CACHE_DIR"
echo ""

# 进入 LLaMA-Factory 目录（脚本所在目录的上级）
cd "$(dirname "$0")/LLaMA-Factory"

# 获取配置文件路径（相对于项目根目录）
CONFIG_PATH="$(dirname "$0")/lora_config.yaml"

# 检查配置文件是否存在
if [ ! -f "$CONFIG_PATH" ]; then
    echo "❌ 配置文件未找到: $CONFIG_PATH"
    exit 1
fi

echo "📝 配置文件: $CONFIG_PATH"
echo ""

# 开始训练
echo "============================================================"
echo "⏳ 正在进行训练，请耐心等待..."
echo "============================================================"
echo ""
echo "📊 训练过程中可使用以下命令监控:"
echo "   - 查看实时日志: tail -f logs/train.log"
echo "   - 查看GPU状态: nvidia-smi"
echo ""

# 启动训练
llamafactory-cli train "$CONFIG_PATH"

# 训练完成
echo ""
echo "============================================================"
echo "✅ 训练完成！"
echo "============================================================"
echo ""
echo "📁 微调模型保存路径:"
echo "   ./saves/qwen3.5-9b/lora/finetune_dep/"
echo ""
echo "🧪 测试微调后的模型:"
echo "   cd LLaMA-Factory"
echo "   llamafactory-cli chat $CONFIG_PATH"
echo ""
echo "📊 查看训练曲线:"
echo "   ls -la ./saves/qwen3.5-9b/lora/finetune_dep/"
