# Celery 跨文件依赖分析：基于 PE / RAG / FT 的效果优化

面向腾讯实习考核题的正式仓库版本。任务聚焦于：

- 真实开源项目上的跨文件依赖分析
- 评测集构建与瓶颈诊断
- Prompt Engineering 系统优化
- RAG 增强检索与上下文融合
- Qwen 领域微调与消融实验

## 核心发现

1. **PE 是当前最强单项增益**  
   在正式 `54-case` 口径上，GPT-5.4 从 `baseline 0.2745` 提升到 `postprocess 0.6062`，绝对提升 `+0.3317`，相对提升 `+120.8%`。

2. **Qwen 的完整消融矩阵已经补齐，最佳开源组合是 `PE + RAG + FT`**  
   Qwen strict baseline 仅 `0.0370`，`PE only` 到 `0.2246`，`FT only` 到 `0.0932`，`PE + FT` 到 `0.4315`，最终 `PE + RAG + FT` 到 `0.4435`。这说明 PE 是开源模型的核心增益源，FT 负责领域适配，RAG 只有在和 PE/FT 组合时才真正有价值。

3. **RAG 的价值是“定向修复 hard 场景”，不是无脑全局提分**  
   GPT-5.4 端到端 `No-RAG 0.2783 -> With-RAG 0.2940`，总体只提升 `+0.0157`；但 `Hard` 难度从 `0.1980 -> 0.3372`，提升 `+0.1392`。RAG 更像是针对 Type A / Type E 的补偿模块。

## 当前结果总览

| 策略 / 模型 | Easy | Medium | Hard | Avg | 说明 |
|------|------:|------:|------:|------:|------|
| GPT-5.4 Baseline | 0.4348 | 0.2188 | 0.2261 | 0.2815 | 商业模型基线 |
| GLM-5 Baseline | 0.1048 | 0.0681 | 0.0367 | 0.0666 | 官方 API，保留原始 thinking |
| Qwen3.5-9B Baseline | 0.0667 | 0.0526 | 0.0000 | 0.0370 | 严格恢复版，45/54 parse fail |
| GPT-5.4 PE only | 0.6651 | 0.6165 | 0.5522 | 0.6062 | 54-case 正式重跑 |
| GPT-5.4 RAG only | 0.2722 | 0.2656 | 0.3372 | 0.2940 | 端到端 weighted RAG |
| Qwen PE only | 0.3167 | 0.2491 | 0.1323 | 0.2246 | 正式 54-case |
| Qwen RAG only | 0.0667 | 0.0000 | 0.0000 | 0.0185 | 最新 Google embedding |
| Qwen PE + RAG | 0.1514 | 0.2614 | 0.0523 | 0.1534 | 最新 Google embedding |
| Qwen FT only | 0.1556 | 0.0895 | 0.0500 | 0.0932 | LoRA 后正式结果 |
| Qwen PE + FT | 0.5233 | 0.5370 | 0.2624 | 0.4315 | 开源模型高性价比路线 |
| Qwen PE + RAG + FT | 0.4985 | 0.4805 | 0.3672 | 0.4435 | 最新 Google embedding，当前开源最优 |

## 图表速览

![模型基线对比](img/final_delivery/01_model_baselines_20260328.png)

![PE 逐步增益](img/final_delivery/02_pe_progression_20260328.png)

![Qwen 组合策略](img/final_delivery/06_qwen_strategies_20260328.png)

## 当前完成度

### 已完成

- 正式评测集：[`data/eval_cases.json`](data/eval_cases.json)，`54` 条
- 正式 few-shot 库：[`data/fewshot_examples_20.json`](data/fewshot_examples_20.json)，`20` 条
- 正式微调集：[`data/finetune_dataset_500.jsonl`](data/finetune_dataset_500.jsonl)，`500` 条
- GPT / GLM / Qwen baseline
- GPT PE 四阶段正式重跑
- Google embedding 版本 RAG 检索正式评测
- GPT 端到端 RAG 正式评测
- Qwen `PE / RAG / PE+RAG / FT / PE+FT / PE+RAG+FT` 全矩阵
- 最终图表与正式报告

### 如需复现 Qwen 完整矩阵

- 现在没有必须补跑项。
- 如果你想在同一环境重现这 4 组正式结果，仍然可以直接使用统一入口：
  - `Qwen PE only`
  - `Qwen RAG only`
  - `Qwen PE + RAG`
  - `Qwen PE + RAG + FT`

复现命令见：

- [`docs/qwen_remaining_runs_20260328.md`](docs/qwen_remaining_runs_20260328.md)

## Google embedding 说明

### 现在需不需要重跑 embedding

- **当前这台机器上不需要。**
- 最新 Google embedding cache 已经完整生成：
  - `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`

### 直接 `git pull` 能不能拿到这个缓存

- **不能。**
- `artifacts/` 没有进 git，这个缓存文件约 `326MB`，因此只存在于本地运行环境。

### 实际影响

- 如果你还在这台机器上继续跑 Qwen 的 RAG 相关实验，可以直接复用，不需要重新切片。
- 如果你换到另一台机器重新拉仓库，只会拿到代码、结果 JSON 和报告，不会自动拿到这个 embedding cache。
- 跨机器复用需要手动复制该文件；否则重新运行 embedding 预计算。

## Quick Start

### 1. 数据检查

```bash
make lint-data
```

### 2. 基线与 RAG 检索

```bash
make eval-baseline
make eval-rag
```

### 3. 生成最终图表与指标快照

```bash
make report
```

### 4. Qwen 完整消融复现

```bash
uv run --with openai python run_qwen_ablation_eval.py --mode pe

export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key
uv run --with openai python run_qwen_ablation_eval.py --mode rag --repo-root external/celery
uv run --with openai python run_qwen_ablation_eval.py --mode pe_rag --repo-root external/celery
```

## 仓库结构

```text
tengxun_open/
├── README.md
├── Makefile
├── data/
├── evaluation/
├── pe/
├── rag/
├── finetune/
├── configs/
├── scripts/
├── results/
├── reports/
├── docs/
└── img/final_delivery/
```

完整地图见：

- [`docs/repository_map_20260328.md`](docs/repository_map_20260328.md)

## 权威文档入口

- 总交付报告：[`reports/DELIVERY_REPORT.md`](reports/DELIVERY_REPORT.md)
- 瓶颈诊断：[`reports/bottleneck_diagnosis.md`](reports/bottleneck_diagnosis.md)
- PE 优化：[`reports/pe_optimization.md`](reports/pe_optimization.md)
- RAG 方案：[`reports/rag_pipeline.md`](reports/rag_pipeline.md)
- 消融矩阵：[`reports/ablation_study.md`](reports/ablation_study.md)
- 当前进度：[`reports/project_progress_20260328.md`](reports/project_progress_20260328.md)
- Qwen 复现实验说明：[`docs/qwen_remaining_runs_20260328.md`](docs/qwen_remaining_runs_20260328.md)

## 当前最稳的对外结论

- 如果只看商业模型上界，`GPT-5.4` 仍明显领先。
- 如果只看“可训练开源模型”的最高正式结果，当前最优是 `Qwen PE + RAG + FT = 0.4435`。
- 如果考虑工程复杂度与性价比，`Qwen PE + FT = 0.4315` 仍然是很强的默认路线。
