#!/usr/bin/env python3
"""直接使用 Qwen 模型文件进行对话测试"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from modelscope import snapshot_download

# 使用模型 ID
model_dir = snapshot_download('Qwen/Qwen3.5-9B', cache_dir='/root/.cache/modelscope/hub')

print("=" * 60)
print(f"🧪 加载模型: {model_dir}")
print("=" * 60)

try:
    # 加载 tokenizer
    print("\n1. 加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    print("   ✅ tokenizer 加载成功")

    # 加载模型
    print("\n2. 加载模型权重...")
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16
    ).eval()
    print("   ✅ 模型加载成功")
    print(f"   设备: {model.device}")

    # 测试对话
    print("\n3. 测试对话...")
    
    # 第一个问题
    response, history = model.chat(tokenizer, "你好！请用中文简单介绍一下你自己。", history=None)
    print("\n👤 用户: 你好！请用中文简单介绍一下你自己。")
    print(f"\n🤖 Qwen3.5: {response}")
    
    print("\n" + "=" * 60)
    
    # 第二个问题
    response, history = model.chat(tokenizer, "Python 中如何计算斐波那契数列？", history=history)
    print("\n👤 用户: Python 中如何计算斐波那契数列？")
    print(f"\n🤖 Qwen3.5: {response}")
    
    print("\n" + "=" * 60)
    print("✅ 对话测试成功！Qwen3.5-9B 模型运行正常！")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
