# Strict 复验与答辩说明（2026-03-29）

## 1. 这条分支修了什么

本分支不是重写历史正式结果，而是在保留正式资产的前提下，新增一套严格复验口径：

- 评分口径从“只看三层并集”扩展为“双口径”：
  - `union F1`：历史正式主分
  - `active-layer macro F1`：strict 主分，只在 gold 或 prediction 非空的层上平均
  - `mislayer rate`：命中的 FQN 中，有多少被放错层
- 数据口径从“历史正式资产”扩展为“strict 复验资产”：
  - `data/fewshot_examples_20_strict.json`
  - `data/finetune_dataset_500_strict.jsonl`
- strict 数据构建规则：
  - 过滤 exact GT overlap
  - 过滤 normalized exact question overlap
  - 过滤 hard question overlap（exact 或 similarity >= `0.90`）
  - `0.85 ~ 0.90` 仅进入审计报告，不自动删除

## 2. 当前 strict 审计结论

### 数据侧

- 历史正式 few-shot exact GT overlap：`2`
- 历史正式 finetune exact GT overlap：`26` 个 row-case pair / `19` 行 / `14` 个 eval case
- 历史正式 finetune normalized exact question overlap：`4`
- 历史正式 finetune hard question overlap：`7`
- strict few-shot / strict finetune 在以下三项均为 `0`：
  - exact GT overlap
  - normalized exact question overlap
  - hard question overlap

详见：`reports/strict_data_audit_20260329.md`

### 评分侧

几组关键 strict 分数如下：

| Experiment | Union F1 | Active-Layer Macro F1 | Mislayer Rate |
|---|---:|---:|---:|
| GPT baseline | 0.2815 | 0.1652 | 0.1954 |
| GLM baseline | 0.0666 | 0.0395 | 0.0556 |
| GPT PE few-shot | 0.5732 | 0.4268 | 0.1694 |
| GPT PE postprocess | 0.6062 | 0.3556 | 0.3037 |
| Qwen PE + FT | 0.4315 | 0.3404 | 0.1309 |
| Qwen PE + RAG + FT | 0.4435 | 0.3182 | 0.2204 |

解释：

- `union F1` 高但 `mislayer rate` 也高，说明模型更像是“找到了 FQN，但层级没放准”。
- `postprocess` 的 union 分很高，但 `mislayer rate` 也明显更高，这和后处理会压平层级信息是一致的。

详见：`reports/strict_scoring_audit_20260329.md`

### 本分支已完成的 strict replay

本次实际新跑出的结果如下：

| Replay | 结果文件 | Union F1 | Active-Layer Macro F1 | Mislayer Rate |
|---|---|---:|---:|---:|
| GPT PE few-shot strict replay | `results/pe_eval_strict_replay_20260329/pe_fewshot_strict.json` | 0.5460 | 0.4035 | 0.1679 |
| GPT PE postprocess strict replay | `results/pe_eval_strict_replay_20260329/pe_postprocess_strict.json` | 0.5935 | 0.3323 | 0.3074 |
| GLM baseline replay (`thinking-mode=disabled`) | `results/glm_eval_strict_replay_20260329_strict.json` | 0.0967 | 0.0432 | 0.0926 |

与历史结果相比：

- GPT PE few-shot：`union -0.0272`，`macro -0.0233`，`mislayer -0.0015`
- GPT PE postprocess：`union -0.0127`，`macro -0.0233`，`mislayer +0.0037`
- GLM baseline replay：`union +0.0301`，`macro +0.0037`，`mislayer +0.0370`

这组 replay 支持两个结论：

- few-shot 增益在 strict 资产上仍然成立，不是靠污染撑出来的。
- postprocess 的确更偏向“提 union、伤层级”，因为 strict macro 比 few-shot 更低，而 mislayer 更高。

## 3. 哪些结果必须重跑，哪些不用

### 必须重跑

如果你要对外声称“PE few-shot 增益不依赖 few-shot 污染”，以下结果必须用 strict few-shot 重跑：

- `results/pe_eval_54_20260328/pe_fewshot.json`
- `results/pe_eval_54_20260328/pe_postprocess.json`
- `results/pe_eval_54_20260328/pe_summary.json`

如果你要对外声称“FT 增益不依赖训练集污染”，以下结果必须用 strict finetune 重训后重跑：

