# 项目数据说明文档

## 概述

本项目用于 **Celery 跨文件依赖分析**，核心任务是给定一个问题，输出该代码的完整依赖链（direct_deps / indirect_deps / implicit_deps）。

---

## 数据文件一览

| 文件 | 数量 | 用途 |
|------|------|------|
| `data/eval_cases_migrated_draft_round4.json` | 50 | **评测数据集**（正式评测用） |
| `data/fewshot_examples_20.json` | 20 | Few-shot 示例池 |
| `data/finetune_dataset_500.jsonl` | 500 | 微调训练数据 |
| `data/hard_samples_expanded.jsonl` | 100 | 困难样本扩展数据 |
| `data/pyan3_generated_samples.jsonl` | 50 | Pyan3 图分析生成的样本 |
| `data/audit_results.jsonl` | ~1000 | 审计结果原始数据 |
| `data/audit_report.json` | - | 审计报告摘要 |

---

## 1. 评测数据集 `eval_cases_migrated_draft_round4.json`

### 用途
**50 道评测题目**，用于评估模型的 Celery 依赖分析能力。跑评测时使用这个文件。

### 数据结构

```json
{
  "id": "easy_001",                    // 案例唯一ID
  "difficulty": "easy",                // 难度: easy / medium / hard
  "category": "re_export",             // 失败类型分类
  "failure_type": "Type C",           // 失效类型: Type A / B / C / D / E
  "implicit_level": null,              // 隐式依赖层级
  "question": "Which real function does the top-level `celery.shared_task` symbol resolve to?",
  "source_file": "celery/__init__.py", // 入口文件
  "source_commit": "...",              // 源码 commit
  "ground_truth": {                    // 标准答案
    "direct_deps": ["celery.app.shared_task"],
    "indirect_deps": [],
    "implicit_deps": []
  },
  "reasoning_hint": "",                // 推理提示
  "source_note": ""                    // 来源备注
}
```

### 难度分布
- **Easy**: 15 cases
- **Medium**: 20 cases  
- **Hard**: 15 cases

### 失败类型分布（Failure Type Bottleneck）
| Type | 描述 | 典型问题 |
|------|------|---------|
| **Type A** | Bootstep生命周期 | Blueprint.apply 调用顺序 |
| **Type B** | 信号回调链 | @shared_task, connect_on_app_finalize |
| **Type C** | Re-export | `__init__.py` 多层转发、别名 |
| **Type D** | 命名空间混淆 | 同名函数、局部覆盖 |
| **Type E** | 动态符号解析 | symbol_by_name、importlib、配置字符串 |

---

## 2. Few-shot 示例池 `fewshot_examples_20.json`

### 用途
20 条高质量 few-shot 示例，按失效类型配比，用于 Prompt Engineering 优化。

### 数据结构

```json
{
  "id": "B01",                         // 示例ID
  "title": "@shared_task 装饰器注册", // 标题
  "failure_type": "Type B",            // 失效类型
  "question": "给定 `@shared_task` 装饰后的函数，最终注册到哪个任务对象路径？",
  "environment_preconditions": [],       // 环境前提条件
  "reasoning_steps": [                 // 推理步骤
    "Step 1: 定位 `shared_task` 在 `celery/app/__init__.py`",
    "Step 2: 发现 `shared_task` 内部先通过 `connect_on_app_finalize(...)` 注册 finalize 回调",
    "..."
  ],
  "ground_truth": {                    // 标准答案
    "direct_deps": ["celery.app.base.Celery._task_from_fun"],
    "indirect_deps": ["celery._state.connect_on_app_finalize"],
    "implicit_deps": ["celery.app.shared_task"]
  }
}
```

### 配比
- Type B (装饰器): 5 条
- Type C (再导出): 5 条
- Type D (命名空间): 4 条
- Type E (动态加载): 4 条
- Type A (长上下文): 2 条

---

## 3. 微调训练数据 `finetune_dataset_500.jsonl`

### 用途
用于 LoRA 微调训练，已验证质量。

### 数据结构（Alpaca 格式）

```jsonl
{
  "instruction": "分析跨包依赖的最终来源",     // 任务指令
  "input": "# celery/app/base.py\n# import 部分: from kombu.utils.uuid import uuid\n# 问题: base.py 中使用的 kombu uuid 函数...",  // 输入（代码+问题）
  "output": "推理过程：\nStep 1: celery/app/base.py 直接从 kombu 包导入 uuid\n...\n最终依赖：\n{\"direct_deps\": [\"kombu.utils.uuid.uuid\"], ...}",  // 完整推理+答案
  "difficulty": "hard",
  "failure_type": "Type C",
  "category": "cross_package_import",
  "verified": true,
  "verify_method": "celery源码验证"
}
```

### 字段说明
| 字段 | 说明 |
|------|------|
| `instruction` | 任务描述/指令 |
| `input` | 输入内容（代码片段+问题） |
| `output` | 完整回答（推理过程+JSON答案） |
| `difficulty` | 难度等级 |
| `failure_type` | 失败类型 |
| `category` | 具体分类 |
| `verified` | 是否已验证 |
| `verify_method` | 验证方式 |

---

## 4. 困难样本扩展 `hard_samples_expanded.jsonl`

### 用途
100 条困难样本，用于提升模型在硬场景的表现。

### 数据结构
同 `finetune_dataset_500.jsonl`，但全部是 hard 难度。

```jsonl
{"instruction": "...", "input": "...", "output": "...", "difficulty": "hard", "failure_type": "...", ...}
```

---

## 5. Pyan3 分析样本 `pyan3_generated_samples.jsonl`

### 用途
50 条由 Pyan3 静态图分析工具生成的样本。

### 数据结构
同 finetune 数据格式，包含 `source_project: "pyan3"` 标识。

---

## 6. 审计结果 `audit_results.jsonl`

### 用途
~1000 条审计结果原始数据。

### 字段
```json
{"case_id": "...", "predicted_deps": [...], "actual_deps": [...], "match_score": ...}
```

---

## 快速开始

### 1. 跑评测（使用 eval_cases）

```bash
# GPT-5.4
python3 -m evaluation.run_gpt_eval \
    --api-key "<api-key>" \
    --cases data/eval_cases_migrated_draft_round4.json \
    --output results/gpt5_eval_results.json \
    --max-cases 50

# Qwen 本地部署
python3 -m evaluation.run_qwen_eval \
    --base-url http://localhost:8000/v1 \
    --cases data/eval_cases_migrated_draft_round4.json \
    --output results/qwen3_eval_results.json
```

### 2. 生成微调数据

```bash
python3 scripts/generate_finetune_data.py \
    --input results/gpt5_eval_results.json \
    --output data/my_finetune_data.jsonl \
    --min-f1 0.5
```

### 3. 使用 few-shot 示例

读取 `data/fewshot_examples_20.json`，在 System Prompt 中选择相关示例注入。

---

## 数据质量说明

| 文件 | 验证状态 | 说明 |
|------|---------|------|
| eval_cases | ✅ 已验证 | 50道题全部人工审核 |
| fewshot | ✅ 已验证 | 20条示例含完整推理链 |
| finetune_dataset_500 | ✅ 已验证 | 500条含verified=True |
| hard_samples_expanded | ✅ 已验证 | 100条困难样本 |
| pyan3 | ⚠️ 待验证 | 50条待人工审核 |

---

## 依赖分析输出格式

所有数据统一使用以下 JSON 格式：

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
3. **评测数据**：只用 `eval_cases_migrated_draft_round4.json`，其他是历史版本或训练数据
