# 项目数据说明文档

> 当前正式口径：`data/eval_cases.json` 是唯一正式评测入口，共 `54` 条，全部手工标注。
> 当前 strict 复验口径：在正式资产之外，额外提供 `fewshot_examples_20_strict.json`、`finetune_dataset_500_strict.jsonl`、`strict_scoring_audit_20260329.md`、`strict_data_audit_20260329.md` 用于答辩防守与去污染复验。
> 其他 `50-case` / `draft` 文件仅用于历史追溯或辅助实验，不作为正式评测入口。

## 概述

本项目用于 **Celery 跨文件依赖分析**。核心任务是给定一个问题，输出该代码问题的完整依赖链：

- `direct_deps`
- `indirect_deps`
- `implicit_deps`

正式主评分指标仍对这三层并集后的 FQN 做精确匹配；三层标签本身仍保留在数据中，用于诊断与展示。
严格复验时，补充使用 `active-layer macro F1` 与 `mislayer rate` 两个分层指标。
这套任务是 `entry-guided` 的：问题文本之外，还会显式提供 `source_file`（运行时映射为 `entry_file`），少量样本再补充 `entry_symbol`。

---

## 数据文件一览

| 文件 | 数量 | 角色 | 说明 |
|------|------|------|------|
| `data/eval_cases.json` | 54 | 正式 | 正式评测集，全部手工标注 |
| `data/fewshot_examples_20_strict.json` | 20 | 当前默认 | 去除 exact GT / hard question overlap 的 few-shot 变体 |
| `data/finetune_dataset_500_strict.jsonl` | 500 | 当前默认 | 去除 exact GT / hard question overlap 的微调变体 |
| `data/fewshot_examples_20.json` | 20 | 历史正式 | Few-shot 示例池，保留作归档对照 |
| `data/finetune_dataset_500.jsonl` | 500 | 历史正式 | LoRA 微调数据，保留作归档对照 |
| `data/hard_samples_expanded.jsonl` | 100 | 辅助 | hard 场景扩展样本 |
| `data/pyan3_generated_samples.jsonl` | 50 | 辅助 | Pyan3 静态图生成样本 |
| `data/audit_results.jsonl` | ~1000 | 辅助 | 审计原始结果 |
| `data/audit_report.json` | - | 辅助 | 审计摘要 |
| `data/eval_cases_migrated_draft_round4.json` | 50 | 历史 | 早期 draft 评测集，不再作为正式入口 |

---

## 1. 正式评测集 `eval_cases.json`

### 用途

正式 `54` 道评测题目，用于基线、PE、RAG 和微调后的统一评估。

### 数据结构

```json
{
  "id": "easy_001",
  "difficulty": "easy",
  "category": "re_export",
  "failure_type": "Type C",
  "implicit_level": null,
  "question": "Which real function does the top-level `celery.shared_task` symbol resolve to?",
  "source_file": "celery/__init__.py",
  "source_commit": "...",
  "ground_truth": {
    "direct_deps": ["celery.app.shared_task"],
    "indirect_deps": [],
    "implicit_deps": []
  },
  "reasoning_hint": "",
  "source_note": ""
}
```

### 当前分布

- Difficulty：`easy 15 / medium 19 / hard 20`
- Failure Type：`Type A 7 / Type B 9 / Type C 11 / Type D 11 / Type E 16`
- 标注方式：`54/54` 全部人工阅读源码后确认

补充说明：

- `source_file` 是正式数据里的稳定入口文件 anchor，不是模型自己猜出来的导航信息。
- 评测 loader 会把 `source_file` 映射到运行时查询用的 `entry_file`，因此评测是 entry-guided，不是 blind question-only。
- 另有 `5/54` 条样本带显式 `entry_symbol` 元信息。

---

## 2. Few-shot 示例池 `fewshot_examples_20.json`

### 用途

`20` 条高质量 few-shot 示例，用于 Prompt Engineering 优化。

### 数据结构

```json
{
  "id": "B01",
  "title": "@shared_task 装饰器注册",
  "failure_type": "Type B",
  "question": "给定 `@shared_task` 装饰后的函数，最终注册到哪个任务对象路径？",
  "environment_preconditions": [],
  "reasoning_steps": [
    "Step 1: 定位 `shared_task` 在 `celery/app/__init__.py`",
    "Step 2: 发现 `shared_task` 内部先通过 `connect_on_app_finalize(...)` 注册 finalize 回调"
  ],
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery._task_from_fun"],
    "indirect_deps": ["celery._state.connect_on_app_finalize"],
    "implicit_deps": ["celery.app.shared_task"]
  }
}
```

### 配比

- Type B：5 条
- Type C：5 条
- Type D：4 条
- Type E：4 条
- Type A：2 条

补充说明：

- 当前默认交付 few-shot 是 `fewshot_examples_20_strict.json`。
- `fewshot_examples_20.json` 是历史正式 few-shot 资产。
- `pe/prompt_templates_v2.py` 支持通过 `FEWSHOT_DATA_PATH` 切换到 strict few-shot。

---

## 3. 微调训练数据 `finetune_dataset_500.jsonl`

### 用途

当前默认 `500` 条 strict-clean LoRA 微调训练数据。

### 数据结构