- `results/qwen_ft_20260327_160136*.json`
- `results/qwen_pe_ft_20260327_162308*.json`
- `results/qwen_pe_rag_ft_google_20260328*.json`

### 不必因为这轮 strict 审计而重跑

- GPT baseline
- GLM baseline
- GPT RAG only
- Qwen baseline
- Qwen RAG only
- GPT PE 的 `baseline / system_prompt / cot`

原因很简单：这些结果不依赖被污染的 few-shot 或 finetune 数据，离线 strict 重评分已经足够诚实。

## 4. 推荐重跑顺序

### 最小代价版本

1. 只重跑 GPT PE 的 `fewshot` 和 `postprocess`
2. 更新 PE 报告与对比图
3. 答辩时把 Qwen FT 结果明确标成“历史正式线”，strict FT replay 作为下一步增强

### 完整严格版本

1. 重跑 GPT PE 的 `fewshot` 和 `postprocess`
2. 用 strict finetune 重训 Qwen adapter
3. 重跑 `FT only / PE + FT / PE + RAG + FT`
4. 更新消融矩阵和最终结论

## 5. 可直接执行的命令

### 5.1 GPT PE strict 重跑

只重跑受影响的两个 PE 变体：

```bash
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 scripts/run_pe_eval.py \
  --api-key "<your-gpt-api-key>" \
  --base-url https://ai.td.ee/v1 \
  --model gpt-5.4 \
  --variants fewshot,postprocess \
  --output-dir results/pe_eval_strict_replay
```

然后做 strict 重评分：

```bash
python3 scripts/rescore_result_file.py \
  --path results/pe_eval_strict_replay/pe_fewshot.json

python3 scripts/rescore_result_file.py \
  --path results/pe_eval_strict_replay/pe_postprocess.json
```

### 5.2 GLM baseline 可选重跑

GLM 不因为 few-shot / finetune 泄漏而必须重跑；如果你想做同日复验，可直接跑：

```bash
python3 -m evaluation.run_glm_eval \
  --api-key "<your-glm-api-key>" \
  --model glm-5 \
  --base-url https://open.bigmodel.cn/api/paas/v4 \
  --thinking-mode disabled \
  --cases data/eval_cases.json \
  --output results/glm_eval_strict_replay.json

python3 scripts/rescore_result_file.py \
  --path results/glm_eval_strict_replay.json
```

### 5.3 Qwen strict 训练与重评

只有在你准备更新 FT 结论时才需要这一步。

训练：

```bash
export PYTHONPATH=.
make train-strict
```

或：

```bash
python3 -m finetune.data_guard data/finetune_dataset_500_strict.jsonl
python3 finetune/train_lora.py --config configs/train_config_strict_20260329.yaml
```

评测：

```bash
python3 run_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_20260329 \
  --output results/qwen_ft_strict_replay.json

FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 run_pe_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_20260329 \
  --output results/qwen_pe_ft_strict_replay.json

export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY="<your-google-api-key>"
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
python3 run_pe_rag_ft_eval.py \
  --cases data/eval_cases.json \
  --repo-root external/celery \
  --adapter-path artifacts/lora/qwen3.5-9b/strict_20260329 \
  --output results/qwen_pe_rag_ft_strict_replay.json
```

### 5.4 一键生成 strict 审计

```bash
make audit-strict
make rescore-strict
```

## 6. 答辩时怎么说最稳

- 历史正式结果保留，用来说明项目原始完成度和工程工作量。
- strict 复验结果单独汇报，用来回答“评分是否过宽松”“few-shot/finetune 是否污染”。
- 不要把 strict 与历史正式结果混成一个表，否则导师会继续追问“你到底改的是模型，还是改的是评分和数据”。
- 更稳的说法是：
  - 正式主分仍保留 union F1
  - strict 复验补充 active-layer macro F1 和 mislayer rate
  - strict 数据用于去污染复验，不覆盖历史正式资产

## 7. 当前建议

- GPT PE 的 `fewshot` 和 `postprocess` 已经完成 strict replay，可以直接用于答辩。
- GLM baseline 已完成一次可复验重跑，但要记得固定 `--thinking-mode disabled`。
- Qwen 如果时间紧，可以先不重跑，把 strict 训练入口和脚本准备好；只有在你准备更新 FT 主结论时再启动。
