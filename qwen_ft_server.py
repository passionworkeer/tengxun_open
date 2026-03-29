#!/usr/bin/env python3
"""微调后的 Qwen3.5 API 服务器（支持 LoRA adapter）"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import List, Optional
import os

app = FastAPI(title="Qwen3.5 FT API Server")

# 全局变量
model = None
tokenizer = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.8


@app.on_event("startup")
async def load_model():
    global model, tokenizer
    model_name = "Qwen/Qwen3.5-9B"
    adapter_path = os.getenv(
        "LORA_ADAPTER_PATH",
        "LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745",
    )

    print(f"正在加载基础模型: {model_name}")
    print(f"LoRA adapter: {adapter_path}")

    # 加载 tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    print("✓ Tokenizer 加载成功")

    # 加载基础模型
    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    print("✓ 基础模型加载成功")

    # 加载 LoRA adapter
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model = model.merge_and_unload()  # 合并权重加速推理
    print("✓ LoRA adapter 加载并合并成功")
    print(f"✓ 模型设备: {model.device}")


@app.get("/health")
async def health():
    return {"status": "healthy", "model": "Qwen/Qwen3.5-9B-FT"}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    global model, tokenizer

    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        # 准备消息
        messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # 应用聊天模板
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # 编码输入
        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        # 生成回复
        with torch.no_grad():
            generated_ids = model.generate(
                model_inputs.input_ids,
                max_new_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                do_sample=True,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )

        # 解码输出
        generated_ids = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

        return {
            "id": "chatcmpl-ft-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "Qwen/Qwen3.5-9B-FT",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": len(model_inputs.input_ids[0]),
                "completion_tokens": len(generated_ids[0]),
                "total_tokens": len(model_inputs.input_ids[0]) + len(generated_ids[0]),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
