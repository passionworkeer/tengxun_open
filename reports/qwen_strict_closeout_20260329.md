# Qwen strict-clean 收口说明（2026-03-29）

## 1. 当前状态

Qwen 这条线现在分成两部分：

- 历史正式矩阵：`PE / RAG / FT / PE+FT / PE+RAG / PE+RAG+FT` 已全部落盘
- strict-clean 微调复验：数据、配置、评测入口和脚本已准备好，但还没有在本仓库里完成重训

因此当前最稳的说法不是：

- “Qwen strict-clean 最优已经是 `PE + RAG + FT = 0.4435`”

而是：

- “Qwen 的历史正式矩阵已经完整，最高分是 `PE + RAG + FT = 0.4435`”
- “如果要回答训练数据纯度问题，strict-clean FT family 仍需在 GPU 机上重训后重评”

## 2. 已经解决的部分

- strict 微调数据已生成：`data/finetune_dataset_500_strict.jsonl`
- strict 数据审计已完成：`reports/strict_data_audit_20260329.md`
- strict few-shot 与 strict finetune 的 overlap 三项都为 `0`
- strict 训练配置已保留：
  - `configs/train_config_strict_20260329.yaml`
  - `configs/train_config_strict_replay_20260329.yaml`
- strict replay 配置已调整为 `eval_steps=50` / `save_steps=50`
  - 目的：下一次重训时保留逐步 `eval_loss` 证据，而不是只留下最终 `eval_loss`
- strict 一键脚本已补齐：`scripts/run_qwen_strict_full.sh`

## 3. 当前没法在这台机器上直接跑完的原因

当前桌面环境是：

- Darwin / Apple Silicon / MPS
- `torch.cuda.is_available() = False`
- `llamafactory-cli` 不在 PATH

而正式 strict 微调入口依赖：

- CUDA GPU
- `llamafactory-cli train`

所以这台机器不能直接把 Qwen strict-clean 训练跑完。这个问题不是代码缺失，而是训练环境不匹配。

对应落盘证据：

- strict replay preflight：`results/strict_replay_train_env_20260329.json`
- formal config preflight：`results/formal_train_env_20260329.json`

## 4. 最短执行路径

在有 CUDA 和 `llamafactory-cli` 的 GPU 环境上，直接执行：

```bash
cd /path/to/tengxun
RUN_NAME=strict_clean_20260329 \
GOOGLE_API_KEY=你的_key \
./scripts/run_qwen_strict_full.sh
```

如果你只想先拿到去污染后的 FT 结论，不想跑 RAG：

```bash
cd /path/to/tengxun
RUN_NAME=strict_clean_20260329 \
WITH_RAG=0 \
./scripts/run_qwen_strict_full.sh
```

脚本会自动完成：

1. `data_guard`
2. 复制 strict 配置并落成独立 run config
3. strict-clean LoRA 训练
4. `FT only` 评测 + strict 重评分
5. `PE + FT` 评测 + strict 重评分
6. 可选 `PE + RAG + FT` 评测 + strict 重评分

输出目录约定：

- adapter：`artifacts/lora/qwen3.5-9b/<RUN_NAME>/`
- 日志：`logs/<RUN_NAME>.train.log`
- 结果：`results/qwen_strict_runs/<RUN_NAME>/`

## 5. 跑完之后哪些说法才变成完全安全

当 strict-clean 训练和三组评测都落盘后，下面三句话才可以无保留对外使用：

- “FT 增益不依赖训练集 overlap”
- “Qwen strict-clean 默认路线是 `PE + FT` 还是 `PE + RAG + FT`”
- “开源模型最优路线已经完成 strict-clean 闭环”

在这之前，更稳的说法是：

- GPT strict PE 是当前最硬的主结论
- Qwen 历史正式矩阵说明了 PE / RAG / FT 的相对作用
- Qwen strict-clean FT replay 是当前唯一仍待 GPU 收尾的部分
