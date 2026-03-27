#!/usr/bin/env python3
"""简单的 Qwen3.5 测试脚本"""

import sys

try:
    import torch
    print(f"✓ PyTorch 版本: {torch.__version__}")
    print(f"✓ CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"✓ CUDA 版本: {torch.version.cuda}")
        print(f"✓ GPU 设备: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"✗ PyTorch 加载失败: {e}")
    sys.exit(1)

try:
    import transformers
    print(f"✓ Transformers 版本: {transformers.__version__}")
except Exception as e:
    print(f"✗ Transformers 加载失败: {e}")
    sys.exit(1)

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print("✓ 可以导入 AutoModelForCausalLM")
except Exception as e:
    print(f"✗ AutoModel 导入失败: {e}")
    sys.exit(1)

print("\n环境检查完成！")
