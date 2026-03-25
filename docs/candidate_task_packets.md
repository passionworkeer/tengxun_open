# Candidate Task Packets

## 文档目标

本文件把首批候选样本 `C01-C12` 进一步拆成可直接发给 AI 的逐条任务包。适合你想把首批评测样本拆到最细时使用。

推荐使用方式：

1. 先看 [first_batch_candidates.md](first_batch_candidates.md) 确认候选范围。
2. 再从本文件复制对应任务包发给 AI。
3. AI 产出后，使用 [eval_case_annotation_template.md](eval_case_annotation_template.md) 做人工复核。

## 字段说明

- `Packet ID`：任务包 ID
- `对应 Task`：映射到哪一个阶段任务
- `要解决的问题`：这一条样本到底在问什么
- `必须读取`：AI 必须先看哪些源码
- `预期答案类型`：通常是一个或多个 FQN
- `证据检查点`：至少要覆盖的推理步骤
- `常见误判`：这条样本最容易错在哪里

---

## Easy 批次

### Packet C01

- `Packet ID`：`EVAL-002-C01`
- `对应 Task`：`EVAL-002`
- `要解决的问题`：`celery.Celery` 最终映射到哪个真实类
- `必须读取`：
  - `external/celery/celery/__init__.py`
  - `external/celery/celery/app/__init__.py`
  - `external/celery/celery/app/base.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - 顶层 `celery.__init__` 是否通过 `recreate_module` 暴露 `Celery`
  - `Celery` 是否来自 `celery.app`
  - `celery.app` 中的 `Celery` 是否来自 `.base`
- `常见误判`：
  - 把 `celery.app.Celery` 当成最终实现，而不继续追到 `celery.app.base.Celery`

### Packet C02

- `Packet ID`：`EVAL-002-C02`
- `对应 Task`：`EVAL-002`
- `要解决的问题`：`celery.shared_task` 最终映射到哪个真实函数
- `必须读取`：
  - `external/celery/celery/__init__.py`
  - `external/celery/celery/app/__init__.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - 顶层暴露是否来自 `celery.app`
  - `shared_task` 的真实定义位置
- `常见误判`：
  - 只写顶层导出名，不写真实定义函数

### Packet C03

- `Packet ID`：`EVAL-002-C03`
- `对应 Task`：`EVAL-002`
- `要解决的问题`：`get_loader_cls('default')` 最终解析到哪个类
- `必须读取`：
  - `external/celery/celery/loaders/__init__.py`
  - `external/celery/celery/loaders/default.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - `LOADER_ALIASES` 中 `default` 的映射
  - `get_loader_cls` 是否通过 `symbol_by_name` 做解析
- `常见误判`：
  - 只写 alias 字符串，不写类

### Packet C04

- `Packet ID`：`EVAL-002-C04`
- `对应 Task`：`EVAL-002`
- `要解决的问题`：`get_implementation('processes')` 最终返回哪个类
- `必须读取`：
  - `external/celery/celery/concurrency/__init__.py`
  - `external/celery/celery/concurrency/prefork.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - `ALIASES['processes']` 的映射
  - `get_implementation` 是否直接调用 `symbol_by_name`
- `常见误判`：
  - 把 alias 名 `processes` 错写成最终类名

## Medium 批次

### Packet C05

- `Packet ID`：`EVAL-003-C05`
- `对应 Task`：`EVAL-003`
- `要解决的问题`：`by_name('redis')` 最终解析到哪个 backend 类
- `必须读取`：
  - `external/celery/celery/app/backends.py`
  - `external/celery/celery/backends/redis.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - `BACKEND_ALIASES['redis']`
  - `by_name` 的 alias 合并逻辑
- `常见误判`：
  - 忽略 `loader.override_backends` 的存在，导致推理不完整

### Packet C06

- `Packet ID`：`EVAL-003-C06`
- `对应 Task`：`EVAL-003`
- `要解决的问题`：`get_loader_cls('app')` 最终解析到哪个类
- `必须读取`：
  - `external/celery/celery/loaders/__init__.py`
  - `external/celery/celery/loaders/app.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - alias `app` 的映射
  - 类名是否来自 `AppLoader`
- `常见误判`：
  - 只看到文件路径，不写出完整 FQN

### Packet C07

