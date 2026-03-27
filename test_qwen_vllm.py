#!/usr/bin/env python3
"""使用 vLLM 启动 Qwen3.5-9B 模型"""

import torch
from vllm import LLM, SamplingParams

print("=" * 60)
print("🚀 使用 vLLM 加载 Qwen3.5-9B")
print("=" * 60)

try:
    # 初始化 vLLM 模型
    print("\n1. 初始化 vLLM...")
    llm = LLM(
        model="Qwen/Qwen3.5-9B",
        trust_remote_code=True,
        dtype="bfloat16",
        tensor_parallel_size=1,
        max_model_len=4096,
    )
    print("   ✅ vLLM 初始化成功")

    # 创建采样参数
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=200,
    )

    # 测试对话
    print("\n2. 测试对话...")

    # 问题 1
    prompts = ["你好！请用中文简单介绍一下你自己。"]
    outputs = llm.generate(prompts, sampling_params)

    for output in outputs:
        prompt = output.prompt
        generated_text = output.outputs[0].text
        print(f"\n👤 用户: {prompt}")
        print(f"\n🤖 Qwen3.5: {generated_text}")

    print("\n" + "=" * 60)

    # 问题 2
    prompts = ["Python 中如何计算斐波那契数列？请给个简单的例子。"]
    outputs = llm.generate(prompts, sampling_params)

    for output in outputs:
        prompt = output.prompt
        generated_text = output.outputs[0].text
        print(f"\n👤 用户: {prompt}")
        print(f"\n🤖 Qwen3.5: {generated_text}")

    print("\n" + "=" * 60)
    print("✅ vLLM 测试成功！Qwen3.5-9B 模型运行正常！")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
