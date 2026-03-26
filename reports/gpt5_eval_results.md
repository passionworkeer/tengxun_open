# GPT-5.4 Evaluation Results & Failure Bottleneck Analysis

## Executive Summary

| Metric | Value |
|--------|-------|
| **Model** | gpt-5.4 |
| **Total Cases** | 50 |
| **Overall Average F1** | 0.3122 |
| **API Endpoint** | https://ai.td.ee/v1 |

---

## Performance by Difficulty

| Difficulty | Cases | Avg F1 |
|------------|-------|--------|
| EASY | 15 | 0.4475 |
| MEDIUM | 20 | 0.2670 |
| HARD | 15 | 0.2373 |

---

## Failure Analysis: 19 Cases with F1=0

### Failure Type Bottleneck Heatmap

| Failure Type | Count | Percentage | Description |
|-------------|-------|------------|-------------|
| **Type E** | 8 | 42% | 动态符号解析 (symbol_by_name/string resolution) |
| **Type B** | 5 | 26% | 信号回调链 (signal/callback chains) |
| **Type C** | 3 | 16% | Re-export/名称生成 |
| **Type A** | 2 | 11% | Bootstep生命周期 |
| **Type D** | 1 | 5% | 命名空间混淆 |

---

## Type E Deep Dive: Root Cause Analysis

**8个Type E失败案例是本次评测最有价值的发现。**

经逐条分析，根因分布如下：

| Root Cause | Count | Percentage | Example |
|------------|-------|------------|---------|
| **格式问题** (System Prompt可修复) | 2 | 25% | `celery.concurrency.eventlet:TaskPool` 应为 `.` |
| **语义问题** (RAG/FT需解决) | 6 | 75% | 输出文件路径而非FQN，或追踪到错误符号 |

### 格式问题 (2 cases) - System Prompt可修复

| Case | Prediction | Ground Truth | Fix |
|------|------------|--------------|-----|
| easy_012 | `celery.concurrency.eventlet:TaskPool` | `celery.concurrency.eventlet.TaskPool` | 将 `:` 替换为 `.` |
| easy_013 | `celery.concurrency.solo:TaskPool` | `celery.concurrency.solo.TaskPool` | 将 `:` 替换为 `.` |

**结论**: 只需在System Prompt加一句"必须用点号分隔FQN"，这2个case可从F1=0修复到接近满分。

### 语义问题 (6 cases) - RAG/FT需解决

| Case | Prediction | Ground Truth | 问题描述 |
|------|------------|--------------|---------|
| hard_004 | `celery.worker.request:Request` (格式对但indirect全错) | `celery.worker.request.Request` | 模型不知道 `task.Request` 在策略里的完整解析路径 |
| medium_008 | `celery/app/task.py: Task.start_strategy` | `celery.worker.strategy.default` | 追踪到了错误的符号入口 |
| medium_007 | `celery/_state.py, celery/app/base.py...` (文件列表) | `celery.loaders.default.Loader` | 只知道涉及哪些文件，不知道最终实例化的类 |
| celery_hard_018 | `celery/fixups/django.py` | `celery.contrib.django.task.DjangoTask` | 完全不知道Django fixup条件下Task类的动态解析终点 |
| celery_medium_020 | `celery/_state.py...` (文件列表) | `celery.loaders.default.Loader` | 只知道涉及哪些文件，不知道loader属性的动态解析链 |
| medium_021 | `Celery.__init__` 实现细节 | `celery.utils.imports.symbol_by_name` | 追踪到使用位置而非函数定义 |

---

## 核心洞察

### GPT-5.4 在 Type E 失败的根因分析

**25% 是格式问题**（System Prompt可修复）
- 输出 `:` 分隔符而非 `.`

**75% 是语义问题**（动态符号解析的真实盲区）

具体表现：
1. **输出文件路径而非FQN** (medium_007, celery_medium_020)
   - 模型知道涉及哪些模块，但不知道符号解析的终点
2. **追踪到错误的符号** (medium_008, hard_004)
   - 模型追踪到了调用栈中的某个中间函数，而非 `symbol_by_name` 的解析目标
3. **完全不知道动态加载的终点** (celery_hard_018)
   - 在Django fixup条件下，`app.Task` 最终解析到 `DjangoTask`，但模型不知道

---

## 优化策略优先级