```jsonl
{
  "instruction": "分析跨包依赖的最终来源",
  "input": "# celery/app/base.py\n# import 部分: from kombu.utils.uuid import uuid\n# 问题: base.py 中使用的 kombu uuid 函数...",
  "output": "推理过程：...\n最终依赖：\n{\"direct_deps\": [\"kombu.utils.uuid.uuid\"], ...}",
  "difficulty": "hard",
  "failure_type": "Type C",
  "category": "cross_package_import",
  "verified": true,
  "verify_method": "celery源码验证"
}
```

### 校验口径

- `finetune/data_guard.py` 会对 **Celery 内部 FQN** 做源码存在性校验。
- 对白名单中的外部依赖包（如 `kombu`、`vine`、`billiard`）做显式放行。
- 因此它是“面向本任务的数据守卫”，不是对所有外部依赖都做源码级追踪。

补充说明：

- 当前默认微调集是 `finetune_dataset_500_strict.jsonl`。
- `finetune_dataset_500.jsonl` 是历史正式 500 条训练资产。
- 若目标是重放 strict 训练流程，使用 `finetune_dataset_500_strict.jsonl`，并配合 `configs/strict_clean_20260329.yaml` / `make train`。
- `configs/train_config_strict_20260329.yaml` 仅保留为第一版 strict 草案，不再作为推荐重训入口。

---

## 4. 辅助与历史数据

### `hard_samples_expanded.jsonl`

- 定位：辅助 hard 场景扩展样本
- 说明：可用于派生训练或增强分析，不是正式评测集

### `pyan3_generated_samples.jsonl`

- 定位：Pyan3 静态图生成样本
- 说明：辅助挖样与扩展研究，不纳入正式评测口径

### `audit_results.jsonl`

- 定位：审计原始数据
- 说明：用于内部排查和统计，不作为正式交付核心资产

### `eval_cases_migrated_draft_round4.json`

- 定位：历史 draft 评测集
- 说明：保留演进过程，不再作为正式评测入口

---

## 快速开始

### 1. 跑正式评测

```bash
# GPT-5.4
python3 -m evaluation.run_gpt_eval \
    --api-key "<api-key>" \
    --cases data/eval_cases.json \
    --output results/gpt5_eval_results.json

# Qwen 本地部署
python3 -m evaluation.run_qwen_eval \
    --base-url http://localhost:8000/v1 \
    --cases data/eval_cases.json \
    --output results/qwen3_eval_results.json

# 对已有结果做 strict 重评分
python3 scripts/rescore_result_file.py \
    --path results/gpt5_eval_results.json
```

### 2. 校验当前默认微调数据

```bash
python3 -m finetune.data_guard data/finetune_dataset_500_strict.jsonl

# 历史正式归档版
python3 -m finetune.data_guard data/finetune_dataset_500.jsonl
```

### 3. 重建正式 embedding cache

```bash
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY="<api-key>"
make prepare-rag-cache
```

如果你只想直接调用底层脚本，也可以：

```bash
python3 scripts/precompute_embeddings.py --repo-root external/celery
```

### 4. 使用 few-shot 示例

读取 `data/fewshot_examples_20_strict.json`，在 Prompt 组装阶段按失效类型挑选相关示例注入。

---

## 数据质量说明

| 文件 | 验证状态 | 说明 |
|------|---------|------|
| `eval_cases.json` | ✅ 已验证 | `54` 条全部人工审核 |
| `fewshot_examples_20_strict.json` | ✅ 当前默认 | 去除 exact GT / hard question overlap 的当前 few-shot 入口 |
| `fewshot_examples_20.json` | ✅ 已验证 | `20` 条历史正式 few-shot，保留历史口径 |
| `finetune_dataset_500_strict.jsonl` | ✅ 当前默认 | 去除 exact GT / hard question overlap 的当前微调入口 |
| `finetune_dataset_500.jsonl` | ⚠️ 历史正式 | `500` 条历史训练数据，默认 gate 现在会报告 overlap 风险 |
| `hard_samples_expanded.jsonl` | ✅ 已整理 | 辅助样本，不是正式评测集 |
| `pyan3_generated_samples.jsonl` | ⚠️ 辅助数据 | 不纳入正式交付口径 |

---

## 依赖分析输出格式

所有正式数据统一使用以下 JSON 格式：

```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery._state.connect_on_app_finalize"
    ],
    "implicit_deps": [
      "celery.app.shared_task"
    ]
  }
}
```

### 字段说明
| 字段 | 说明 | 示例 |
|------|------|------|
| `direct_deps` | 直接依赖（当前文件直接导入） | `celery.utils.imports.gen_task_name` |
| `indirect_deps` | 间接依赖（通过其他模块再导出） | `celery.app.base.Celery.gen_task_name` |
| `implicit_deps` | 隐式依赖（装饰器、动态加载等） | `celery.local.Proxy` |

---

## 注意事项

1. **FQN 格式**：必须使用 `.` 分隔符，如 `celery.app.base.Celery`，而非 `celery/app/base.py:Celery`
2. **UTF-8 BOM**：部分 JSON 文件带 BOM，读取时使用 `encoding='utf-8-sig'`
3. **评测数据**：正式评测只用 `data/eval_cases.json`；`eval_cases_migrated_draft_round4.json` 是历史版本
