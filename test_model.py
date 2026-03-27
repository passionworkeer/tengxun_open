#!/usr/bin/env python3
"""简单测试 Qwen3.5-9B 模型"""

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
    messages = [{"role": "user", "content": "你好，请用一句话介绍 Qwen3.5。"}]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    print("   生成回复...")
    with torch.no_grad():
        generated_ids = model.generate(
            model_inputs.input_ids,
            max_new_tokens=100,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )

    response = tokenizer.batch_decode([
        output_ids[len(input_ids):]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ], skip_special_tokens=True)[0]

    print(f"\n📝 模型回复:\n{response}\n")

    # 显示模型信息
    print("=" * 60)
    print("✅ 模型测试成功！")
    print("=" * 60)
    print(f"\n📊 模型信息:")
    print(f"  模型名称: {model_name}")
    print(f"  精度: bfloat16")
    print(f"  设备: {model.device}")
    print(f"  参数量: {sum(p.numel() for p in model.parameters()) / 1e9:.2f}B")

    print(f"\n🚀 现在可以开始 LoRA 微调:")
    print(f"   bash /workspace/train_lora.sh")

except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()
