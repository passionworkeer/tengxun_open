# Experiment Log Template

## 使用目标

本模板用于统一记录每一次 baseline、PE、RAG、Fine-tune 和组合实验，保证结果可追溯。

## 实验记录模板（JSON 格式）

```json
{
  "exp_id": "RAG-003",
  "timestamp": "2025-xx-xx",
  "model": "gpt-4o",
  "prompt_version": "v2.1",
  "rag_config": {
    "chunker": "ast",
    "retriever": "rrf_k60",
    "embedding_model": "text-embedding-3-small",
    "top_k": 5
  },
  "eval_scope": "all_50_cases",
  "results": {
    "easy_f1": 0.79,
    "medium_f1": 0.71,
    "hard_f1": 0.52,
    "avg_f1": 0.67,
    "recall_at_5": 0.82,
    "mrr": 0.73
  },
  "token_cost": {
    "avg_input": 3240,
    "avg_output": 180,
    "relative_to_baseline": "+140%"
  },
  "anomalies": ["case_id_031 检索结果为空，降级到 BM25 兜底"],
  "failure_type_distribution": {
    "Type A": 2,
    "Type B": 5,
    "Type C": 3,
    "Type D": 4,
    "Type E": 1
  }
}
```

## 实验记录模板（Markdown 格式）

```md
# Experiment Log

## Basic Info
- exp_id:
- timestamp:
- operator:
- repo snapshot: b8f85213f45c937670a6a6806ce55326a0eb537f
- eval dataset version:

## Model Setup
- base model: GPT-4o / GLM-5 / Qwen2.5-Coder-7B
- decoding params:
- context window:

## Prompt Setup
- system prompt version:
- few-shot version:
- CoT enabled: yes / no
- post-processing enabled: yes / no

## Retrieval Setup
- chunking strategy: ast / text
- embedding model: CodeBERT / text-embedding-3-small
- keyword retriever: BM25
- graph retriever: NetworkX import graph
- fusion strategy: RRF(k=60)
- top_k:

## Fine-tune Setup
- fine-tune enabled: yes / no
- dataset version:
- lora / qlora config: r=16, alpha=32
- early stopping: patience=3

## Results
- Easy F1:
- Medium F1:
- Hard F1:
- Avg F1:
- Recall@5:
- MRR:
- token cost (relative):

## Error Analysis
- representative bad case 1:
- representative bad case 2:
- failure type distribution:
  - Type A:
  - Type B:
  - Type C:
  - Type D:
  - Type E:

## Conclusion
- biggest gain:
- biggest regression risk:
- next action:
```

## 检索-生成四象限分析

```md
## Retrieval-Generation Quadrant Analysis

| Quadrant | Count | Examples | Root Cause |
| :--- | :--- | :--- | :--- |
| Case A (R✓ G✓) | - | | 理想状态 |
| Case B (R✓ G✗) | - | | 融合策略瓶颈 |
| Case C (R✗ G✓) | - | | 模型参数补偿 |
| Case D (R✗ G✗) | - | | 双重失效 |
```

## 命名建议

- `baseline_gpt4o_v1`
- `baseline_glm5_v1`
- `baseline_qwen7b_v1`
- `pe_system_v1`
- `pe_system_cot_v1`
- `pe_system_cot_fewshot_v1`
- `rag_ast_vector_v1`
- `rag_ast_bm25_v1`
- `rag_ast_graph_v1`
- `rag_rrf_v1`
- `ft_qwen25_7b_v1`
- `pe_rag_v1`
- `pe_ft_v1`
- `all_stack_v1`

## 记录原则

- 每次只改一个关键变量，便于做消融
- 同一批次实验尽量固定评测集版本
- 重要异常不要只写在聊天记录里，要写回日志模板
- Token 消耗必须记录，体现 ROI 意识
