#!/usr/bin/env python3
"""Qwen3.5-9B 本地部署脚本"""

import sys
import os
from pathlib import Path

print("=" * 70)
print("Qwen3.5-9B 模型部署测试")
print("=" * 70)

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch

    print("\n✓ 核心库导入成功")
    print(f"  - PyTorch: {torch.__version__}")
    print(f"  - CUDA 可用: {torch.cuda.is_available()}")
    
    # 模型配置
    model_name = "Qwen/Qwen3.5-9B"
    
    print(f"\n正在加载模型: {model_name}")
    print("注意: 首次运行需要下载模型文件 (~18GB)")
    
    # 加载 tokenizer
    print("\n[1/3] 加载 tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=True
    )
    print("✓ Tokenizer 加载成功")
    
    # 加载模型 (CPU模式)
    print("\n[2/3] 加载模型 (CPU 模式)...")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        device_map="cpu",
        trust_remote_code=True
    )
    print("✓ 模型加载成功")
    
    # 准备输入
    print("\n[3/3] 测试对话...")
    prompt = "你好！请用中文简单介绍一下你自己。"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt}
    ]
    
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    print(f"\n用户输入: {prompt}")
    print("生成回答中...")
    
    # 生成回复
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        generated_ids = model.generate(
            model_inputs.input_ids,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.8,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id
        )
    
    generated_ids = [
        output_ids[len(input_ids):] 
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    print(f"\n模型回答:\n{response}")
    print("\n" + "=" * 70)
    print("✓ Qwen3.5-9B 部署测试完成！")
    print("=" * 70)
    
except KeyboardInterrupt:
    print("\n\n用户中断操作")
    sys.exit(0)
    
except Exception as e:
    print(f"\n\n✗ 错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
