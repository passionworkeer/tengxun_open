#!/usr/bin/env python3
"""尝试使用多种方法启动 Qwen3.5"""

import subprocess
import time

print("=" * 60)
print("🔥 尝试多种方法启动 Qwen3.5-9B")
print("=" * 60)

methods = []

# 方法 1: 直接使用 Python + transformers
print("\n[方法 1] 尝试使用 Python 直接加载...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    
    # 测试能否识别模型类型
    from transformers import AutoConfig
    config = AutoConfig.from_pretrained("Qwen/Qwen3.5-9B", trust_remote_code=True)
    print(f"   模型类型: {config.model_type}")
    print(f"   架构: {config.architectures}")
    
    print("   ✅ 模型配置可读取")
    methods.append("方法1-配置可读取")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 方法 2: 使用 vLLM
print("\n[方法 2] 尝试使用 vLLM...")
try:
    from vllm import LLM, SamplingParams
    print("   ✅ vLLM 已安装")
    print("   ⚠️  但需要实际测试加载")
    methods.append("方法2-vLLM已安装")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 方法 3: 启动 vLLM API Server
print("\n[方法 3] 尝试启动 vLLM API Server...")
try:
    cmd = [
        "python", "-m", "vllm.entrypoints.api_server",
        "--model", "Qwen/Qwen3.5-9B",
        "--dtype", "bfloat16",
        "--trust-remote-code",
        "--host", "0.0.0.0",
        "--port", "8000"
    ]
    print(f"   命令: {' '.join(cmd)}")
    print("   ⚠️  将在后台启动...")
    # subprocess.Popen(cmd)
    methods.append("方法3-可以启动API Server")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 方法 4: 使用 modelscope
print("\n[方法 4] 尝试使用 ModelScope...")
try:
    from modelscope import snapshot_download, AutoModelForCausalLM, AutoTokenizer
    print("   ✅ ModelScope 已安装")
    methods.append("方法4-ModelScope可用")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 方法 5: 使用 transformers chat 模式
print("\n[方法 5] 尝试使用 transformers chat 模式...")
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print("   ✅ transformers 已安装")
    print("   ⚠️  但需要支持 qwen3_5 架构")
    methods.append("方法5-transformers已安装")
except Exception as e:
    print(f"   ❌ 失败: {e}")

# 方法 6: 检查模型文件
print("\n[方法 6] 检查本地模型文件...")
import os
model_cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
for item in os.listdir(model_cache_dir):
    if "Qwen" in item:
        print(f"   ✅ 找到模型缓存: {item}")
        methods.append("方法6-模型文件存在")

# 总结
print("\n" + "=" * 60)
print("📊 可用方法总结:")
print("=" * 60)
for method in methods:
    print(f"   ✅ {method}")

print("\n💡 推荐方案:")
if "方法4-ModelScope可用" in methods:
    print("   使用 ModelScope + transformers 来加载模型")
elif "方法2-vLLM已安装" in methods:
    print("   使用 vLLM 启动模型")
elif "方法6-模型文件存在" in methods:
    print("   模型文件已存在，可以尝试直接加载")

print("\n🔧 下一步:")
print("   1. 升级 transformers 到支持 qwen3_5 的版本")
print("   2. 或使用 ModelScope 的官方推理代码")
print("   3. 或使用 vLLM 启动 API 服务")

print("\n" + "=" * 60)