- `Packet ID`：`EVAL-003-C07`
- `对应 Task`：`EVAL-003`
- `要解决的问题`：`get_implementation('threads')` 最终指向哪个实现
- `必须读取`：
  - `external/celery/celery/concurrency/__init__.py`
  - `external/celery/celery/concurrency/thread.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - `threads` alias 是在什么条件下插入的
  - 最终 `TaskPool` 位于哪个模块
- `常见误判`：
  - 忽略 `concurrent.futures` 条件分支

### Packet C08

- `Packet ID`：`EVAL-003-C08`
- `对应 Task`：`EVAL-003`
- `要解决的问题`：`Celery.gen_task_name` 最终把命名委托给哪个函数
- `必须读取`：
  - `external/celery/celery/app/base.py`
  - `external/celery/celery/utils/imports.py`
- `预期答案类型`：单个 FQN
- `证据检查点`：
  - `Celery.gen_task_name` 的方法体
  - `gen_task_name` 在 `celery.utils.imports` 中的定义
- `常见误判`：
  - 把实例方法名直接当作最终答案，不继续追踪委托目标

## Hard 批次

### Packet C09

- `Packet ID`：`EVAL-004-C09`
- `对应 Task`：`EVAL-004`
- `要解决的问题`：`@shared_task` 装饰后的函数最终经由哪个真实方法注册
- `必须读取`：
  - `external/celery/celery/app/__init__.py`
  - `external/celery/celery/_state.py`
  - `external/celery/celery/app/base.py`
- `预期答案类型`：单个或两个关键 FQN
- `证据检查点`：
  - `shared_task` 内部是否调用 `connect_on_app_finalize`
  - finalize 回调里是否触发 `app._task_from_fun`
  - finalized app 分支是否也调用 `_task_from_fun`
- `常见误判`：
  - 只写 `shared_task` 本身，不追到 `_task_from_fun`

### Packet C10

- `Packet ID`：`EVAL-004-C10`
- `对应 Task`：`EVAL-004`
- `要解决的问题`：`@app.task` 装饰流程最终落到哪个核心注册方法
- `必须读取`：
  - `external/celery/celery/app/base.py`
- `预期答案类型`：单个或两个关键 FQN
- `证据检查点`：
  - `Celery.task` 是如何区分 `lazy` / 非 `lazy`
  - 最终是否落到 `_task_from_fun`
  - 是否存在 `shared=True` 分支转发到 `shared_task`
- `常见误判`：
  - 只说“被装饰为 task”，但不指出核心注册方法

### Packet C11

- `Packet ID`：`EVAL-004-C11`
- `对应 Task`：`EVAL-004`
- `要解决的问题`：`celery.backend_cleanup` 这个内置任务通过哪条链被注册
- `必须读取`：
  - `external/celery/celery/app/builtins.py`
  - `external/celery/celery/_state.py`
  - `external/celery/celery/app/base.py`
- `预期答案类型`：注册链上的关键 FQN 组合
- `证据检查点`：
  - `add_backend_cleanup_task` 是否被 `@connect_on_app_finalize` 包装
  - finalize 时回调是否返回一个 `@app.task(...)` 生成的任务
  - 内部任务名是否固定为 `celery.backend_cleanup`
- `常见误判`：
  - 只记录内部函数 `backend_cleanup`，不写注册链

### Packet C12

- `Packet ID`：`EVAL-004-C12`
- `对应 Task`：`EVAL-004`
- `要解决的问题`：`task.Request` 最终如何解析为真实 Request 类
- `必须读取`：
  - `external/celery/celery/worker/strategy.py`
  - `external/celery/celery/utils/imports.py`
  - 与样本对应的 task 定义位置
- `预期答案类型`：单个 FQN 或“属性 -> 解析函数 -> 真实类”链
- `证据检查点`：
  - `symbol_by_name(task.Request)` 在什么地方执行
  - `task.Request` 的值来源于哪里
  - 最终真实类路径是什么
- `常见误判`：
  - 只停留在字符串属性层，不继续解析到真实类

---

## 建议派发方式

* **第一轮派发**
    * `EVAL-002-C01` 至 `EVAL-002-C04`
    * `EVAL-003-C05` 至 `EVAL-003-C08`
    * `EVAL-004-C09` 至 `EVAL-004-C12`
* **第二轮派发**
    * 对 AI 草稿做人工复核
    * 把通过复核的样本写入正式候选池
* **第三轮派发**
    * 让 AI 根据通过复核的样本风格继续扩展 Easy / Medium / Hard
