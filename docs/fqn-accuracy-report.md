# FQN 可溯源性核验报告

**Owner**: self  
**日期**: 2026-03-25  
**Celery 快照**: `b8f85213f45c937670a6a6806ce55326a0eb537f`

## 0. 先把边界写死

这份文档只回答一个问题：

> 当前正式样本池里的 `ground_truth` FQN，能不能在当前 Celery 源码快照里找到真实定义、真实导入链或真实解析终点。

这份文档**不回答**以下问题：

- 这些样本是否已经满足正式 `eval` 集的升格标准。
- 这些样本是否已经满足“单问单判、最小闭包、运行时前提完整”的严格要求。
- `few-shot` 是否已经足够防泄漏、覆盖足够均衡、教学信号足够稳定。
- `finetune` 数据是否可训练。
- `RAG` 实验是否已可复现。

换句话说，**FQN 可溯源性高，不等于数据集已经可以直接用于正式实验**。

---

## 1. 审计范围

本次只核验当前仓库里已经落地的两份正式池文件：

- `data/eval_cases.json`：12 条正式 `eval` 样本
- `data/fewshot_examples_20.json`：20 条正式 `few-shot` 样本

本次**不在范围内**的内容：

- `data/eval_cases_migrated_draft_round4.json`：32 条 `draft eval`
- `data/finetune_dataset_500.jsonl`：当前仍是 `0 valid`
- RAG 原型与检索实验产物

所以，这份报告的覆盖上限就是：

- 正式 `eval`：12 条
- 正式 `few-shot`：20 条
- 合计：32 条正式样本

---

## 2. 为什么旧版统计必须作废

旧版文档里同时出现了两套互不兼容的口径：

- 开头写的是“34 个 FQN，26 正确，准确率 76%”
- 结尾又写成“31/32 = 97%”

这两套数字不能混用，原因有三点：

1. 前者把“样本里的多个辅助依赖 FQN”也混进了分母，后者则是按“样本条目数”在算。
2. 旧版“硬错误 2 个”的问题清单实际上只明确列出 1 个硬错误，统计本身就不自洽。
3. 旧版把一部分**已经修过的历史问题**继续写成“当前未修”，结论已经过时。

因此，旧版里的“76%”和“97%”都不应该再作为当前仓库状态的正式结论。

---

## 3. 这次重写后的核心结论

### 3.1 可以确认的事

- 当前正式池的审计范围是 32 条样本，不是 34 个混口径的 FQN 计数。
- 旧版报告里最显眼的两个“当前问题”已经不是 live issue：
  - `E02` 当前正式 `few-shot` 文件里已经写成 `kombu.utils.imports.symbol_by_name`，不再是旧版报告里的错误路径。
  - `D04` 不能再写成“无测试覆盖”。虽然 `external/celery/celery/utils/dispatch/signal.py` 里有 `# pragma: no cover`，但当前源码快照下仍然能在 `external/celery/t/unit/utils/test_dispatcher.py` 里找到 `dispatch_uid` 去重相关测试。
- 当前最明确、仍然成立的 live caveat 是：
  - `data/eval_cases.json` 里的 `medium_003` 仍然缺少显式环境前提，题面本身没有把 `concurrent.futures` 可用性写进样本契约。

### 3.2 更准确的一句话结论

> 当前正式池里，没有证据表明存在“大面积编造 FQN”的问题；更现实的风险已经转移到样本契约、正式集规模、formal/draft 边界、微调数据为空、RAG 仍是原型这些层面。

---

## 4. 对旧版问题的逐项校正

### 4.1 E02：旧版写成错误，当前正式文件里其实已经修了

旧版说：

- `indirect_deps` 错写成 `celery.utils.imports.symbol_by_name`
- 应改成 `kombu.utils.imports.symbol_by_name`

当前实际文件 `data/fewshot_examples_20.json` 中，`E02` 已经是：

```json
"indirect_deps": [
  "kombu.utils.imports.symbol_by_name"
]
```

因此，**E02 不应再作为当前正式池的 live FQN 错误继续写在结论里**。

### 4.2 D04：旧版写成“无测试覆盖”并不成立

旧版把 `D04` 定性为：

- `signal.py` 全文件 `# pragma: no cover`
- 因此“无法验证”

这个说法不够准确。当前源码快照下，至少可以确认：

- `external/celery/celery/utils/dispatch/signal.py` 中，`_make_lookup_key` 和 `Signal._connect_signal` 的去重逻辑是清楚可读的。
- `external/celery/t/unit/utils/test_dispatcher.py` 中存在 `dispatch_uid` 去重相关测试：
  - 重复注册同一 `dispatch_uid` 时，`receivers` 长度保持为 1。
  - `retry=True` 与 `dispatch_uid` 的组合也有测试覆盖。

所以，`D04` 更准确的描述应该是：

> 它属于“有源码依据，也能找到相关测试佐证”的样本，不应继续被写成“无运行时证据、无法验证”。

