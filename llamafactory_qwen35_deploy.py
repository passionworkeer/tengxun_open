#!/usr/bin/env python3
"""
使用 LLaMA Factory 部署 Qwen3.5-9B 的简化示例

注意：由于环境依赖复杂，本脚本提供基于 Transformers 的直接部署方案
如果 LLaMA Factory CLI 工作正常，你也可以使用：
  llamafactory-cli webui
或
  llamafactory-cli api examples/inference/qwen35.yaml
"""

import sys

def test_environment():
    """测试环境"""
    print("=" * 70)
    print("Qwen3.5-9B 部署环境检测")
    print("=" * 70)
    
    try:
        import torch
        print(f"✓ PyTorch: {torch.__version__}")
        print(f"  - CUDA 可用: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  - GPU: {torch.cuda.get_device_name(0)}")
            print(f"  - 显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    except Exception as e:
        print(f"✗ PyTorch 加载失败: {e}")
        return False
    
    try:
        import transformers
        print(f"✓ Transformers: {transformers.__version__}")
        
        # 检查是否支持 Qwen3.5
        from transformers import AutoConfig
        try:
            config = AutoConfig.from_pretrained("Qwen/Qwen3.5-9B", trust_remote_code=True)
            print(f"✓ 支持 Qwen3.5 架构: {config.model_type}")
        except Exception as e:
            print(f"⚠ Qwen3.5 支持检查: {e}")
            print("  提示: 可能需要升级 transformers: pip install --upgrade transformers")
    except Exception as e:
        print(f"✗ Transformers 加载失败: {e}")
        return False
    
    return True

def try_llamafactory_webui():
    """尝试启动 LLaMA Factory Web UI"""
    print("\n" + "=" * 70)
    print("尝试启动 LLaMA Factory Web UI")
    print("=" * 70)
    
    try:
        from llamafactory.cli import main
        
        print("\n启动 Web UI...")
        print("访问地址: http://localhost:7860")
        print("按 Ctrl+C 停止服务\n")
        
        # 启动 webui
        main(["webui"])
        
    except Exception as e:
        print(f"✗ Web UI 启动失败: {e}")
        print("\n替代方案：")
        print("1. 使用 Transformers 直接部署（见下方示例）")
        print("2. 检查 LLaMA Factory 安装: cd LLaMA-Factory && pip install -e .")
        return False

def show_transformers_example():
    """显示 Transformers 直接部署示例"""
    print("\n" + "=" * 70)
    print("Transformers 直接部署方案")
    print("=" * 70)
    
    example_code = '''
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# 加载 Qwen3.5-9B
model_name = "Qwen/Qwen3.5-9B"

print("加载模型...")
tokenizer = AutoTokenizer.from_pretrained(
    model_name,
    trust_remote_code=True
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto" if torch.cuda.is_available() else "cpu",
    trust_remote_code=True
)

# 对话
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你好！请介绍一下你自己。"}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

with torch.no_grad():
    generated_ids = model.generate(
        model_inputs.input_ids,
        max_new_tokens=512,
        temperature=0.7,
        top_p=0.8,
        do_sample=True
    )

generated_ids = [
    output_ids[len(input_ids):]
    for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(response)
'''
    
    print("\n完整示例代码：")
    print(example_code)
    
    print("\n" + "=" * 70)
    print("快速测试命令：")
    print("=" * 70)
    print("\n方法1: 使用 Hugging Face 直接下载（需要约 18GB 空间）")
    print('  pip install "transformers>=5.0.0" torch')
    print('  python -c "from transformers import AutoModel; AutoModel.from_pretrained(\'Qwen/Qwen3.5-9B\', trust_remote_code=True)"')
    
    print("\n方法2: 使用 LLaMA Factory Web UI（可视化界面）")
    print("  cd /workspace/LLaMA-Factory")
    print("  llamafactory-cli webui")
    
    print("\n方法3: 使用 LLaMA Factory CLI（命令行）")
    print("  cd /workspace/LLaMA-Factory")
    print("  llamafactory-cli chat examples/inference/qwen35.yaml")

if __name__ == "__main__":
    # 测试环境
    if not test_environment():
        print("\n✗ 环境检测失败，请检查依赖安装")
        sys.exit(1)
    
    # 尝试启动 LLaMA Factory Web UI
    print("\n是否尝试启动 LLaMA Factory Web UI？")
    print("这需要正确的环境配置。如果失败，将显示替代方案。\n")
    
    if False:  # 默认不启动，避免环境问题
        try_llamafactory_webui()
    
    # 显示替代方案
    show_transformers_example()
    
    print("\n" + "=" * 70)
    print("✓ 部署指南完成！")
    print("=" * 70)
    print("\n详细文档请查看: /workspace/Qwen3.5_DEPLOY_GUIDE.md")
