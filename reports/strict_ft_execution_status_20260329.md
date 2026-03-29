# Strict FT 执行状态（2026-03-29）

> 历史说明：这份文档记录的是 **GPU 执行前**，为什么本机无法完成 strict-clean 重训。  
> 当前最终状态请优先看：
> - `reports/qwen_strict_closeout_20260329.md`
> - `reports/qwen_strict_result_audit_20260329.md`

这份说明只回答一个问题：

> 为什么 Qwen strict-clean 微调线现在还没有在本机直接重跑完成？

## 1. 当前已就绪的部分

- strict 微调数据已就绪：`data/finetune_dataset_500_strict.jsonl`
- strict 数据映射已注册：`dataset_info.json -> fintune_qwen_dep_strict`
- strict 重训配置已就绪：`configs/train_config_strict_replay_20260329.yaml`
- strict 一键执行脚本已就绪：`scripts/run_qwen_strict_full.sh`
- strict 评测入口已就绪：
  - `run_ft_eval.py --strategy ft`
  - `run_ft_eval.py --strategy pe_ft`
  - `run_ft_eval.py --strategy pe_rag_ft`
- strict 训练环境检查脚本已就绪：`scripts/check_train_env.py`

换句话说，**代码链路已经补全**，缺的不是“脚本”，而是“可用的 GPU 训练环境”。

此外，strict replay 配置已经补上：

- `eval_steps=50`
- `save_steps=50`
- `load_best_model_at_end=true`

也就是说，下一次 strict-clean 重训可以同时产出逐步 `eval_loss` 和中间 checkpoint，不会再重复历史正式训练里“只有最终 eval_loss”的问题。

## 2. 本机前置检查结果

实际执行：

```bash
python3 scripts/check_train_env.py \
  --config configs/train_config_strict_replay_20260329.yaml \
  --require-cuda \
  --json-out results/strict_replay_train_env_20260329.json
```

结果文件：`results/strict_replay_train_env_20260329.json`

结论：`overall = FAIL`

失败项只有两个，但都属于硬阻塞：

| 检查项 | 结果 | 说明 |
|---|---|---|
| CUDA | FAIL | 当前机器无 CUDA，仅有 Apple MPS |
| `llamafactory-cli` | FAIL | 当前环境未安装训练启动器 |

同时，以下项目已经通过：

- Python 可用
- torch 可用
- strict 数据文件存在
- `dataset_info.json` 注册完整
- Celery 源码目录存在

所以这不是“仓库没准备好”，而是：

> 当前这台 Mac 只适合做数据、评测、文档和 orchestration，不适合承担正式 Qwen 9B strict-clean LoRA 训练。

额外已经落盘的对比证据：

- strict replay preflight：`results/strict_replay_train_env_20260329.json`
- formal config preflight：`results/formal_train_env_20260329.json`

这组对比现在能直接说明：

- strict replay 配置的 `eval_steps=50 / save_steps=50` 是合理的
- 历史正式配置的 `eval_steps=500 / save_steps=500` 都超过了估算总步数 `339`
- 因此旧训练没有逐步 `eval_loss` 曲线，不再只是经验解释，而是有结构化证据

## 3. 当前最短执行路径

如果切到外部 GPU 环境，最短命令已经不是手工拼接，而是一条：

```bash
make qwen-strict-rerun
```

它会顺序完成：

1. `nvidia-smi` 环境检查
2. `data_guard` 校验
3. materialize strict config
4. strict-clean LoRA 训练
5. `FT only` 评测 + strict 重评分
6. `PE + FT` 评测 + strict 重评分
7. `PE + RAG + FT` 评测 + strict 重评分（满足 RAG 条件时）

对应脚本：`scripts/run_qwen_strict_full.sh`

## 4. 对当时答辩口径的影响

这条状态说明意味着：

- GPT strict PE 结论已经是干净且可复验的
- Qwen `FT only / PE + FT / PE + RAG + FT` 当时仍然属于**历史正式结果**
- strict-clean Qwen FT 线当时已经具备完整执行包，但**尚未在可用 GPU 环境上重新落盘**

因此更稳妥的对外说法应该是：

- “开源模型历史正式最高分”是 `Qwen PE + RAG + FT = 0.4435`
- “当前 strict-clean 微调复验入口已经补齐，但需要外部 CUDA 环境执行”

## 5. 建议

如果目标是继续拉分，优先级只有一件事：

1. 在外部 GPU 环境执行 `make qwen-strict-rerun`

这一步补完以后，当前项目最容易被严格导师卡住的硬伤就只剩下结果本身，而不是方法学和复现链路。
