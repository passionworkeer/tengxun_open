# Qwen 正式实验复现说明（2026-03-28）

## 文档目的

这份文档现在只回答一件事：

- `Qwen` 的正式实验现在怎么复现
- 应该用什么脚本跑
- 应该用什么数据集跑
- 结果会保存到哪里
- 哪些旧脚本和旧结果不要再当正式版使用

当前权威总览仍然是：

- [`reports/project_progress_20260328.md`](../reports/project_progress_20260328.md)

这份文档是它的 Qwen 专项执行版。

## 一句话结论

当前 `Qwen` 正式矩阵已经补齐，已有结果包括：

- baseline 恢复版
- `PE only`
- `RAG only`
- `PE + RAG`
- `FT only`
- `PE + FT`
- `PE + RAG + FT`

也就是说，这份文档不再是待办清单，而是正式结果的复现手册。

## 正式数据集

所有复现实验统一使用这份正式评测集：

- 评测集：[`data/eval_cases.json`](../data/eval_cases.json)
- 用例数：`54`
- 难度分布：`easy 15 / medium 19 / hard 20`

不要再用这些旧入口作为正式评测集：

- `data/eval_cases_final_v1.json`
- 任何旧的 `50-case` 报告口径

## 当前已存在的 Qwen 结果

### 已完成且可引用

- baseline 严格恢复版：
  - [`results/qwen_baseline_recovered_20260328.json`](../results/qwen_baseline_recovered_20260328.json)
  - [`results/qwen_baseline_recovered_summary_20260328.json`](../results/qwen_baseline_recovered_summary_20260328.json)
- FT only：
  - [`results/qwen_ft_20260327_160136.json`](../results/qwen_ft_20260327_160136.json)
  - [`results/qwen_ft_20260327_160136_stats.json`](../results/qwen_ft_20260327_160136_stats.json)
- PE + FT：
  - [`results/qwen_pe_ft_20260327_162308.json`](../results/qwen_pe_ft_20260327_162308.json)
  - [`results/qwen_pe_ft_20260327_162308_stats.json`](../results/qwen_pe_ft_20260327_162308_stats.json)
- PE only：
  - [`results/qwen_pe_only_20260328.json`](../results/qwen_pe_only_20260328.json)
  - [`results/qwen_pe_only_20260328_stats.json`](../results/qwen_pe_only_20260328_stats.json)
- RAG only：
  - [`results/qwen_rag_only_google_20260328.json`](../results/qwen_rag_only_google_20260328.json)
  - [`results/qwen_rag_only_google_20260328_stats.json`](../results/qwen_rag_only_google_20260328_stats.json)
- PE + RAG：
  - [`results/qwen_pe_rag_google_20260328.json`](../results/qwen_pe_rag_google_20260328.json)
  - [`results/qwen_pe_rag_google_20260328_stats.json`](../results/qwen_pe_rag_google_20260328_stats.json)
- PE + RAG + FT：
  - [`results/qwen_pe_rag_ft_google_20260328.json`](../results/qwen_pe_rag_ft_google_20260328.json)
  - [`results/qwen_pe_rag_ft_google_20260328_stats.json`](../results/qwen_pe_rag_ft_google_20260328_stats.json)

## 环境前提

### 1. Qwen 服务

默认使用本地 vLLM / OpenAI 兼容接口：

- Base URL：`http://localhost:8000/v1`
- Model：`Qwen/Qwen3.5-9B`

仓库里的启动脚本：

- [`start_qwen_vllm.sh`](../start_qwen_vllm.sh)

典型启动方式：

```bash
bash start_qwen_vllm.sh
```

确认服务可用：

```bash
curl http://localhost:8000/v1/models
```

### 2. RAG / Embedding

凡是涉及 `RAG only`、`PE + RAG`、`PE + RAG + FT` 的实验，统一使用最新正式 embedding 方案：

- `EMBEDDING_PROVIDER=google`
- `GOOGLE_API_KEY=你的_google_key`

当前这台机器上不需要重新切片，也不需要重新跑完整 embedding：

- 已有完整 cache：`artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json`

如果本地没有完整 Google embedding cache，可以先运行 `python3 scripts/precompute_embeddings.py` 按正式配置重建；正式结果不依赖“必须拷贝这台机器的 cache 文件”。

## 正式复现入口

### A. Qwen PE only

使用统一脚本：

- 脚本：[`run_qwen_ablation_eval.py`](../run_qwen_ablation_eval.py)

命令：

```bash
uv run --with openai python run_qwen_ablation_eval.py \
  --mode pe \
  --cases data/eval_cases.json \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen3.5-9B \
  --output results/qwen_pe_only_20260328.json
```