### 4.3 D02：旧版“hint 过薄”的批评已部分过时

旧版把 `D02` 的问题写成：

- `reasoning_hint` 把 `gen_task_name` 说成了“thin wrapper”
- 但没有体现 `sys.modules` 和 `MP_MAIN_FILE`

当前正式 `few-shot` 文件里，`D02` 已经不再只停留在“thin wrapper”级别，而是明确写了：

- `Celery.task` 的同步注册路径
- `_task_from_fun`
- `gen_task_name`
- `self._tasks` 的 first-wins 语义

这不代表它已经完美，但至少**不能再直接沿用旧版“D02 仍是当前问题”的表述**。

### 4.4 medium_003：这是当前仍然成立的 live caveat

`data/eval_cases.json` 中的 `medium_003` 当前仍是旧 schema，只有：

- `question`
- `gold_fqns`
- `reasoning_hint`

它没有能力显式承载 `environment_preconditions`。而该题的真实语义是：

- `threads` alias 只有在 `concurrent.futures` 可导入时才会注册进 `ALIASES`

因此，这条样本当前更准确的状态不是“FQN 错了”，而是：

> **答案路径本身可溯源，但正式样本契约不完整。**

这件事应该在后续迁移到新 schema 时补上，而不是继续混在“FQN 错误率”里。

---

## 5. 当前应采用的汇报口径

以后再引用这份报告，建议统一用下面这套口径。

### 5.1 FQN 可溯源性

- 审计对象：当前正式池 32 条样本
- 结论：当前没有证据表明正式池里存在大面积伪造 FQN
- 已确认被旧版误报、但当前已修或可佐证的项：
  - `E02`
  - `D04`
  - `D02` 的旧版批评已不应直接原样沿用

### 5.2 样本有效性

这一层和 FQN 可溯源性是两回事。当前仍然存在的问题包括：

- `eval_cases.json` 仍是旧 schema，只包含 12 条正式样本
- `medium_003` 这类题目的环境前提无法在旧 schema 中显式表达
- `draft eval` 虽已扩到 32 条，但仍未通过 formal 升格 gate
- 正式 `eval` 与正式 `few-shot` 在结构覆盖上仍有错位，尤其是 `draft` 侧 `Type D` 仍偏少

### 5.3 实验可启动性

这一层更不能从 FQN 报告直接推出。当前项目现实仍然是：

- 正式 `eval`：12 条
- `draft eval`：32 条，但仍处于 hold
- 正式 `few-shot`：20 条
- `finetune`：`0 valid`
- `RAG`：只有原型，没有正式检索报告

因此，**不能把“FQN 基本能对上源码”误读成“实验线已经 ready”**。

---

## 6. 本报告现在真正想指出的核心问题

当前最需要修正的，不是“数据里充满编造 FQN”，而是下面这个更现实的问题：

> 旧版文档把“局部符号路径可追溯”写成了“整体数据质量已经足够高”，这会直接误导后续实验决策。

更具体地说，旧版文档容易让人误读成：

- 正式 `eval` 已经足够稳定
- 正式 `few-shot` 的正确性问题已经完全收口
- 可以基于这份报告直接启动 baseline / RAG / finetune

这些推论都不成立。

这份文档现在应该承担的角色只有一个：

> 作为“符号路径是否来自真实源码”的审计记录，而不是“整体数据是否已可正式实验”的放行凭证。

---

## 7. 建议落地动作

### P0

- 以后不再引用旧版“34 个 FQN / 76%”和“31/32 = 97%”这两组混口径统计。
- 在所有状态文档里，把这份报告的定位统一写成“FQN 可溯源性核验”，不要再写成“整体答案准确性证明”。
- 明确把 `medium_003` 记录为“需在新 schema 中补环境前提”的样本契约问题。

### P1

- 如果后续还要做严格版 FQN 报告，按“正式池 32 条样本”重新逐条复核并统一统计口径。
- 新版统计必须把三层概念拆开：
  - `FQN traceability`
  - `sample validity`
  - `experiment readiness`

### P2

- 把当前项目现实写进所有相关结论页，避免口径外推：
  - 正式 `eval=12`
  - `draft eval=32`
  - 正式 `few-shot=20`
  - `finetune valid=0`
  - `RAG prototype only`

---

## 8. 最终结论

这份报告重写后的结论应该是：

> 当前正式样本池里的 FQN 路径，整体上没有表现出“大面积编造”的迹象；旧版报告里一些最刺眼的问题，如 `E02` 路径错误、`D04` 无测试覆盖、`D02` 说明过薄，至少已有一部分不再是当前 live issue。  
> 但这并不意味着数据集已经可以直接用于正式实验。当前真正阻塞项目的，仍然是正式 `eval` 只有 12 条、`draft eval` 仍未升格、`finetune` 仍是 0 valid、`RAG` 仍停留在原型阶段。

如果只用一句话概括：

> **当前的问题重点，已经不是“FQN 是不是编的”，而是“不要把 FQN 可溯源性误写成实验可用性”。**
