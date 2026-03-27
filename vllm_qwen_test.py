#!/usr/bin/env python3
"""使用 vLLM 测试 Qwen3.5-9B 对话功能"""

from vllm import LLM, SamplingParams
from transformers import AutoTokenizer

model_name = "Qwen/Qwen3.5-9B"

print("=" * 60)
print(f"🧪 使用 vLLM 加载模型: {model_name}")
print("=" * 60)

try:
    # 加载 tokenizer
    print("\n1. 加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    print("   ✅ tokenizer 加载成功")

    # 使用 vLLM 加载模型
    print("\n2. 使用 vLLM 加载模型...")
    llm = LLM(
        model=model_name,
        trust_remote_code=True,
        tensor_parallel_size=1,
        dtype="bfloat16",
        max_model_len=8192,
    )
    print("   ✅ 模型加载成功")

    # 设置采样参数
    sampling_params = SamplingParams(
        temperature=0.7,
        top_p=0.9,
        max_tokens=200,
    )

    # 测试对话
    print("\n3. 测试对话...")
    
    # 第一个问题
    prompt = "你好！请用中文简单介绍一下你自己。"
    print(f"\n👤 用户: {prompt}")
    print("\n🤖 Qwen3.5: ", end="", flush=True)
    
    outputs = llm.generate([prompt], sampling_params)
    print(outputs[0].outputs[0].text)
    
    print("\n" + "=" * 60)
    
    # 第二个问题
    prompt = "Python 中如何计算斐波那契数列？请给个简单的例子。"
    print(f"\n👤 用户: {prompt}")
    print("\n🤖 Qwen3.5: ", end="", flush=True)
    
    sampling_params.max_tokens = 300
    outputs = llm.generate([prompt], sampling_params)
    print(outputs[0].outputs[0].text)
    
    print("\n" + "=" * 60)
    print("✅ vLLM 对话测试成功！Qwen3.5-9B 模型运行正常！")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
