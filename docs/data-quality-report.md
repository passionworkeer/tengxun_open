# 数据质检报告

**Owner**: codex  
**日期**: 2026-03-29  
**Celery 版本**: `b8f85213f45c937670a6a6806ce55326a0eb537f`

## 结论

- `data/eval_cases.json` 仍是唯一正式评测入口，共 `54` 条，全部手工标注。
- 历史正式 few-shot / finetune 资产保留，但不再声称“严格无污染”。
- 当前仓库已额外生成 strict 复验资产：
  - `data/fewshot_examples_20_strict.json`
  - `data/finetune_dataset_500_strict.jsonl`
- strict 资产当前满足：
  - exact GT overlap = `0`
  - normalized exact question overlap = `0`
  - hard question overlap（exact 或 similarity >= `0.90`）= `0`

## 正式资产与 strict 资产

| 文件 | 条目数 | 角色 | 当前口径 |
|------|--------|------|------|
| `data/eval_cases.json` | 54 | 正式评测集 | 正式 |
| `data/fewshot_examples_20.json` | 20 | Few-shot 示例 | 历史正式 |
| `data/finetune_dataset_500.jsonl` | 500 | 微调训练集 | 历史正式 |
| `data/fewshot_examples_20_strict.json` | 20 | Few-shot 示例 | strict 复验 |
| `data/finetune_dataset_500_strict.jsonl` | 500 | 微调训练集 | strict 复验 |

## 污染审计摘要

### 历史正式资产

- few-shot exact GT overlap：`2`
- finetune exact GT overlap：`26` 个 row-case pair / `19` 行 / `14` 个 eval case
- few-shot normalized exact question overlap：`0`
- finetune normalized exact question overlap：`4`
- few-shot hard question overlap：`0`
- finetune hard question overlap：`7`

### strict 复验资产

- few-shot exact GT overlap：`0`
- finetune exact GT overlap：`0`
- few-shot normalized exact question overlap：`0`
- finetune normalized exact question overlap：`0`
- few-shot hard question overlap：`0`
- finetune hard question overlap：`0`

详见：

- `reports/strict_data_audit_20260329.md`

## strict 构建规则

- 过滤 exact GT overlap
- 过滤 normalized exact question overlap
- 过滤 hard question overlap（similarity >= `0.90`）
- `0.85 ~ 0.90` 的 near-overlap 进入审计报告，不自动删除

## 微调数据状态

- strict 微调数据有效记录：`500`
- strict failure type 分布：
  - `Type A = 104`
  - `Type B = 116`
  - `Type C = 89`
  - `Type D = 94`
  - `Type E = 97`

## 使用建议

- 如果你是在复现实习项目原始正式结果，继续使用历史正式资产。
- 如果你是在回答“是否存在训练/评测泄漏”的导师追问，使用 strict 资产。
- 如果你准备继续训练并更新最终答辩结果，优先使用 strict 资产并重跑受影响实验。
