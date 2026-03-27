#!/usr/bin/env python3
"""
完整部署 Qwen3.5-9B 模型
下载并验证模型，为 bf16-LoRA 微调做准备
"""

import os
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from pathlib import Path

def check_environment():
    """检查环境"""
    print("=" * 60)
    print("🔍 检查环境")
    print("=" * 60)

    # 检查 CUDA
    cuda_available = torch.cuda.is_available()
    if cuda_available:
        print(f"✅ CUDA 可用: {torch.cuda.get_device_name(0)}")
        print(f"   显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("⚠️  CUDA 不可用，将使用 CPU")

    # 检查磁盘空间
    disk = os.statvfs('/')
    free_gb = disk.f_bavail * disk.f_frsize / (1024**3)
    print(f"✅ 可用磁盘空间: {free_gb:.1f} GB")

    if free_gb < 40:
        print("⚠️  警告: 磁盘空间不足 40GB")
        return False

    return cuda_available, free_gb

def download_model(model_name):
    """下载模型"""
    print("\n" + "=" * 60)
    print(f"📥 开始下载模型: {model_name}")
    print("=" * 60)
    print("⏳ 这可能需要 10-30 分钟，请耐心等待...\n")

    try:
        # 下载 tokenizer
        print("1. 下载 tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        print("   ✅ tokenizer 下载完成")

        # 下载模型（使用 bf16 优化显存占用）
        print("\n2. 下载模型权重...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True
        )
        print("   ✅ 模型权重下载完成")

        return model, tokenizer

    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return None, None

def test_model(model, tokenizer):
    """测试模型"""
    print("\n" + "=" * 60)
    print("🧪 测试模型")
    print("=" * 60)

    try:
        messages = [{"role": "user", "content": "你好，请介绍一下你自己。"}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

        print("⏳ 生成回复...")
        with torch.no_grad():
            generated_ids = model.generate(
                model_inputs.input_ids,
                max_new_tokens=128,
                do_sample=True,
                temperature=0.7,
                top_p=0.9
            )

        response = tokenizer.batch_decode([
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ], skip_special_tokens=True)[0]

        print(f"\n📝 模型回复:\n{response}\n")
        print("✅ 模型测试成功")
        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def save_config(model_name):
    """保存配置信息"""
    print("\n" + "=" * 60)
    print("💾 保存配置")
    print("=" * 60)

    config_path = Path("/workspace/qwen35_config.txt")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(f"模型名称: {model_name}\n")
        f.write(f"精度: bfloat16\n")
        f.write(f"微调方式: LoRA\n")
        f.write(f"部署日期: {os.popen('date').read().strip()}\n")
        f.write(f"\nLLaMA Factory 配置示例:\n\n")
        f.write("""### model
model_name_or_path: Qwen/Qwen3.5-9B

### method
stage: sft
do_train: true
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16
lora_dropout: 0.05

### dataset
dataset: alpaca_zh
template: qwen
cutoff_len: 512
max_samples: 1000
overwrite_cache: true
preprocessing_num_workers: 16

### output
output_dir: ./saves/qwen3.5-9b/lora
logging_steps: 10
save_steps: 500
plot_loss: true
overwrite_output_dir: true

### train
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 5.0e-5
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true
ddp_timeout: 180000000

### eval
val_size: 0.1
per_device_eval_batch_size: 1
eval_strategy: steps
eval_steps: 500
""")

    print(f"✅ 配置已保存到: {config_path}")

def main():
    """主函数"""
    model_name = "Qwen/Qwen3.5-9B"

    # 检查环境
    result = check_environment()
    if not result:
        print("❌ 环境检查失败")
        return 1

    cuda_available, free_gb = result

    # 下载模型
    model, tokenizer = download_model(model_name)
    if model is None:
        return 1

    # 测试模型
    if not test_model(model, tokenizer):
        return 1

    # 保存配置
    save_config(model_name)

    # 完成
    print("\n" + "=" * 60)
    print("🎉 部署完成！")
    print("=" * 60)
    print(f"\n✅ 模型 {model_name} 已成功部署")
    print(f"✅ 精度: bfloat16")
    print(f"✅ 已准备好进行 LoRA 微调")
    print(f"\n📁 模型缓存位置: ~/.cache/huggingface/hub/")
    print(f"📄 配置文件: /workspace/qwen35_config.txt")
    print(f"\n🚀 下一步 - 开始 LoRA 微调:")
    print(f"   cd /workspace/LLaMA-Factory")
    print(f"   llamafactory-cli train /workspace/lora_config.yaml")

    return 0

if __name__ == "__main__":
    sys.exit(main())
