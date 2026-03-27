# Qwen3.5-9B 本地部署指南

## 环境准备

### 1. 系统要求
- **CPU**: 16核心以上推荐
- **内存**: 64GB+ (CPU 推理) / 16GB+ (GPU推理)
- **存储**: 40GB+ 可用空间
- **操作系统**: Linux/Windows/macOS

### 2. Python 环境
```bash
# 创建虚拟环境（推荐）
conda create -n qwen python=3.11
conda activate qwen

# 或使用 venv
python -m venv qwen_env
source qwen_env/bin/activate  # Linux/Mac
# 或
qwen_env\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
# 安装核心依赖
pip install torch>=2.0.0
pip install transformers>=5.0.0
pip install accelerate
pip install optimum
pip install "protobuf>=3.20,<4"

# 可选：量化支持
pip install bitsandbytes  # CUDA only
pip install auto-gptq  # GPTQ量化
pip install auto-awq  # AWQ量化
```

## 部署方案

### 方案一：CPU 推理（无 GPU）

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_name = "Qwen/Qwen3.5-9B"

# 加载模型
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="cpu",
    trust_remote_code=True
)

# 对话
messages = [{"role": "user", "content": "你好"}]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

with torch.no_grad():
    generated_ids = model.generate(
        model_inputs.input_ids,
        max_new_tokens=512
    )

generated_ids = [
    output_ids[len(input_ids):] 
    for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
]

response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
print(response)
```

### 方案二：GPU 推理（推荐）

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

model_name = "Qwen/Qwen3.5-9B"

# 加载模型到 GPU
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto",  # 自动分配到 GPU
    trust_remote_code=True
)

# 其余代码同上
```

### 方案三：量化推理（显存优化）

#### 4-bit 量化（显存需求 ~8GB）
```python
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

model_name = "Qwen/Qwen3.5-9B"

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4"
)

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=quantization_config,
    device_map="auto",
    trust_remote_code=True
)
```

#### 8-bit 量化（显存需求 ~12GB）
```python
quantization_config = BitsAndBytesConfig(
    load_in_8bit=True,
    llm_int8_threshold=6.0
)
```

### 方案四：使用 vLLM 加速（高性能）

```bash
pip install vllm
```

```python
from vllm import LLM, SamplingParams

model_name = "Qwen/Qwen3.5-9B"

llm = LLM(model_name, trust_remote_code=True)
sampling_params = SamplingParams(temperature=0.7, top_p=0.8, max_tokens=512)

prompts = ["你好，请介绍一下你自己"]
outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(output.outputs[0].text)
```

### 方案五：OpenAI 兼容 API 部署

```bash
pip install openai
```

**启动服务器:**
```python
from vllm.entrypoints.openai.api_server import run_server

run_server(
    model="Qwen/Qwen3.5-9B",
    host="0.0.0.0",
    port=8000,
    trust_remote_code=True
)
```

**客户端调用:**
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

response = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B",
    messages=[{"role": "user", "content": "你好"}]
)

print(response.choices[0].message.content)
```

## 性能优化建议

1. **批处理**: 一次处理多个请求
2. **流式输出**: 使用 `stream=True` 获取实时响应
3. **KV Cache**: 启用以加速长文本生成
4. **Flash Attention 2**: 使用 Flash Attention 加速（CUDA 11.6+）
5. **混合精度**: 使用 `torch_dtype=torch.float16` 或 `bfloat16`

## 常见问题

### Q: 内存不足怎么办？
A: 使用量化方案（4-bit/8-bit）或选择更小的模型（Qwen2.5-7B/3B）

### Q: CPU 推理太慢？
A: 考虑使用 GPU，或使用量化模型 + vLLM

### Q: 如何提高生成质量？
A: 调整参数：`temperature=0.7`, `top_p=0.8`, `top_k=40`

### Q: 模型下载失败？
A:
1. 设置镜像：`HF_ENDPOINT=https://hf-mirror.com`
2. 使用 ModelScope：`pip install modelscope`

## 推荐硬件配置

| 推理方式 | 显存需求 | 推荐显卡 | 性能 |
|---------|---------|---------|-----|
| FP16 全量 | ~18GB | RTX 3090/4090, A10G | 最佳 |
| 8-bit 量化 | ~12GB | RTX 3060/4060, T4 | 良好 |
| 4-bit 量化 | ~8GB | RTX 3060 Ti/4050, RTX A2000 | 较好 |
| CPU 推理 | 64GB RAM | CPU 多核 | 较慢 |

## 相关资源

- [Qwen 官方文档](https://huggingface.co/Qwen)
- [Transformers 文档](https://huggingface.co/docs/transformers)
- [vLLM 文档](https://docs.vllm.ai/)
- [LLaMA Factory 文档](https://llamafactory.readthedocs.io/)
