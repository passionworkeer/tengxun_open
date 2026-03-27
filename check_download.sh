#!/bin/bash
# 检查 Qwen3.5-9B 下载进度

echo "============================================================"
echo "📥 Qwen3.5-9B 下载进度检查"
echo "============================================================"
echo ""

MODEL_CACHE="$HOME/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B*"

# 检查进程
if pgrep -f "python.*full_deploy" > /dev/null; then
    echo "✅ 下载进程运行中"
    echo ""
else
    echo "⚠️  下载进程未运行"
    echo ""
fi

# 检查文件
echo "📁 已下载文件统计:"
echo ""

# 统计不同大小的文件数量
echo "  按文件大小分类:"
for size in "10M" "100M" "500M" "1G"; do
    count=$(find $MODEL_CACHE -type f -size +$size 2>/dev/null | wc -l)
    echo "    > $size: $count 个文件"
done

echo ""

# 总大小
total_size=$(du -sh $MODEL_CACHE 2>/dev/null | cut -f1)
echo "  📦 已下载总量: $total_size"
echo ""

# 预计大小
echo "  📊 预计总大小: ~18-20 GB"
echo ""

# 列出最大的文件
echo "📋 已下载的最大文件:"
find $MODEL_CACHE -type f -exec du -h {} + 2>/dev/null | sort -rh | head -10 | while read size file; do
    filename=$(basename "$file")
    echo "  $size  $filename"
done

echo ""
echo "============================================================"
echo "💡 提示:"
echo "  - 首次下载需要 10-30 分钟（取决于网络）"
echo "  - 完成后可运行: python /workspace/full_deploy_qwen35.py"
echo "  - 或直接开始 LoRA 微调: bash /workspace/train_lora.sh"
echo "============================================================"
