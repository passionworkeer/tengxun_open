# 数据质检报告

**Owner**: self
**日期**: 2026-03-27 (最终修复版)
**Celery 版本**: b8f85213f45c (2026-03-15)
**状态**: ✅ 所有问题已修复，数据已清理

---

## 一、正式数据集清单

| 文件 | 条目数 | 用途 | 状态 |
|------|--------|------|------|
| `data/eval_cases.json` | **54条** | 正式评测集 | ✅ |
| `data/finetune_dataset_500.jsonl` | **500条** | 微调训练集 | ✅ |
| `data/finetune_dataset_500_local.jsonl` | **500条** | 本地参考版 | ✅ |
| `data/fewshot_examples_20.json` | **20条** | Few-shot 示例 | ✅ |

---

## 二、评测集 (eval_cases.json) — 54条 ✅

### Type 分布

| Type | 数量 | 占比 |
|------|------|------|
| Type A | 7 | 13% |
| Type B | 9 | 17% |
| Type C | 11 | 20% |
| Type D | 11 | 20% |
| Type E | 16 | 30% |
| **总计** | **54** | **100%** |

### Difficulty 分布

| Difficulty | 数量 | 占比 |
|------------|------|------|
| easy | 15 | 28% |
| medium | 19 | 35% |
| hard | 20 | 37% |
| **总计** | **54** | **100%** |

### 覆盖场景

- 顶层懒加载重导出 (`re_export`, `re_export_proxy`)
- 别名解析 (`loader_alias`, `backend_alias`, `alias_resolution`)
- 动态解析 (`symbol_by_name_resolution`)
- 任务注册链路 (`shared_task_registration`, `app_task_registration`)
- 回调链 (`finalize_callback`, `autodiscovery_signal_chain`)
- 命名遮蔽 (`parameter_shadowing`, `class_hierarchy_with_same_logical_name`)
- 环境变量动态覆盖 (`env_var_dynamic_alias_override`)
- 生命周期 (`bootstep_lifecycle_conditional`, `acks_late_failure_matrix`)

---

## 三、微调数据集 (finetune_dataset_500.jsonl) — 500条 ✅

### 数据结构

```json
{
  "instruction": "任务描述",
  "input": "源码上下文",
  "output": "推理过程 + 最终依赖",
  "difficulty": "easy|medium|hard",
  "failure_type": "Type A-E",
  "category": "分类标识",
  "verified": true,
  "verify_method": "manual|libcst"
}
```

### 质量验证

- ✅ 500/500 条有效
- ✅ 无 libcst AST 序列化损坏
- ✅ 所有条目包含完整推理链

---

## 四、Fewshot 数据 (fewshot_examples_20.json) — 20条 ✅

### Type 覆盖

| Type | Fewshot | 说明 |
|------|---------|------|
| Type A | 2 | A01 CLI启动链, A02 current_app首访 |
| Type B | 5 | B01-B05 任务注册与 finalize |
| Type C | 5 | C01-C05 重导出链路 |
| Type D | 4 | D01-D04 命名冲突与遮蔽 |
| Type E | 4 | E01-E04 字符串动态解析 |

---

## 五、清理记录 (2026-03-27)

### 已删除的垃圾文件

| 文件 | 大小 | 原因 |
|------|------|------|
| `data/eval_cases_new_18.json` | 20,825 bytes | 旧版本，已迁移到正式集 |
| `data/eval_cases_migrated_draft.json` | 0 bytes | 空文件 |
| `data/eval_cases_migrated_draft_round4.json` | 47,545 bytes | draft版本，正式版已超要求 |
| `data/archive/finetune_dataset.jsonl` | 1 bytes | 空文件 |
| `data/archive/hard_samples_expanded.jsonl` | 129,377 bytes | 旧数据 |
| `data/archive/pyan3_generated_samples.jsonl` | 44,870 bytes | 旧数据 |
| `data/audit_results.jsonl` | 54,970 bytes | 旧审计结果 |
| `data/audit_report.json` | 2,918 bytes | 旧审计报告 |

**共清理**: 8 个垃圾文件 (~300KB)

---

## 六、数据质量总评

```
评测集:              54 条    ████████████████████ 100% ✅
微调数据集:          500 条   ████████████████████ 100% ✅
本地参考版:          500 条   ████████████████████ 100% ✅
Fewshot:            20 条    ████████████████████ 100% ✅

数据类型覆盖:       Type A-E  ✅ 全部覆盖
难度分布:           easy/medium/hard ✅ 均衡
Celery 源码版本:    b8f85213  ✅ 已锁定
```

---

## 七、参考指标 (GPT-5.4 基线)

| 指标 | 值 |
|------|------|
| Overall Avg F1 | **0.3122** |
| Easy | **0.4475** |
| Medium | **0.2670** |
| Hard | **0.2373** |
| F1=0 失败 case | **19 个（38%）** |

---

**结论**：数据质量已全面达标，正式数据集已冻结，垃圾文件已清理完毕。
