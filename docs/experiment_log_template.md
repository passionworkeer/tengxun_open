# Experiment Log Template

## 使用目标

本模板用于统一记录每一次 baseline、PE、RAG、Fine-tune 和组合实验，保证结果可追溯。

## 实验记录模板

```md
# Experiment Log

## Basic Info
- date:
- operator:
- repo snapshot:
- eval dataset version:

## Model Setup
- base model:
- decoding params:
- context window:

## Prompt Setup
- system prompt version:
- few-shot version:
- CoT enabled: yes / no
- post-processing enabled: yes / no

## Retrieval Setup
- chunking strategy:
- embedding model:
- keyword retriever:
- graph retriever:
- fusion strategy:

## Fine-tune Setup
- fine-tune enabled: yes / no
- dataset version:
- lora / qlora config:
- early stopping:

## Results
- Easy F1:
- Medium F1:
- Hard F1:
- Avg F1:
- Recall@5:
- MRR:
- token cost:

## Error Analysis
- representative bad case 1:
- representative bad case 2:
- failure type distribution:

## Conclusion
- biggest gain:
- biggest regression risk:
- next action:
```

## 命名建议

- `baseline_v1`
- `pe_system_v1`
- `pe_system_cot_v1`
- `rag_rrf_v1`
- `ft_qwen25_v1`
- `all_stack_v1`

## 记录原则

- 每次只改一个关键变量，便于做消融
- 同一批次实验尽量固定评测集版本
- 重要异常不要只写在聊天记录里，要写回日志模板
