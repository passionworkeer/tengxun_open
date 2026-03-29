# Qwen Strict-Clean CUDA 机器执行文档（2026-03-29）

> 归档说明：这份 runbook 最初对应 **2026-03-29 外部 CUDA 执行前** 的操作手册，当前已改写成 **strict-clean 结果的 GPU 复现实验手册**。  
> 当前 strict-clean 训练已经完成；结果完整度请看：
> - `reports/qwen_strict_closeout_20260329.md`
> - `reports/qwen_strict_result_audit_20260329.md`

这份文档只负责一件事：

> 在外部 NVIDIA CUDA 机器上，重新复现 Qwen strict-clean `FT only / PE + FT / PE + RAG + FT`，并把结果打包带回。

如果你只想知道最短执行路径，直接看下面这一段。

## 1. 一键执行版

```bash
git checkout main
git pull

export PYTHONPATH=.
export GOOGLE_API_KEY=你的_google_key

pip install -r requirements.txt
pip install -r requirements-finetune.txt

make check-train-env-strict
make train-strict-dry-run

RUN_NAME=strict_clean_20260329 make qwen-strict-rerun
RUN_NAME=strict_clean_20260329 ./scripts/package_qwen_strict_run.sh
```

如果你还要把 adapter 一起带回：

```bash
RUN_NAME=strict_clean_20260329 INCLUDE_ADAPTER=1 ./scripts/package_qwen_strict_run.sh
```

最终至少要带回这个包：

```bash
artifacts/handoff/strict_clean_20260329.tar.gz
```

## 2. 这一步在补什么

当前仓库里：

- GPT strict PE 最优已经落盘
- Qwen `PE only / RAG only / PE + RAG` 现有结果可直接使用
- Qwen `FT only / PE + FT / PE + RAG + FT` strict-clean 结果已经完整落盘

这次去 CUDA 机器上跑，目的不再是“补结果”，而是做独立复现、重新核对训练证据，或者在你需要时刷新一版新的 strict-clean 运行包。

当前本机为什么不能跑，见：

- `results/strict_replay_train_env_20260329.json`
- `reports/strict_ft_execution_status_20260329.md`

## 3. 机器要求

最低要求：

- NVIDIA CUDA GPU
- `nvidia-smi` 可用
- `llamafactory-cli` 已安装并在 `PATH`
- Python 环境能安装仓库依赖

如果你要跑完整的 `PE + RAG + FT`，还需要：

- `GOOGLE_API_KEY`
- `external/celery` 仓库存在，或者把 `REPO_ROOT` 指向正确路径

## 4. 开跑前准备

### 4.1 拉取正确分支

```bash
git checkout main
git pull
```

### 4.2 安装依赖

```bash
pip install -r requirements.txt
pip install -r requirements-finetune.txt
```

### 4.3 设置环境变量

至少要有：

```bash
export PYTHONPATH=.
```

如果要跑 `PE + RAG + FT`，还要有：

```bash
export GOOGLE_API_KEY=你的_google_key
```

如果 `external/celery` 不在默认位置，可以显式指定：

```bash
export REPO_ROOT=/your/path/to/celery
```

## 5. 正式执行顺序

### 5.1 先做预检

```bash
make check-train-env-strict
make train-strict-dry-run
```

你应该至少看到这些检查通过：

- `cuda = pass`
- `launcher = pass`
- `eval_schedule = pass`
- `save_schedule = pass`

如果这里不通过，不要继续训练。

### 5.2 跑完整 strict-clean 路线

```bash
RUN_NAME=strict_clean_20260329 make qwen-strict-rerun
```

这一步会自动完成：

1. 环境检查
2. `data_guard`
3. materialize run config
4. strict-clean LoRA 训练
5. `FT only` 评测
6. `PE + FT` 评测
7. `PE + RAG + FT` 评测

### 5.3 如果暂时只跑到 FT family，不跑 RAG

```bash
RUN_NAME=strict_clean_20260329 WITH_RAG=0 make qwen-strict-rerun
```

## 6. 跑完后必须核对什么

### 6.1 训练产物

应该看到：

- `artifacts/lora/qwen3.5-9b/<RUN_NAME>/`
- `logs/<RUN_NAME>.train.log`
- `results/qwen_strict_runs/<RUN_NAME>/`
- `configs/<RUN_NAME>.yaml`

### 6.2 评测结果

结果目录里至少应出现：

- `qwen_ft_strict.json`
- `qwen_ft_strict_metrics.json`
- `qwen_pe_ft_strict.json`
- `qwen_pe_ft_strict_metrics.json`

如果跑了 RAG，还应出现：

- `qwen_pe_rag_ft_strict.json`
- `qwen_pe_rag_ft_strict_metrics.json`

### 6.3 成功判定

最小成功标准：

- 训练没有中途报错退出
- `qwen_ft_strict_metrics.json` 已生成
- `qwen_pe_ft_strict_metrics.json` 已生成
- 如果启用了 RAG，`qwen_pe_rag_ft_strict_metrics.json` 已生成

## 7. 打包带回

推荐直接用仓库内置打包脚本：

```bash
RUN_NAME=strict_clean_20260329 ./scripts/package_qwen_strict_run.sh
```

默认会打包：

- `results/qwen_strict_runs/<RUN_NAME>/`
- `logs/<RUN_NAME>.train.log`
- `configs/<RUN_NAME>.yaml`
- strict / formal preflight JSON
- strict closeout 与训练证据相关文档

输出包：

```bash
artifacts/handoff/<RUN_NAME>.tar.gz
```

如果你还想把 adapter 一起打包：

```bash
RUN_NAME=strict_clean_20260329 INCLUDE_ADAPTER=1 ./scripts/package_qwen_strict_run.sh
```

## 8. 跑完后你要带回什么

最少带回：

- `artifacts/handoff/strict_clean_20260329.tar.gz`

如果方便，也一起带回：

- `artifacts/lora/qwen3.5-9b/strict_clean_20260329/`

## 9. 常见失败点

训练前就失败：

- 先看 `make check-train-env-strict`
- 一般是 `CUDA`、`llamafactory-cli`、依赖或路径问题

训练中途失败：

- 先看 `logs/<RUN_NAME>.train.log`

RAG 没跑起来：

- 先确认 `GOOGLE_API_KEY`
- 再确认 `REPO_ROOT` 指向的 Celery 仓库是否存在

结果没生成：

- 先看 `results/qwen_strict_runs/<RUN_NAME>/`
- 再看 `scripts/run_qwen_strict_full.sh`

## 10. 跑完后我这边会做什么

你把 `artifacts/handoff/strict_clean_20260329.tar.gz` 带回来后，如结果需要刷新，我会继续：

1. 核对 strict-clean FT family 指标
2. 更新 `README.md`
3. 更新 `reports/DELIVERY_REPORT.md`
4. 更新 `reports/ablation_study.md`
5. 更新 `reports/final_numbers_cheatsheet_20260329.md`
6. 如有必要，刷新 Qwen FT 家族的正式 strict-clean 口径
