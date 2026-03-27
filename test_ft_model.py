#!/usr/bin/env python3
"""
快速测试微调模型的推理能力
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

base_model_path = "Qwen/Qwen3.5-9B"
adapter_path = "LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print("Loading base model...")
model = AutoModelForCausalLM.from_pretrained(
    base_model_path,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True,
)

print("Loading adapter...")
model = PeftModel.from_pretrained(model, adapter_path)
model.eval()

# 测试问题
prompt = """Question: Which real class does `celery.Celery` resolve to in the top-level lazy API?

Entry Symbol: celery.Celery
Entry File: celery/__init__.py

IMPORTANT: Return ONLY a valid JSON object, no other text.
Format: {"ground_truth": {"direct_deps": ["module.path"], "indirect_deps": [], "implicit_deps": []}}
Example: {"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}"""

system_prompt = "You are a JSON-only response bot. You must ONLY output valid JSON objects, no explanations, no markdown, no extra text. Your response must be parseable by json.loads()."

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": prompt},
]

text = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True
)

inputs = tokenizer(text, return_tensors="pt").to(model.device)

print("Generating response...")
with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=200,
        temperature=0.0,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )

generated_tokens = outputs[0][inputs["input_ids"].shape[1] :]
response = tokenizer.decode(generated_tokens, skip_special_tokens=True)

print("\n" + "=" * 50)
print("Model Response:")
print("=" * 50)
print(response)
print("=" * 50)
print(f"Response length: {len(response)} characters")
