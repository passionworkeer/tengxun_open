# GPT-5.4 失败案例瓶颈分析报告

## 核心数据：瓶颈热力图

| Failure Type | Count | Percentage | Description |
|-------------|-------|------------|-------------|
| **Type E** | 8 | 42% | 动态符号解析 (symbol_by_name/string resolution) |
| **Type B** | 5 | 26% | 信号回调链 (signal/callback chains) |
| **Type C** | 3 | 16% | Re-export/名称生成 |
| **Type A** | 2 | 11% | Bootstep生命周期 |
| **Type D** | 1 | 5% | 命名空间混淆 |

---

## 瓶颈分析

### Type E (8 cases) - 最严重瓶颈
**问题本质**: 模型无法正确追踪 `symbol_by_name` 动态解析路径

| Case ID | Difficulty | Category | Ground Truth | Prediction |
|---------|------------|----------|--------------|------------|
| hard_004 | hard | symbol_by_name_resolution | celery.worker.request.Request | celery.worker.request:Request (wrong format) |
| medium_008 | medium | strategy_string_resolution | celery.worker.strategy.default | celery/app/task.py: Task.start_strategy (wrong FQN) |
| medium_007 | medium | fallback_loader_alias | celery.loaders.default.Loader | celery/_state.py (file only, no class) |
| celery_hard_018 | hard | django_task_cls_string_resolution | celery.contrib.django.task.DjangoTask | celery/fixups/django.py (file only) |
| celery_medium_020 | medium | default_app_loader_alias_chain | celery.app.base.Celery.loader | celery/_state.py (file only) |
| easy_012 | easy | alias_resolution | celery.concurrency.eventlet.TaskPool | celery.concurrency.eventlet:TaskPool (wrong separator) |
| easy_013 | easy | alias_resolution | celery.concurrency.solo.TaskPool | celery.concurrency.solo:TaskPool (wrong separator) |
| medium_021 | medium | dynamic_loading | celery.utils.imports.symbol_by_name | celery/app/base.py (wrong location) |

**根本原因**: GPT-5.4 输出的是文件路径或使用了错误的 `:` 分隔符，而非正确的 `.` 分隔的完全限定类名

---

### Type B (5 cases) - 第二大瓶颈
**问题本质**: 信号/回调链追踪失败，返回了过多的中间层而非真正执行的目标

| Case ID | Difficulty | Category | Ground Truth | Prediction |
|---------|------------|----------|--------------|------------|
| hard_003 | hard | finalize_callback | celery._state._announce_app_finalized | connect_on_app_finalize (missing prefix) |
| easy_006 | easy | re_export_proxy | celery._state.get_current_task | celery.__init__.current_task -> ... (chained) |
| celery_hard_015 | hard | autodiscovery_signal_chain | celery.app.base.Celery._autodiscover_tasks | 4个方法的复杂链 (over-complex) |
| medium_012 | medium | decorator_registration | celery.app.base.Celery._task_from_fun | null (解析失败) |
| medium_014 | medium | builtin_registration | celery._state.connect_on_app_finalize | _acquire_tasks (完全错误) |

---

### Type C (3 cases) - Re-export追踪
**问题本质**: 无法追踪 `__getattr__` 懒加载导出链

| Case ID | Difficulty | Category | Issue |
|---------|------------|----------|-------|
| easy_002 | easy | re_export | 返回了 `celery.__init__.shared_task` 而非 `celery.app.shared_task` |
| medium_004 | medium | name_generation | 返回 `gen_task_name` 而非 `celery.utils.imports.gen_task_name` |
| medium_018 | medium | re_export_chain | 完全追踪错了链 |

---

### Type A (2 cases) - Bootstep生命周期
**问题本质**: Blueprint.apply 调用顺序中的条件分支

| Case ID | Difficulty | Category | Issue |
|---------|------------|----------|-------|
| celery_hard_122 | hard | bootstep_lifecycle | 返回了错误的断点方法 |
| celery_hard_024 | hard | persistent_scheduler | setup_schedule vs _create_schedule 混淆 |

---

### Type D (1 case) - 命名空间混淆
**问题本质**: Python 模块 vs 对象导出混淆

| Case ID | Difficulty | Category | Issue |
|---------|------------|----------|-------|
| medium_020 | medium | namespace_confusion | `celery.canvas.subtask` 和 `celery.canvas.signature` 是同一对象，但模型混淆了 |

---

## GPT-5.4 错误模式总结

### 1. FQN 格式错误 (Type E)
- 使用 `:` 分隔符而非 `.` (easy_012, easy_013)
- 只输出文件路径而非类名 (medium_007, celery_hard_018)
- 缺少完整模块前缀 (medium_004)

### 2. 过度复杂化 (Type B)
- 返回完整的调用链而非最终目标函数
- 混淆"触发机制"和"实际执行函数"

### 3. 懒加载导出 (Type C)
- 无法追踪 `__getattr__` 懒加载路径
- 混淆模块级代理对象和实际函数

### 4. Null 输出 (Type B)
- medium_012 直接返回 null
- 说明模型无法解析某些模式

---

## 原始完整输出记录

