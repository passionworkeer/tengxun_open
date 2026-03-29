# Qwen3.5-9B bf16-LoRA 微调完整指南

## 📦 部署状态

### ✅ 已完成
- [x] 环境检查 (GPU: NVIDIA A10 23GB)
- [x] 模型下载中... (Qwen/Qwen3.5-9B)
- [x] LoRA 配置文件已准备
- [x] 训练脚本已创建

### 📁 文件说明

| 文件 | 说明 |
|------|------|
| `/workspace/full_deploy_qwen35.py` | 完整部署脚本（下载+测试模型） |
| `/workspace/lora_config.yaml` | LoRA 微调配置文件 |
| `/workspace/train_lora.sh` | 一键启动训练脚本 |
| `/workspace/qwen35_config.txt` | 模型配置信息（部署后生成） |

---

## 🚀 使用流程

### 1. 检查部署状态

```bash
# 查看模型是否下载完成
ls -lh ~/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B*

# 查看配置文件
cat /workspace/qwen35_config.txt
```

### 2. 准备训练数据

#### 方法 A: 使用内置数据集

编辑 `/workspace/lora_config.yaml`，修改 `dataset` 字段：

```yaml
dataset: identity,alpaca_zh  # 使用内置数据集
```

#### 方法 B: 使用自定义数据集

1. 创建数据集文件 `my_dataset.json`：
```json
[
  {
    "instruction": "解释什么是机器学习",
    "input": "",
    "output": "机器学习是一种人工智能..."
  },
  {
    "instruction": "用Python写一个快速排序",
    "input": "",
    "output": "def quick_sort(arr):\n    ..."
  }
]
```

2. 注册数据集到 LLaMA-Factory：

编辑 `/workspace/LLaMA-Factory/data/dataset_info.json`，添加：

```json
{
  "my_dataset": {
    "file_name": "my_dataset.json",
    "formatting": "alpaca",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

3. 更新训练配置：
```yaml
dataset: my_dataset
```

### 3. 调整训练参数

根据你的需求修改 `/workspace/lora_config.yaml`：

```yaml
# LoRA 参数（影响模型大小和效果）
lora_rank: 8          # 通常 4-16，越大效果越好但模型越大
lora_alpha: 16        # 通常是 rank 的 2 倍
lora_dropout: 0.05    # 0.0-0.1，防止过拟合

# 训练参数
per_device_train_batch_size: 1     # 根据显存调整 (A10 建议 1-2)
gradient_accumulation_steps: 8     # 梯度累积，实际 batch_size = 1*8=8
learning_rate: 5.0e-5              # 学习率，通常 1e-5 到 5e-5
num_train_epochs: 3.0              # 训练轮数

# 序列长度
cutoff_len: 1024                   # 最大序列长度，越长显存占用越大
```

### 4. 开始训练

#### 方式 A: 使用一键脚本（推荐）

```bash
bash /workspace/train_lora.sh
```

#### 方式 B: 手动执行

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli train /workspace/lora_config.yaml
```

#### 方式 C: 使用 Web UI（可视化）

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli webui
```

然后访问 `http://localhost:7860`，在界面中配置并启动训练。

### 5. 监控训练进度

训练过程中会实时输出日志：

```
{'loss': 2.3456, 'learning_rate': 4.8e-5, 'epoch': 0.5, 'step': 50}
{'loss': 1.9876, 'learning_rate': 4.5e-5, 'epoch': 1.0, 'step': 100}
...
```

查看保存的检查点：

```bash
# 查看已保存的模型
ls -lh ./saves/qwen3.5-9b/lora/sft/

# 查看训练曲线图片
ls -lh ./saves/qwen3.5-9b/lora/sft/*.png
```

### 6. 测试微调后的模型

#### 方式 A: 命令行对话

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli chat /workspace/lora_config.yaml
```

#### 方式 B: Web UI 对话

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli webui
```

在 Chat 页面加载微调后的模型进行测试。

#### 方式 C: Python 脚本测试

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

model_path = "Qwen/Qwen3.5-9B"
lora_path = "./saves/qwen3.5-9b/lora/sft"

# 加载基础模型
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True
)

# 加载 LoRA 权重
model = PeftModel.from_pretrained(model, lora_path)

# 对话
messages = [{"role": "user", "content": "你好"}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to(model.device)

outputs = model.generate(**inputs, max_new_tokens=512)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

### 7. 导出/合并模型

#### 导出为独立模型

```bash
cd /workspace/LLaMA-Factory
llamafactory-cli export \
    --model_name_or_path Qwen/Qwen3.5-9B \
    --adapter_name_or_path ./saves/qwen3.5-9b/lora/sft \
    --export_dir ./merged_model \
    --export_size 2 \
    --export_device cuda \
    --export_legacy_format false
```

---

## ⚙️ 参数调优建议

### LoRA 参数

| 场景 | lora_rank | lora_alpha | 说明 |
|------|-----------|------------|------|
| 轻量微调 | 4 | 8 | 快速训练，显存占用低 |
| 平衡方案 | 8 | 16 | 推荐，效果和效率平衡 |
| 效果优先 | 16 | 32 | 更好效果，但更慢 |

### 训练参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `learning_rate` | 1e-5 ~ 5e-5 | 任务简单用低，任务复杂用高 |
| `batch_size` | 1-2 (GPU) | A10 建议 1 |
| `num_train_epochs` | 2-5 | 数据少多轮，数据少几轮 |
| `cutoff_len` | 512-2048 | 短文本 512，长文本 1024+ |

---

## 📊 常见问题

### 1. 显存不足 OOM

**解决方案：**
- 降低 `per_device_train_batch_size` 到 1
- 降低 `cutoff_len` 到 512 或 256
- 降低 `lora_rank` 到 4
- 减少 `max_samples` 限制数据量

### 2. 训练太慢

**解决方案：**
- 增加 `per_device_train_batch_size`（如果显存足够）
- 减少 `gradient_accumulation_steps`
- 减少 `num_train_epochs`
- 使用更小的 `max_samples` 先测试

### 3. 效果不好

**解决方案：**
- 增加 `lora_rank` 和 `lora_alpha`
- 增加 `num_train_epochs`
- 检查数据质量
- 调整 `learning_rate`

---

## 🎯 快速开始示例

### 最小化配置（快速测试）

```yaml
# /workspace/lora_config_minimal.yaml
model_name_or_path: Qwen/Qwen3.5-9B
stage: sft
finetuning_type: lora
lora_rank: 4
lora_alpha: 8
dataset: identity
template: qwen
cutoff_len: 512
max_samples: 100
output_dir: ./saves/qwen3.5-9b/lora/test
per_device_train_batch_size: 1
gradient_accumulation_steps: 4
learning_rate: 5.0e-5
num_train_epochs: 1.0
bf16: true
```

运行：
```bash
cd /workspace/LLaMA-Factory
llamafactory-cli train /workspace/lora_config_minimal.yaml
```

---

## 📚 参考资源

- [LLaMA Factory 文档](https://llamafactory.readthedocs.io/)
- [Qwen3.5 模型页](https://huggingface.co/Qwen/Qwen3.5-9B)
- [LoRA 论文](https://arxiv.org/abs/2106.09685)

---

## 💡 提示

1. **首次训练**：使用小数据集（100-1000条）测试流程
2. **监控显存**：训练时用 `nvidia-smi` 监控显存使用
3. **保存检查点**：调整 `save_steps` 适时保存
4. **备份配置**：训练前备份配置文件

---

部署日期: 2026-03-25
GPU: NVIDIA A10 (23GB)
模型: Qwen3.5-9B
精度: bf16
微调方式: LoRA
