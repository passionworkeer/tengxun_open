# Qwen Strict-Clean GPU Runbook（2026-03-29）

这份 runbook 只负责一件事：

> 在外部 CUDA 机器上，把 Qwen strict-clean `FT only / PE + FT / PE + RAG + FT` 跑完并打包带回。

## 1. 前提

建议环境：

- NVIDIA CUDA GPU
- `llamafactory-cli` 已安装
- Python 环境可运行仓库依赖
- 如果要跑 `PE + RAG + FT`，还需要 `GOOGLE_API_KEY`

当前本机为何不能跑，见：

- `results/strict_replay_train_env_20260329.json`
- `reports/strict_ft_execution_status_20260329.md`

## 2. 建议执行顺序

### 2.1 拉取分支

```bash
git checkout codex/strict-ft-remediation
git pull
```

### 2.2 安装依赖

```bash
pip install -r requirements.txt
pip install -r requirements-finetune.txt
```

### 2.3 训练前检查

```bash
export PYTHONPATH=.
make check-train-env-strict
make train-strict-dry-run
```

你应该看到：

- `cuda = pass`
- `launcher = pass`
- `eval_schedule = pass`
- `save_schedule = pass`

如果这里不通过，不要继续训练。

## 3. 正式执行

### 3.1 全量 strict-clean 路线

```bash
export PYTHONPATH=.
export GOOGLE_API_KEY=你的_google_key
RUN_NAME=strict_clean_20260329 make qwen-strict-rerun
```

这会自动完成：

1. 环境检查
2. `data_guard`
3. materialize run config
4. strict-clean LoRA 训练
5. `FT only`
6. `PE + FT`
7. `PE + RAG + FT`

### 3.2 如果只想先跑到 FT family，不跑 RAG

```bash
export PYTHONPATH=.
RUN_NAME=strict_clean_20260329 WITH_RAG=0 make qwen-strict-rerun
```

## 4. 期望输出

跑完后，至少应出现：

- adapter：
  - `artifacts/lora/qwen3.5-9b/<RUN_NAME>/`
- 训练日志：
  - `logs/<RUN_NAME>.train.log`
- 结果目录：
  - `results/qwen_strict_runs/<RUN_NAME>/`

结果目录里重点检查：

- `qwen_ft_strict.json`
- `qwen_ft_strict_metrics.json`
- `qwen_pe_ft_strict.json`
- `qwen_pe_ft_strict_metrics.json`
- 如果跑 RAG：
  - `qwen_pe_rag_ft_strict.json`
  - `qwen_pe_rag_ft_strict_metrics.json`

## 5. 打包带回

推荐用仓库内置脚本打包：

```bash
RUN_NAME=strict_clean_20260329 ./scripts/package_qwen_strict_run.sh
```

默认会打包：

- `results/qwen_strict_runs/<RUN_NAME>/`
- `logs/<RUN_NAME>.train.log`
- `configs/<RUN_NAME>.yaml`
- strict / formal preflight JSON
- 训练证据审计和 strict closeout 文档

输出：

- `artifacts/handoff/<RUN_NAME>.tar.gz`

如果你还想连 adapter 一起带回：

```bash
RUN_NAME=strict_clean_20260329 INCLUDE_ADAPTER=1 ./scripts/package_qwen_strict_run.sh
```

## 6. 跑完后怎么更新仓库

建议顺序：

1. 把 `artifacts/handoff/<RUN_NAME>.tar.gz` 带回当前机器
2. 解包核对结果
3. 更新：
   - `reports/DELIVERY_REPORT.md`
   - `reports/ablation_study.md`
   - `reports/final_numbers_cheatsheet_20260329.md`
   - `README.md`
4. 把 Qwen FT 家族从“历史正式线”升级成“strict-clean 已落盘”

## 7. 如果失败，优先看哪里

- 训练启动失败：先看 `make check-train-env-strict`
- 训练中断：看 `logs/<RUN_NAME>.train.log`
- RAG 失败：先确认 `GOOGLE_API_KEY` 和 `external/celery`
- 结果没生成：先看 `results/qwen_strict_runs/<RUN_NAME>/`
