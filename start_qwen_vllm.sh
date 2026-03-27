#!/bin/bash

# 停止旧的进程
pkill -f "vllm.entrypoints.api_server"

echo "🚀 启动 Qwen3.5-9B vLLM 服务..."
echo "=================================="

# 启动 vLLM API 服务器
python -m vllm.entrypoints.api_server \
    --model Qwen/Qwen3.5-9B \
    --dtype bfloat16 \
    --trust-remote-code \
    --host 0.0.0.0 \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 8192 &

VLLM_PID=$!
echo "vLLM 进程 ID: $VLLM_PID"

# 等待服务启动
echo "⏳ 等待服务启动..."
for i in {1..60}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ 服务已启动！"
        break
    fi
    echo "   等待中... ($i/60)"
    sleep 5
done

# 检查服务状态
echo ""
echo "📊 检查服务状态..."
curl -s http://localhost:8000/health

echo ""
echo "=================================="
echo "📝 测试对话..."
echo "=================================="

# 发送测试请求
curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "Qwen/Qwen3.5-9B",
        "messages": [
            {
                "role": "user",
                "content": "你好！请用中文简单介绍一下你自己。"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }'

echo ""
echo "=================================="
echo "✅ 测试完成！vLLM 服务正在后台运行"
echo "📍 API 地址: http://localhost:8000"
echo "🔧 停止服务: pkill -f 'vllm.entrypoints.api_server'"
echo "=================================="
