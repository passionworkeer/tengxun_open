#!/bin/bash
# 完整的微调训练脚本 - 带详细日志记录

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs/training_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$LOG_DIR"

echo "============================================================"
echo "🚀 完整微调训练 - 带详细日志"
echo "============================================================"
echo "📁 日志目录: $LOG_DIR"

# 保存超参数配置
echo "📝 保存配置文件..."
cp "$SCRIPT_DIR/lora_config.yaml" "$LOG_DIR/lora_config.yaml"
cp "$SCRIPT_DIR/HYPERPARAMS_REASONING.md" "$LOG_DIR/"

# 创建训练信息文件
cat > "$LOG_DIR/training_info.txt" << 'EOF'
============================================================
Qwen3.5-9B LoRA 微调训练信息
============================================================

开始时间: $(date)
模型: Qwen/Qwen3.5-9B
数据集: fintune_qwen_dep (500条)
任务: 代码依赖链分析

超参数:
- lora_rank: 8
- lora_alpha: 16
- learning_rate: 5e-5
- batch_size: 1 (accum 8)
- epochs: 3
- bf16: true
EOF

echo "$(date)" >> "$LOG_DIR/training_info.txt"

# 记录数据集统计
echo "📊 数据集统计..."
python3 << EOF >> "$LOG_DIR/dataset_stats.txt"
import json

with open("$SCRIPT_DIR/data/finetune_dataset_500.jsonl", 'r') as f:
    data = [json.loads(line) for line in f]

print(f"总数据量: {len(data)}")
print(f"字段: {list(data[0].keys())}")

# 难度分布
from collections import Counter
difficulty = Counter(d.get('difficulty', 'unknown') for d in data)
print(f"\n难度分布: {dict(difficulty)}")

# 类型分布
category = Counter(d.get('category', 'unknown') for d in data)
print(f"类型分布: {dict(category)}")

# 失败类型
failure = Counter(d.get('failure_type', 'unknown') for d in data)
print(f"失败类型: {dict(failure)}")
EOF

# 启动训练，实时记录
echo ""
echo "⏳ 开始训练..."
echo "============================================================"

cd "$SCRIPT_DIR/LLaMA-Factory"

# 记录训练日志
llamafactory-cli train "$SCRIPT_DIR/lora_config.yaml" 2>&1 | tee "$LOG_DIR/train_output.log"

# 训练结束记录
echo ""
echo "============================================================"
echo "✅ 训练完成"
echo "============================================================"
echo "时间: $(date)" >> "$LOG_DIR/training_info.txt"

echo ""
echo "📁 训练日志保存在: $LOG_DIR/"
echo ""
echo "文件列表:"
ls -la "$LOG_DIR/"

echo ""
echo "📊 后续分析使用:"
echo "  - 查看损失曲线: tensorboard --logdir=$LOG_DIR/../runs"
echo "  - 验证模型: llamafactory-cli chat $SCRIPT_DIR/lora_config.yaml"