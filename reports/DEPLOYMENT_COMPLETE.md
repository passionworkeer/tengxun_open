# Qwen3.5-9B bf16-LoRA 部署完整说明

## 🎉 部署状态

### ✅ 环境就绪
- **GPU**: NVIDIA A10 (23GB 显存)
- **CUDA**: 13.0
- **Python**: 3.11.1
- **PyTorch**: 2.10.0
- **Transformers**: 5.3.0 (支持 Qwen3.5)
- **磁盘空间**: 227GB 可用

### 📥 模型下载
- **当前进度**: ~35% (6.9GB / 20GB)
- **状态**: 下载进行中...
- **预计完成时间**: 10-20 分钟

---

## 📁 已创建文件

### 核心文件
| 文件 | 用途 |
|------|------|
| `/workspace/full_deploy_qwen35.py` | 完整部署脚本（下载+测试） |
| `/workspace/lora_config.yaml` | LoRA 微调配置 |
| `/workspace/train_lora.sh` | 一键训练脚本 |
| `/workspace/check_download.sh` | 下载进度监控 |
| `/workspace/lora_usage_guide.md` | 完整使用指南 |

### 文档文件
| 文件 | 用途 |
|------|------|
| `/workspace/DEPLOYMENT_COMPLETE.md` | 本文档 |
| `/workspace/README.md` | 项目说明 |
| `/workspace/Qwen3.5_DEPLOY_GUIDE.md` | 部署指南 |
| `/workspace/DEPLOYMENT_SUMMARY.md` | 部署总结 |

---

## 🚀 使用流程

### 阶段 1: 等待下载完成

**检查下载进度**:
```bash
bash /workspace/check_download.sh
```

或手动查看:
```bash
# 查看已下载大小
du -sh ~/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B*

# 查看进程
ps aux | grep python
```

下载完成后，会自动测试模型。

### 阶段 2: 准备训练数据

#### 选项 A: 使用内置数据集（快速测试）

编辑 `/workspace/lora_config.yaml`:
```yaml
dataset: identity,alpaca_zh  # 使用内置数据集
max_samples: 1000            # 先用 1000 条测试
```

#### 选项 B: 使用自定义数据集

1. **创建数据集文件** (`/workspace/my_data.json`):
```json
[
  {
    "instruction": "你的问题",
    "input": "补充信息（可选）",
    "output": "期望的回答"
  }
]
```

2. **注册数据集** - 编辑 `/workspace/LLaMA-Factory/data/dataset_info.json`:
```json
{
  "my_data": {
    "file_name": "my_data.json",
    "formatting": "alpaca",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

3. **更新配置**:
```yaml
dataset: my_data
```

### 阶段 3: 调整训练参数

根据你的需求修改 `/workspace/lora_config.yaml`:

```yaml
# ⚙️ LoRA 参数（影响效果和大小）
lora_rank: 8          # 推荐: 4-16，越大效果越好
lora_alpha: 16        # 通常是 rank 的 2 倍
lora_dropout: 0.05    # 防止过拟合

# 🎯 训练参数
per_device_train_batch_size: 1     # A10 建议 1
gradient_accumulation_steps: 8     # 实际 batch = 1*8=8
learning_rate: 5.0e-5              # 学习率
num_train_epochs: 3.0              # 训练轮数

# 📝 数据参数
cutoff_len: 1024                   # 序列长度
max_samples: 10000                 # 数据量限制
```

### 阶段 4: 开始训练

#### 方式 1: 一键训练（推荐）
```bash
bash /workspace/train_lora.sh
```

#### 方式 2: 手动执行
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli train /workspace/lora_config.yaml
```

#### 方式 3: Web UI（可视化）
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli webui
# 访问 http://localhost:7860
```

### 阶段 5: 监控训练

**实时日志**:
```bash
# 查看训练输出（会自动显示）
# 如果是后台运行，可以用:
tail -f ./saves/qwen3.5-9b/lora/sft/trainer_log.jsonl
```

**监控显存**:
```bash
watch -n 1 nvidia-smi
```

**查看保存的模型**:
```bash
ls -lh ./saves/qwen3.5-9b/lora/sft/
```

### 阶段 6: 测试微调后的模型

#### 命令行对话:
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli chat /workspace/lora_config.yaml
```