### Case 1: easy_002 (Type C)
```
Question: Which real function does the top-level `celery.shared_task` symbol resolve to?
Ground Truth: celery.app.shared_task
Prediction: celery.__init__.shared_task, celery.local.recreate_module (错)
Raw: {"direct_deps":["celery.__init__.shared_task","celery.local.recreate_module"],...}
```

### Case 2: medium_004 (Type C)
```
Question: Which helper function does `Celery.gen_task_name` delegate to?
Ground Truth: celery.utils.imports.gen_task_name
Prediction: gen_task_name (缺少模块前缀)
```

### Case 3: hard_003 (Type B)
```
Question: Which function is responsible for firing all shared-task and built-in finalize callbacks?
Ground Truth: celery._state._announce_app_finalized
Prediction: connect_on_app_finalize (缺少 celery._state 前缀)
```

### Case 4: hard_004 (Type E)
```
Question: In `celery.worker.strategy.default`, what real class does `task.Request` resolve to?
Ground Truth: celery.worker.request.Request
Prediction: celery.worker.request:Request (错误分隔符)
```

### Case 5: medium_008 (Type E)
```
Question: `Task.start_strategy` 调用时，`Task.Strategy` 字符串最终会被解析为哪个可调用对象？
Ground Truth: celery.worker.strategy.default
Prediction: celery/app/task.py: Task.start_strategy (错误的文件路径格式)
```

### Case 6: easy_006 (Type B)
```
Question: 在顶层懒加载 API 中，`celery.current_task` 在取值时直接调用哪个函数...
Ground Truth: celery._state.get_current_task
Prediction: celery.__init__.current_task -> celery._state.get_current_task (过度复杂化)
```

### Case 7: medium_007 (Type E)
```
Question: 当线程中没有 current app...最终会实例化哪个 Loader 类？
Ground Truth: celery.loaders.default.Loader
Prediction: celery/_state.py, celery/app/base.py... (只返回了文件列表)
```

### Case 8: celery_hard_015 (Type B)
```
Question: 在 `app.autodiscover_tasks(..., force=False)` 的 lazy 路径下...
Ground Truth: celery.app.base.Celery._autodiscover_tasks
Prediction: 返回了4个方法的复杂链 (过度复杂)
```

### Case 9: celery_hard_018 (Type E)
```
Question: 在满足 Django fixup 前置条件...`app.Task` 的最终基类解析到哪个真实类？
Ground Truth: celery.contrib.django.task.DjangoTask
Prediction: celery/fixups/django.py (文件路径而非类)
```

### Case 10: celery_medium_020 (Type E)
```
Question: `_state._get_current_app` 懒创建 fallback app 后...
Ground Truth: celery.app.base.Celery.loader, celery.loaders.default.Loader
Prediction: celery/_state.py... (文件列表)
```

### Case 11: celery_hard_122 (Type A)
```
Question: 当某个 `StartStopStep.include_if()` 最终为 `False` 时...
Ground Truth: celery.bootsteps.Blueprint.apply
Prediction: celery/bootsteps.py:Blueprint.apply (正确格式但位置错误)
```

### Case 12: celery_hard_024 (Type A)
```
Question: `PersistentScheduler` 启动阶段若持久化 store 缺失 `utc_enabled` 元数据字段...
Ground Truth: celery.beat.PersistentScheduler._create_schedule
Prediction: PersistentScheduler.setup_schedule (错误的方法)
```

### Case 13: easy_012 (Type E)
```
Question: In `celery.concurrency.get_implementation`, what does `get_implementation('eventlet')` resolve to?
Ground Truth: celery.concurrency.eventlet.TaskPool
Prediction: celery.concurrency.eventlet:TaskPool (错误分隔符)
```

### Case 14: easy_013 (Type E)
```
Question: In `celery.concurrency.get_implementation`, what does `get_implementation('solo')` resolve to?
Ground Truth: celery.concurrency.solo.TaskPool
Prediction: celery.concurrency.solo:TaskPool (错误分隔符)
```

### Case 15: medium_012 (Type B)
```
Question: When `@shared_task` decorates a function...
Ground Truth: celery.app.base.Celery._task_from_fun
Prediction: null (解析完全失败)
```

### Case 16: medium_014 (Type B)
```
Question: What function implements the `celery.accumulate` built-in task...
Ground Truth: celery._state.connect_on_app_finalize
Prediction: _acquire_tasks, app.task, sum (完全错误)
```

### Case 17: medium_018 (Type C)
```
Question: What is the full dependency chain when calling `celery.app.disable_trace()`?
Ground Truth: celery._state.disable_trace
Prediction: celery.app.trace.setup_worker_optimizations... (完全错误)
```

### Case 18: medium_020 (Type D)
```
Question: In `celery` top-level module, `subtask` is exported. In `celery.canvas`, `subtask` is also defined...
Ground Truth: celery.canvas.signature (same object)
Prediction: celery/canvas.py: subtask = signature (混淆了)
```

### Case 19: medium_021 (Type E)
```
Question: When Celery app is initialized, how does it resolve the fixup classes...
Ground Truth: celery.utils.imports.symbol_by_name
Prediction: celery/app/base.py (错误位置)