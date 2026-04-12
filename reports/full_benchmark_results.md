# 完整评测对比表格

生成时间: 2026-04-12 20:18:24
评测数据集: `data/eval_cases.json` (84 cases: 15 Easy, 19 Medium, 20 Hard, 30 Type A/B/C/D/E)

## Union F1 Score (Primary Metric)

| Strategy | Description | Easy | Medium | Hard | **Overall** | Δ Baseline | Source |
|---|---|---|---|---|---|---|---|
| GPT-5.4 PE | GPT-5.4 + Fewshot + Postprocess | 0.6651 | 0.6165 | 0.5522 | **0.6062** | +0.5692 | summary.json |
| Qwen PE + RAG + FT | 完整策略：Qwen + PE + RAG + Fine-tuned | 0.4985 | 0.4805 | 0.3672 | **0.4435** | +0.4065 | summary.json |
| Qwen PE + FT | Qwen + PE + Fine-tuned | 0.5233 | 0.5370 | 0.2624 | **0.4315** | +0.3945 | summary.json |
| GPT-5.4 Baseline | GPT-5.4 无 PE 无 RAG | 0.4348 | 0.2188 | 0.2261 | **0.2815** | +0.2445 | summary.json |
| Qwen PE | Qwen + PE (Fewshot + Postprocess) | 0.3167 | 0.2491 | 0.1323 | **0.2246** | +0.1876 | summary.json |
| Qwen PE + RAG | Qwen + PE + RAG | 0.1514 | 0.2614 | 0.0523 | **0.1534** | +0.1164 | summary.json |
| GLM-5 Baseline | GLM-5 无 PE 无 RAG | 0.1048 | 0.0681 | 0.0367 | **0.0666** | +0.0296 | summary.json |
| Qwen Baseline | Qwen3-9B 无 PE 无 RAG | 0.0667 | 0.0526 | 0.0000 | **0.0370** | +0.0000 | summary.json |
| Qwen RAG | Qwen + RAG (无 PE) | 0.0667 | 0.0000 | 0.0000 | **0.0185** | -0.0185 | summary.json |

## Macro F1 Score (Per-Layer Quality)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 0.5670 | 0.3018 | 0.2482 | **0.3556** |
| Qwen PE + RAG + FT | 0.3648 | 0.3561 | 0.2473 | **0.3182** |
| Qwen PE + FT | 0.4141 | 0.4237 | 0.2059 | **0.3404** |
| GPT-5.4 Baseline | 0.2859 | 0.1316 | 0.1065 | **0.1652** |
| Qwen PE | 0.2185 | 0.2117 | 0.0944 | **0.1702** |
| Qwen PE + RAG | 0.1185 | 0.2281 | 0.0381 | **0.1273** |
| GLM-5 Baseline | 0.1000 | 0.0333 | 0.0000 | **0.0395** |
| Qwen Baseline | 0.0667 | 0.0526 | 0.0000 | **0.0370** |
| Qwen RAG | 0.0667 | 0.0000 | 0.0000 | **0.0185** |

## Direct Dependency F1 (Easiest Layer)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 0.6689 | 0.4579 | 0.3627 | **0.4812** |
| Qwen PE + RAG + FT | 0.7444 | 0.6491 | 0.4783 | **0.6123** |
| Qwen PE + FT | 0.6444 | 0.5877 | 0.3333 | **0.5093** |
| GPT-5.4 Baseline | 0.5578 | 0.2281 | 0.1779 | **0.3011** |
| Qwen PE | 0.3778 | 0.3509 | 0.1833 | **0.2963** |
| Qwen PE + RAG | 0.3111 | 0.3509 | 0.0500 | **0.2284** |
| GLM-5 Baseline | 0.1000 | 0.0526 | 0.0000 | **0.0463** |
| Qwen Baseline | 0.0667 | 0.0526 | 0.0000 | **0.0370** |
| Qwen RAG | 0.0667 | 0.0000 | 0.0000 | **0.0185** |

## Per-Failure-Type Breakdown (Overall Union F1)

| Strategy | Type C | Type E | Type A | Type B | Type D |
|---|---|---|---|---|---|
| GPT-5.4 PE | 0.5133 | 0.5502 | 0.7394 | 0.6159 | 0.5801 |
| Qwen PE + RAG + FT | 0.3391 | 0.2571 | 0.5424 | 0.5258 | 0.4695 |
| Qwen PE + FT | 0.0406 | 0.4361 | 0.6717 | 0.5579 | 0.3479 |
| GPT-5.4 Baseline | N/A | N/A | N/A | N/A | N/A |
| Qwen PE | 0.0000 | 0.1868 | 0.4394 | 0.3030 | 0.1425 |
| Qwen PE + RAG | 0.0714 | 0.0000 | 0.1792 | 0.1273 | 0.2758 |
| GLM-5 Baseline | N/A | N/A | N/A | N/A | N/A |
| Qwen Baseline | 0.0000 | 0.0000 | 0.0909 | 0.0000 | 0.0625 |
| Qwen RAG | 0.0000 | 0.0000 | 0.0909 | 0.0000 | 0.0000 |

## Mislayer Rate (Lower is Better)

| Strategy | Easy | Medium | Hard | **Overall** |
|---|---|---|---|---|
| GPT-5.4 PE | 10.0% | 33.2% | 43.0% | **30.4%** |
| Qwen PE + RAG + FT | 10.0% | 20.5% | 32.5% | **22.0%** |
| Qwen PE + FT | 10.0% | 17.0% | 11.7% | **13.1%** |
| GPT-5.4 Baseline | 16.7% | 20.2% | 21.1% | **19.5%** |
| Qwen PE | 10.0% | 5.3% | 8.3% | **7.7%** |
| Qwen PE + RAG | 6.7% | 1.8% | 3.3% | **3.7%** |
| GLM-5 Baseline | 0.0% | 5.3% | 10.0% | **5.6%** |
| Qwen Baseline | 0.0% | 0.0% | 0.0% | **0.0%** |
| Qwen RAG | 0.0% | 0.0% | 0.0% | **0.0%** |

## 评测结论

### 最佳策略
- **GPT-5.4 PE**: Overall=0.6062, Macro=0.3556, Hard=0.5522

### Hard 场景瓶颈
- GPT-5.4 PE: Hard F1=0.5522
- Qwen PE + RAG + FT: Hard F1=0.3672
- Qwen PE + FT: Hard F1=0.2624

### 下一步行动建议
1. **Hard 场景严重不足**（多数策略 F1<0.1），Type E 是核心瓶颈
2. 建议: 增加 RAG Type E 专项优化 + 增强微调数据覆盖