#### Web UI 对话:
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli webui
# 在 Chat 页面加载模型
```

#### Python 脚本:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

# 加载模型
model_path = "Qwen/Qwen3.5-9B"
lora_path = "./saves/qwen3.5-9b/lora/sft"

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True
)
model = PeftModel.from_pretrained(model, lora_path)

# 对话
messages = [{"role": "user", "content": "你好"}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to(model.device)
outputs = model.generate(**inputs, max_new_tokens=512)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

---

## 📊 参数优化建议

### LoRA 参数选择

| 使用场景 | lora_rank | lora_alpha | 说明 |
|---------|-----------|-----------|------|
| 快速测试 | 4 | 8 | 最小资源，快速验证 |
| 推荐配置 | 8 | 16 | 平衡效果和效率 ⭐ |
| 效果优先 | 16 | 32 | 更好效果，更慢训练 |

### 训练参数调优

| 问题 | 解决方案 |
|------|----------|
| 显存 OOM | 降低 `per_device_train_batch_size` → 1 |
| 显存 OOM | 降低 `cutoff_len` → 512 |
| 显存 OOM | 降低 `lora_rank` → 4 |
| 训练太慢 | 增加 `gradient_accumulation_steps` |
| 训练太慢 | 减少 `num_train_epochs` |
| 效果不好 | 增加 `lora_rank` |
| 效果不好 | 增加 `num_train_epochs` |
| 效果不好 | 调整 `learning_rate` (1e-5 ~ 5e-5) |

---

## 🔧 常用命令

### 下载相关
```bash
# 检查下载进度
bash /workspace/check_download.sh

# 重新下载（如果中断）
rm -rf ~/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B*
python /workspace/full_deploy_qwen35.py
```

### 训练相关
```bash
# 开始训练
bash /workspace/train_lora.sh

# 查看训练日志
tail -f ./saves/qwen3.5-9b/lora/sft/trainer_log.jsonl

# 查看保存的检查点
ls -lh ./saves/qwen3.5-9b/lora/sft/

# 查看训练曲线
ls -lh ./saves/qwen3.5-9b/lora/sft/*.png
```

### 测试相关
```bash
# 命令行测试
cd /workspace/LLaMA-Factory
llamafactory-cli chat /workspace/lora_config.yaml

# Web UI
cd /workspace/LLaMA-Factory
llamafactory-cli webui
```

---

## 🎯 快速开始示例

### 最小配置（5分钟测试）

创建 `/workspace/lora_config_quick.yaml`:
```yaml
model_name_or_path: Qwen/Qwen3.5-9B
stage: sft
finetuning_type: lora
lora_rank: 4
lora_alpha: 8
dataset: identity
template: qwen
cutoff_len: 512
max_samples: 100
output_dir: ./saves/qwen3.5-9b/lora/quick
per_device_train_batch_size: 1
gradient_accumulation_steps: 4
learning_rate: 5.0e-5
num_train_epochs: 1.0
bf16: true
```

运行:
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli train /workspace/lora_config_quick.yaml
```

---

## 📚 参考资源

- [LLaMA Factory 文档](https://llamafactory.readthedocs.io/)
- [Qwen3.5 模型页](https://huggingface.co/Qwen/Qwen3.5-9B)
- [LoRA 论文](https://arxiv.org/abs/2106.09685)
- [本机完整指南](/workspace/lora_usage_guide.md)

---

## 💡 重要提示

1. **首次使用**: 先用小数据集（100-1000条）测试流程
2. **监控显存**: 训练时用 `nvidia-smi` 实时监控
3. **保存检查点**: 调整 `save_steps` 适时保存
4. **备份数据**: 训练前备份重要的配置和数据
5. **耐心等待**: 9B 模型训练需要时间，请勿中断

---

## 📞 需要帮助？

如果遇到问题：
1. 查看 `/workspace/lora_usage_guide.md` 的常见问题章节
2. 检查 LLaMA Factory 日志
3. 确认模型下载完成: `bash /workspace/check_download.sh`

---

**部署日期**: 2026-03-25
**GPU**: NVIDIA A10 (23GB)
**模型**: Qwen3.5-9B
**精度**: bf16
**微调方式**: LoRA