输出：

- 结果文件：`results/qwen_pe_only_20260328.json`
- 统计文件：`results/qwen_pe_only_20260328_stats.json`

### B. Qwen RAG only

使用统一脚本：

- 脚本：[`run_qwen_ablation_eval.py`](../run_qwen_ablation_eval.py)

命令：

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key

uv run --with openai python run_qwen_ablation_eval.py \
  --mode rag \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen3.5-9B \
  --output results/qwen_rag_only_google_20260328.json
```

输出：

- 结果文件：`results/qwen_rag_only_google_20260328.json`
- 统计文件：`results/qwen_rag_only_google_20260328_stats.json`

### C. Qwen PE + RAG

使用统一脚本：

- 脚本：[`run_qwen_ablation_eval.py`](../run_qwen_ablation_eval.py)

命令：

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key

uv run --with openai python run_qwen_ablation_eval.py \
  --mode pe_rag \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --base-url http://localhost:8000/v1 \
  --model Qwen/Qwen3.5-9B \
  --output results/qwen_pe_rag_google_20260328.json
```

输出：

- 结果文件：`results/qwen_pe_rag_google_20260328.json`
- 统计文件：`results/qwen_pe_rag_google_20260328_stats.json`

### D. Qwen PE + RAG + FT

使用已有 FT 脚本：

- 脚本：[`run_pe_rag_ft_eval.py`](../run_pe_rag_ft_eval.py)

默认 adapter 路径：

- `LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745`
- 也可以通过环境变量 `QWEN_LORA_ADAPTER_PATH` 统一指定 LoRA adapter

命令：

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=你的_google_key

uv run python run_pe_rag_ft_eval.py \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --output results/qwen_pe_rag_ft_google_20260328.json
```

如果 LoRA adapter 不在默认位置，显式指定：

```bash
uv run python run_pe_rag_ft_eval.py \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --adapter-path LLaMA-Factory/saves/qwen3.5-9b/lora/finetune_20260327_143745 \
  --output results/qwen_pe_rag_ft_google_20260328.json
```

输出：

- 结果文件：`results/qwen_pe_rag_ft_google_20260328.json`
- 统计文件：`results/qwen_pe_rag_ft_google_20260328_stats.json`

## 结果保存约定

建议后续正式结果统一按下面的文件名保存，避免再次混乱：

| 实验 | 建议结果文件 | 建议统计文件 |
|------|--------------|--------------|
| Qwen PE only | `results/qwen_pe_only_20260328.json` | `results/qwen_pe_only_20260328_stats.json` |
| Qwen RAG only | `results/qwen_rag_only_google_20260328.json` | `results/qwen_rag_only_google_20260328_stats.json` |
| Qwen PE + RAG | `results/qwen_pe_rag_google_20260328.json` | `results/qwen_pe_rag_google_20260328_stats.json` |
| Qwen PE + RAG + FT | `results/qwen_pe_rag_ft_google_20260328.json` | `results/qwen_pe_rag_ft_google_20260328_stats.json` |

## 跑完后怎么判断是否合格

每组实验至少要确认这几件事：

1. `total_cases == 54`
2. `stats` 文件成功生成
3. 输入数据集是 `data/eval_cases.json`
4. RAG 实验使用了 `google` provider
5. 输出文件名不覆盖旧历史文件

## 不要再用的旧入口

这些脚本或口径容易把结果跑偏，不建议继续作为正式入口：

- [`scripts/run_qwen_eval.sh`](../scripts/run_qwen_eval.sh)
  - 默认 `MAX_CASES=50`
  - 不是当前正式 54-case 口径
- [`scripts/step5_pe_rag_ft.sh`](../scripts/step5_pe_rag_ft.sh)
  - 仍引用 `data/eval_cases_final_v1.json`
  - 输出文件名过于泛化，容易覆盖历史结果
- 任何未显式指定输出路径、直接写到旧文件名的临时命令

## 建议执行顺序

如果要从零复现完整矩阵，建议按这个顺序跑：

1. `Qwen PE only`
2. `Qwen RAG only`
3. `Qwen PE + RAG`
4. `Qwen PE + RAG + FT`

原因：

- 前三组可以先验证 `PE / RAG / PE+RAG` 的单独和组合贡献
- 最后一组用于复现当前开源最高分配置

## 当前状态

Qwen 这四组已经落盘完成。  
如果后续继续实验，建议直接在现有正式结果基础上做 hard case 定向优化，而不是再重复补齐矩阵。
