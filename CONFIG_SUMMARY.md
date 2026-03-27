# 配置与文件说明

## 📦 核心配置文件

### 1. 训练配置 - lora_config.yaml
```yaml
model_name_or_path: Qwen/Qwen3.5-9B
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16
dataset: fintune_qwen_dep
learning_rate: 5.0e-5
num_train_epochs: 3.0
bf16: true
```

### 2. 模型路径
- **基座模型**: `~/.cache/huggingface/hub/models--Qwen--Qwen3.5-9B`
- **微调输出**: `LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_dep/`

### 3. 数据集配置
模型: Qwen/Qwen3.5-9B → 数据集: fintune_qwen_dep (500条)

## 🔧 常用命令

### 服务相关
```bash
# 启动vLLM服务
python simple_qwen_server.py

# 启动训练
cd LLaMA-Factory && llamafactory-cli train ../lora_config.yaml

# 测试对话
llamafactory-cli chat ../lora_config.yaml
```

### 评测相关
```bash
# 基线评测
python evaluation/run_qwen_eval.py --cases data/eval_cases_final_v1.json

# 带PE评测
python evaluation/run_qwen_eval.py --cases data/eval_cases_final_v1.json --pe

# 带RAG评测
python evaluation/run_qwen_eval.py --cases data/eval_cases_final_v1.json --rag
```

## 📁 文件对照表

| 文件 | 说明 |
|------|------|
| `simple_qwen_server.py` | Qwen推理服务 |
| `test_qwen_vllm.py` | vLLM测试 |
| `vllm_qwen_test.py` | vLLM推理测试 |
| `llm_client.py` | LLM客户端 |
| `merge_batches.py` | 合并批次数据 |
| `lora_config.yaml` | LoRA训练配置 |
| `qwen35_config.txt` | Qwen3.5配置 |

## 💾 依赖环境

- Python 3.11+
- PyTorch 2.0+
- Transformers 5.0+
- LLaMA-Factory
- vLLM
- A100 40GB GPU