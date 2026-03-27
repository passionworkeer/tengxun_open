#!/usr/bin/env python3
"""简单测试 Qwen3.5-9B 对话功能"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

model_name = "Qwen/Qwen3.5-9B"

print("=" * 60)
print(f"🧪 加载模型: {model_name}")
print("=" * 60)

try:
    # 加载 tokenizer
    print("\n1. 加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    print("   ✅ tokenizer 加载成功")

    # 加载模型（使用 bf16）
    print("\n2. 加载模型权重（bf16）...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True
    )
    print("   ✅ 模型加载成功")
    print(f"   设备: {model.device}")

    # 测试对话
    print("\n3. 测试对话...")
    
    # 第一个问题
    messages = [{"role": "user", "content": "你好！请用中文简单介绍一下你自己。"}]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    print("\n👤 用户: 你好！请用中文简单介绍一下你自己。")
    print("\n🤖 Qwen3.5: ", end="", flush=True)
    
    with torch.no_grad():
        generated_ids = model.generate(
            model_inputs.input_ids,
            max_new_tokens=200,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )
    
    response = tokenizer.batch_decode([
        output_ids[len(input_ids):]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ], skip_special_tokens=True)[0]
    
    print(response)
    
    print("\n" + "=" * 60)
    
    # 第二个问题
    messages = [{"role": "user", "content": "Python 中如何计算斐波那契数列？请给个简单的例子。"}]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    print("\n👤 用户: Python 中如何计算斐波那契数列？请给个简单的例子。")
    print("\n🤖 Qwen3.5: ", end="", flush=True)
    
    with torch.no_grad():
        generated_ids = model.generate(
            model_inputs.input_ids,
            max_new_tokens=300,
            do_sample=True,
            temperature=0.7,
            top_p=0.9,
            pad_token_id=tokenizer.eos_token_id
        )
    
    response = tokenizer.batch_decode([
        output_ids[len(input_ids):]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ], skip_special_tokens=True)[0]
    
    print(response)
    
    print("\n" + "=" * 60)
    print("✅ 对话测试成功！Qwen3.5-9B 模型运行正常！")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
