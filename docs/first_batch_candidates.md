# First Batch Candidates

## 目标

本文件给出第一批优先处理的样本候选，供人工标注时直接开工。这里的候选是“高价值入口”，不是已经完成复核的正式评测样本。

## 第一批建议数量

- 先做 12 条
- 其中 `easy` 4 条、`medium` 4 条、`hard` 4 条
- 完成后再扩到 50 条正式评测集

## 候选清单

| 编号 | 难度 | 类别 | 入口符号 / 文件 | 候选问题 | 价值 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C01 | easy | `re_export` | `celery.__init__` / `external/celery/celery/__init__.py` | `celery.Celery` 最终映射到哪个真实类？ | 顶层懒加载和再导出基础样本 |
| C02 | easy | `re_export` | `celery.__init__` / `external/celery/celery/__init__.py` | `celery.shared_task` 最终映射到哪个真实函数？ | 顶层 API 到真实入口 |
| C03 | easy | `loader_alias` | `celery.loaders.get_loader_cls` / `external/celery/celery/loaders/__init__.py` | `get_loader_cls('default')` 最终解析到哪个类？ | 字符串 alias 到类 |
| C04 | easy | `alias_resolution` | `celery.concurrency.get_implementation` / `external/celery/celery/concurrency/__init__.py` | `get_implementation('processes')` 最终返回哪个类？ | 兼容 alias 解析 |
| C05 | medium | `backend_alias` | `celery.app.backends.by_name` / `external/celery/celery/app/backends.py` | `by_name('redis')` 最终解析到哪个 backend 类？ | 典型映射链 |
| C06 | medium | `loader_alias` | `celery.loaders.get_loader_cls` / `external/celery/celery/loaders/__init__.py` | `get_loader_cls('app')` 最终解析到哪个类？ | 简洁但真实 |
| C07 | medium | `alias_resolution` | `celery.concurrency.get_implementation` / `external/celery/celery/concurrency/__init__.py` | `get_implementation('threads')` 最终指向哪个实现？ | 条件性 alias |
| C08 | medium | `name_generation` | `celery.app.base.Celery.gen_task_name` / `external/celery/celery/app/base.py` | `Celery.gen_task_name` 最终把命名委托给哪个函数？ | 中间跳板链 |
| C09 | hard | `shared_task_registration` | `celery.app.__init__.shared_task` / `external/celery/celery/app/__init__.py` | `@shared_task` 装饰后的函数最终经由哪个真实方法注册？ | 典型隐式依赖 |
| C10 | hard | `app_task_registration` | `celery.app.base.Celery.task` / `external/celery/celery/app/base.py` | `@app.task` 装饰流程最终落到哪个核心注册方法？ | 核心 Hard 样本 |
| C11 | hard | `finalize_callback` | `celery.app.builtins.add_backend_cleanup_task` / `external/celery/celery/app/builtins.py` | `celery.backend_cleanup` 这个内置任务通过哪条链被注册？ | finalize 回调链 |
| C12 | hard | `symbol_by_name_resolution` | `celery.worker.strategy.default` / `external/celery/celery/worker/strategy.py` | `task.Request` 最终如何解析为真实 Request 类？ | 属性 + 动态解析链 |

## 推荐执行顺序

1. 先标 `C01` 到 `C04`，把 FQN 和证据链格式跑顺。
2. 再标 `C05` 到 `C08`，把 alias / 委托 / 中间跳板类样本补起来。
3. 最后标 `C09` 到 `C12`，集中处理 Hard 样本。

## 标注完成标准

- 每条候选都要经过 [eval_case_annotation_template.md](eval_case_annotation_template.md) 里的模板检查
- 只有证据链写清楚之后，才允许写进正式 `eval_cases.json`
- 如果某条候选发现问题定义不够单一，应拆成两条样本，而不是强行塞进一条
