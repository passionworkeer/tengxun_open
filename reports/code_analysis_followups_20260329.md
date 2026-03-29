# 代码分析 Follow-up 实验报告（2026-03-29）

## 1. 实验边界

- 本轮工作**只新增独立实验文件**，不修改原有生产实现。
- 目标是验证三条后续方向是否值得进入正式方案：
  1. Type E 动态符号解析专项增强
  2. Type E / Type B 零分 bad case 定向增样
  3. 条件式 RAG 触发策略

对应实验代码：

- `experiments/dynamic_symbol_rag.py`
- `experiments/conditional_rag_model.py`
- `scripts/run_dynamic_typee_retrieval_experiment.py`
- `scripts/generate_targeted_badcase_finetune.py`
- `scripts/run_conditional_rag_model_experiment.py`

对应实验产物：

- `artifacts/experiments/typee_dynamic_symbol_rag_v2.json`
- `artifacts/experiments/badcase_targeted_finetune_typeeb_v2.jsonl`
- `artifacts/experiments/conditional_rag_policy_trainable.json`

## 2. 实验一：Type E 动态符号检索 v2

### 2.1 方案

第一版只靠 regex 提取 alias dict，覆盖面太窄。第二版升级为 AST 级动态绑定抽取，并加入有限深度 alias chaining。当前可识别的动态模式包括：

- alias table：如 `LOADER_ALIASES["default"] -> celery.loaders.default:Loader`
- 类属性/实例属性字符串：如 `Task.Request = "celery.worker.request:Request"`
- `symbol_by_name(...)` / `instantiate(...)` 字面量入口
- 少量高信号 keyword binding：如 `loader=...`、`task_cls=...`

同时做了两层降噪：

- 只分析 `celery/` 生产代码，不纳入测试文件和文档扩展代码。
- 对长 module path 不再盲目回退到尾 token，避免把完整路径问题误降成 alias 问题。

### 2.2 结果

评测集：`16` 条 Type E case。

| 指标 | Baseline | Dynamic v2 |
|---|---:|---:|
| Recall@5 | `0.4985` | `0.4985` |
| MRR | `0.6850` | `0.7350` |
| alias coverage | - | `0.7500` |
| regressed cases | - | `0` |
| mrr improved cases | - | `1` |

主要收益来自 `medium_001 / backend_alias`：

- 基线：`MRR = 0.2`
- 动态增强后：`MRR = 1.0`
- 关键命中：`'redis' -> celery.backends.redis.RedisBackend`

### 2.3 结论

- 这条线已经从“有提升但会退化”收敛到“**不退步，且排序质量提升**”。
- 当前收益主要体现在 `MRR`，不是 `Recall@5`。说明它更像一个**重排序增强器**，还不是独立的召回增强器。
- 现阶段最合理的定位是：作为 Type E 的附加排序源或 reranker feature，而不是直接替换主检索。

### 2.4 局限

- 对 `autodiscovery_fixup_import` 这类跨多跳隐式导入链，当前动态索引几乎没有额外收益。
- 对 `symbol_by_name_resolution_chain`，如果问题本身给的是完整 dotted path，过强的 alias 回退会引入噪声，因此现在已经被刻意收紧。

## 3. 实验二：Type E / Type B bad case 定向增样

### 3.1 方案

从 GPT baseline 的零分样本出发，筛出 `Type E` 和 `Type B` bad case，做纠错式增样，而不是泛化式扩容。

原始 bad case 数量：

- 零分总量：`24`
- 其中 Type E：`8`
- 其中 Type B：`5`

第二版增样不再只复制一份答案，而是给每条 case 生成 4 种训练风格：

- `cot_repair`：强调链式追踪
- `json_contract`：强调结构化收口
- `negative_guardrail`：强调不要把 helper / wrapper / registry 误报成 direct
- `evidence_first`：强调先给 runtime 证据再给结论

### 3.2 结果

最终生成：

- 总记录数：`52`
- Type E：`32`
- Type B：`20`

风格分布：

- `cot_repair = 13`
- `json_contract = 13`
- `negative_guardrail = 13`
- `evidence_first = 13`

### 3.3 结论

- 这批数据不是“大而全”训练集，而是**面向失效模式修补**的小型高密度补丁集。
- 如果后续做 LoRA/QLoRA，这 52 条可以直接作为二阶段纠错集，和原来的 500 条通用数据分开训练或做 curriculum。

## 4. 实验三：可训练条件式 RAG 触发器

### 4.1 方案

第一版是规则分类器，只能粗糙判断 implicit level。第二版换成一个轻量可训练的 ordinal 模型：

- 输入特征：question / entry_symbol / entry_file 的 token、短语、路径特征
- 目标：预测 `implicit_level`
- 训练方式：`6-fold cross validation`
- 触发规则：预测 `implicit_level >= 3` 时启用 RAG

### 4.2 结果

评测集：`54` 条完整 case。

分类指标：

- `exact_accuracy = 0.4444`
- `threshold_accuracy = 0.6852`

策略收益：

| 策略 | 平均 F1 |
|---|---:|
| No RAG | `0.2783` |
| Always RAG | `0.2940` |
| Conditional RAG（trainable） | `0.3292` |
| Oracle threshold reference | `0.3130` |

触发率：

- `rag_activation_rate = 0.6296`

按难度拆分：

- Easy：`0.3833`
- Medium：`0.2542`
- Hard：`0.3598`

### 4.3 观察

最典型的正收益来自“避免 Easy 被 RAG 噪声污染”：

- `easy_001`：`0.6667 -> 0.0` 的退化被成功规避
- `celery_easy_018`：`0.6667 -> 0.0` 的退化被成功规避

主要漏判仍然集中在高隐式 Type E / Type B：

- `medium_002`：漏掉 loader alias，损失 `+0.4`
- `hard_002`：漏掉 decorator registration，损失 `+0.2222`
- `medium_008`：漏掉 strategy string resolution，损失 `+0.2`
- `medium_001`：漏掉 backend alias，损失 `+0.2`

### 4.4 结论

- 这条线已经不是概念验证，而是**可以明确写进报告的有效策略**。
- 在当前数据上，训练式条件 RAG 已经优于 always-rag，说明“先判断隐式程度再决定是否检索”是对的。
- 下一步不是再堆规则，而是继续强化对 `Type E / Type B` 的判别特征。

## 5. 综合判断

三条 follow-up 的成熟度不同：

1. **条件式 RAG**：最成熟，已经有端到端收益，可优先纳入主方案。
2. **Type E 动态索引**：方向成立，但当前更适合作为 reranking enhancement，不适合作为主召回器。
3. **bad-case 定向增样**：数据已经可用，但是否真正提升模型还要靠下一轮 LoRA 验证。

如果只允许优先推进一条，我建议先推**条件式 RAG**。原因很简单：它已经直接带来了总体 F1 提升，而且对 Easy 负收益的治理最明显。

## 6. 推荐下一步

1. 把条件式 RAG 触发器并入正式消融矩阵，增加一列 `Conditional RAG`。
2. 用这 52 条专项样本做一次小步 LoRA，对比 `baseline FT` 与 `baseline FT + badcase patch set`。
3. 把 Type E 动态索引改成“只影响排序分数、不改原始召回集合”的 reranker 模式，再做一轮对比。

## 7. 复现命令

```bash
python3 scripts/run_dynamic_typee_retrieval_experiment.py
python3 scripts/generate_targeted_badcase_finetune.py
python3 scripts/run_conditional_rag_model_experiment.py
```
