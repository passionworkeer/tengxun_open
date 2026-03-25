# Candidate Dispatch Prompts

## 文档目标

本文件把首批样本 `C01-C12` 全部写成可直接复制给 AI 的 prompt。适合你不想再手动组织输入时直接使用。

使用建议：

1. 一次只发一条，不要把多个样本混在同一个 prompt 里。
2. AI 返回草稿后，必须用 [eval_case_annotation_template.md](eval_case_annotation_template.md) 做人工复核。
3. 只有复核通过后，才允许写入正式 `data/eval_cases.json`。

---

## C01

```text
你现在负责执行任务包 EVAL-002-C01。

目标：
为首批评测集起草 1 条 easy 样本，问题是“celery.Celery 最终映射到哪个真实类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/first_batch_candidates.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/__init__.py
- external/celery/celery/app/__init__.py
- external/celery/celery/app/base.py

你的输出必须包含：
1. 这条样本的 JSON 草稿
2. 对应的证据链，按 step 1 / step 2 / step 3 写清楚
3. 你认为这条样本的风险点

要求：
- 最终答案必须是完整 FQN
- 不要只停留在顶层导出
- 如果发现有多个合理答案，明确说明并解释原因
- 先给草稿，不要直接改正式数据文件
```

## C02

```text
你现在负责执行任务包 EVAL-002-C02。

目标：
为首批评测集起草 1 条 easy 样本，问题是“celery.shared_task 最终映射到哪个真实函数”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/first_batch_candidates.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/__init__.py
- external/celery/celery/app/__init__.py

你的输出必须包含：
1. 这条样本的 JSON 草稿
2. step-by-step 证据链
3. 可能引起误判的位置

要求：
- 不要只写顶层符号名
- 要追到真实定义函数
- 如果证据不足，明确说明不确定
```

## C03

```text
你现在负责执行任务包 EVAL-002-C03。

目标：
为首批评测集起草 1 条 easy 样本，问题是“get_loader_cls('default') 最终解析到哪个类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/loaders/__init__.py
- external/celery/celery/loaders/default.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 为什么这条样本属于 easy

要求：
- 必须说明 alias 是怎么解析的
- 最终答案必须是类的 FQN
```

## C04

```text
你现在负责执行任务包 EVAL-002-C04。

目标：
为首批评测集起草 1 条 easy 样本，问题是“get_implementation('processes') 最终返回哪个类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/concurrency/__init__.py
- external/celery/celery/concurrency/prefork.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 可能的误判点

要求：
- 必须指出 `processes` 是 alias，不是最终实现
- 不要跳过 `symbol_by_name`
```

## C05

```text
你现在负责执行任务包 EVAL-003-C05。

目标：
为首批评测集起草 1 条 medium 样本，问题是“by_name('redis') 最终解析到哪个 backend 类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/app/backends.py
- external/celery/celery/backends/redis.py

你的输出必须包含：
1. 样本 JSON 草稿
2. step-by-step 证据链
3. 为什么这条样本属于 medium

要求：
- 要说明 alias 合并逻辑
- 最终答案必须是 backend 类的 FQN
- 不要忽略 override 机制带来的推理风险
```

## C06

```text
你现在负责执行任务包 EVAL-003-C06。

目标：
为首批评测集起草 1 条 medium 样本，问题是“get_loader_cls('app') 最终解析到哪个类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/loaders/__init__.py
- external/celery/celery/loaders/app.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 可能的误判点

要求：
- 不要只给文件路径
- 最终必须给完整类 FQN
```

## C07

```text
你现在负责执行任务包 EVAL-003-C07。

目标：
为首批评测集起草 1 条 medium 样本，问题是“get_implementation('threads') 最终指向哪个实现”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/concurrency/__init__.py
- external/celery/celery/concurrency/thread.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 为什么这条样本不是 easy

要求：
- 要说明 `threads` alias 的条件来源
- 不能忽略条件分支
```

## C08

```text
你现在负责执行任务包 EVAL-003-C08。

目标：
为首批评测集起草 1 条 medium 样本，问题是“Celery.gen_task_name 最终把命名委托给哪个函数”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md

请重点查看这些源码文件：
- external/celery/celery/app/base.py
- external/celery/celery/utils/imports.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 为什么这是中间跳板链样本

要求：
- 不要把实例方法本身当作最终答案
- 要追踪委托目标
```

## C09

```text
你现在负责执行任务包 EVAL-004-C09。

目标：
为首批评测集起草 1 条 hard 样本，问题是“@shared_task 装饰后的函数最终经由哪个真实方法注册”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md
- plan.md

请重点查看这些源码文件：
- external/celery/celery/app/__init__.py
- external/celery/celery/_state.py
- external/celery/celery/app/base.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 至少 3 步证据链
3. 这条样本为什么属于 hard
4. 需要人工重点复核的地方

要求：
- 不要停在 shared_task 表层
- 要追到 connect_on_app_finalize 和 _task_from_fun
- 不确定时明确说不确定，不要猜
```

## C10

```text
你现在负责执行任务包 EVAL-004-C10。

目标：
为首批评测集起草 1 条 hard 样本，问题是“@app.task 装饰流程最终落到哪个核心注册方法”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md
- plan.md

请重点查看这些源码文件：
- external/celery/celery/app/base.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 至少 3 步证据链
3. lazy / 非 lazy / shared 分支的说明
4. 风险点

要求：
- 必须指出核心注册方法
- 不要只说“它变成了 task”
- 如果有多个分支路径，要明确哪条是主链
```

## C11

```text
你现在负责执行任务包 EVAL-004-C11。

目标：
为首批评测集起草 1 条 hard 样本，问题是“celery.backend_cleanup 这个内置任务通过哪条链被注册”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md
- plan.md

请重点查看这些源码文件：
- external/celery/celery/app/builtins.py
- external/celery/celery/_state.py
- external/celery/celery/app/base.py

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 为什么这是 finalize callback 类型的 hard 样本
4. 需要人工复核的点

要求：
- 不要只记录内部函数 backend_cleanup
- 要把注册链写清楚
- 必须指出任务名 `celery.backend_cleanup`
```

## C12

```text
你现在负责执行任务包 EVAL-004-C12。

目标：
为首批评测集起草 1 条 hard 样本，问题是“task.Request 最终如何解析为真实 Request 类”。

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/candidate_task_packets.md
- plan.md

请重点查看这些源码文件：
- external/celery/celery/worker/strategy.py
- external/celery/celery/utils/imports.py
- 与该样本相关的 task 定义位置

你的输出必须包含：
1. 样本 JSON 草稿
2. 证据链
3. 属性 -> 解析函数 -> 真实类 的链路解释
4. 哪个环节最容易出现幻觉

要求：
- 不要停在字符串属性 `task.Request`
- 要继续追到真实类路径
- 如果当前上下文不足以唯一确定类，必须明确标注不确定
```