| 策略 | 解决的问题 | 预期F1增益 |
|------|----------|-----------|
| **System Prompt修格式** | Type E中的2个格式问题 | +0.02 (4% case从0→0.5+) |
| **RAG** | 提供动态符号解析的上下文（symbol_by_name的源码/文档） | 解决6个Type E语义问题 + 部分Type B/C |
| **FT** | 让模型学会symbol_by_name的推理模式 | 解决Type E的根因，但需要大量同类数据 |

**System Prompt修格式是PE消融实验里最漂亮的数据点**：
- 改动最小（只加一句话）
- 增益可量化（+0.02 F1）
- 但这只是低垂的果实，真正的问题在语义

---

## F1 Score Distribution

| Range | Count |
|-------|-------|
| 0.0-0.1 | 19 |
| 0.1-0.2 | 4 |
| 0.2-0.3 | 5 |
| 0.3-0.4 | 3 |
| 0.4-0.5 | 0 |
| 0.5-0.6 | 11 |
| 0.6-0.7 | 3 |
| 0.7-0.8 | 0 |
| 0.8-0.9 | 1 |
| 0.9-1.0 | 4 |

---

## Top Performing Categories

| Category | Cases | Avg F1 |
|----------|-------|--------|
| module_alias | 1 | 0.8000 |
| backend_alias | 1 | 0.6667 |
| app_task_registration | 1 | 0.6667 |
| loader_smart_import_fallback | 1 | 0.6667 |
| re-export | 9 | 0.5870 |
| autodiscovery_fixup_import | 1 | 0.5714 |
| fixup_string_entry_resolution | 1 | 0.5714 |
| loader_default_resolution | 1 | 0.5455 |
| loader_alias | 2 | 0.5357 |
| backend_url_alias | 1 | 0.5333 |

---

## Detailed Results

| Case ID | Difficulty | F1 |
|---------|------------|-----|
| easy_001 | easy | 0.2500 |
| easy_002 | easy | 0.0000 |
| easy_003 | easy | 0.5714 |
| easy_004 | easy | 0.2857 |
| easy_007 | easy | 0.3333 |
| easy_005 | easy | 0.5714 |
| easy_006 | easy | 0.0000 |
| easy_008 | easy | 0.5000 |
| easy_010 | easy | 1.0000 |
| easy_011 | easy | 1.0000 |
| easy_012 | easy | 0.0000 |
| easy_013 | easy | 0.0000 |
| easy_014 | easy | 1.0000 |
| easy_015 | easy | 0.2000 |
| easy_016 | easy | 1.0000 |
| medium_001 | medium | 0.6667 |
| medium_002 | medium | 0.5000 |
| medium_003 | medium | 0.2222 |
| medium_004 | medium | 0.0000 |
| medium_005 | medium | 0.5455 |
| medium_008 | medium | 0.0000 |
| medium_006 | medium | 0.5333 |
| medium_007 | medium | 0.0000 |
| medium_011 | medium | 0.5000 |
| medium_012 | medium | 0.0000 |
| medium_013 | medium | 0.1667 |
| medium_014 | medium | 0.0000 |
| medium_015 | medium | 0.8000 |
| medium_016 | medium | 0.3333 |
| medium_017 | medium | 0.5000 |
| medium_018 | medium | 0.0000 |
| medium_020 | medium | 0.0000 |
| medium_021 | medium | 0.0000 |
| hard_001 | hard | 0.1667 |
| hard_002 | hard | 0.6667 |
| hard_003 | hard | 0.0000 |
| hard_004 | hard | 0.0000 |
| hard_015 | hard | 0.1765 |
| celery_hard_014 | hard | 0.2500 |
| celery_hard_016 | hard | 0.5714 |
| celery_hard_019 | hard | 0.6667 |
| celery_hard_013 | hard | 0.3750 |
| celery_hard_015 | hard | 0.0000 |
| celery_hard_018 | hard | 0.0000 |
| celery_hard_121 | hard | 0.5333 |
| celery_hard_122 | hard | 0.0000 |
| celery_hard_024 | hard | 0.0000 |
| celery_hard_025 | hard | 0.1538 |
| celery_medium_017 | medium | 0.5714 |
| celery_medium_020 | medium | 0.0000 |

---

## Files Generated

- `results/gpt5_eval_results.json` - 完整评测结果
- `results/gpt5_failed_cases_detail.json` - 19个失败案例的详细原始输出
- `reports/gpt5_failure_bottleneck_analysis.md` - 瓶颈分析详细报告