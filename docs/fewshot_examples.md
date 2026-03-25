# Few-shot Examples Pool

## 文档目标

本文件给出 20 条高质量 few-shot 示例的候选清单，按失效类型配比，用于 Prompt Engineering 优化。

当前正式文档中的答案统一采用与新版评测 schema 兼容的结构：

```json
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

## 配比原则

- 按失效类型配比，不允许偏向 Easy
- 优先覆盖从 Day 2 bad case 中识别的高频失效模式
- 每条示例必须包含完整的推理过程

## 按失效类型配比

| 覆盖类型 | 数量 | 重点内容 |
|---------|------|---------|
| Type B 装饰器 | 5 条 | `@app.task`、`@shared_task`、`connect_on_app_finalize` |
| Type C 再导出 | 5 条 | `__init__.py` 多层转发、别名 |
| Type D 命名空间 | 4 条 | 同名函数、局部覆盖 |
| Type E 动态加载 | 4 条 | `symbol_by_name`、`importlib.import_module`、配置字符串 |
| Type A 长上下文 | 2 条 | 超长链路的截断补偿策略 |

---

## Type B 装饰器（5 条）

### Few-shot B01: @shared_task 装饰器注册

**问题**: 给定 `@shared_task` 装饰后的函数，最终注册到哪个任务对象路径？

**推理过程**:
1. Step 1: 定位 `shared_task` 在 `celery/app/__init__.py`
2. Step 2: 发现 `shared_task` 返回一个 `_create_shared_task` 调用
3. Step 3: 追踪 `_create_shared_task`，它使用 `connect_on_app_finalize` 延迟注册
4. Step 4: 在 app finalized 时，调用 `Celery._task_from_fun` 完成注册

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery._task_from_fun"],
    "indirect_deps": ["celery.app.task.create_task_cls"],
    "implicit_deps": ["celery.app.builtins.add_backend_cleanup_task"]
  }
}
```

### Few-shot B02: pending 队列在 finalize 时如何兑现

**问题**: 当 `@app.task(shared=True, lazy=True)` 装饰函数且 app 尚未 finalized 时，`self._pending` 里的代理对象在 finalize 阶段通过哪个关键链路被兑现为真实任务？

**环境前置条件**: 无

**推理过程**:
1. `Celery.task` 在 `lazy=True` 且未 finalized 分支中返回 `PromiseProxy(self._task_from_fun, ...)` 并压入 `self._pending`。
2. `shared=True` 分支同时通过 `connect_on_app_finalize(cons)` 注册 finalize callback，其中 `cons(app)` 也会调用 `app._task_from_fun(...)`。
3. `Celery.finalize` 先触发 `_announce_app_finalized(self)`，执行 finalize callbacks。
4. 随后 `finalize` 进入 `while pending: maybe_evaluate(pending.popleft())`，把 `PromiseProxy` 兑现为真实调用。
5. 两条路径最终都汇聚到 `Celery._task_from_fun` 完成任务实例创建/注册。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.local.maybe_evaluate",
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.finalize",
      "celery.local.PromiseProxy",
      "celery._state.connect_on_app_finalize"
    ],
    "implicit_deps": [
      "celery._state._announce_app_finalized"
    ]
  }
}
```

### Few-shot B03: 导入即注册 finalize 回调

**问题**: 为什么 `celery.app.builtins` 里的 `add_map_task` 等函数在没有被显式调用时，仍能在 app finalize 阶段执行？它们在导入阶段是通过哪个注册入口接入全局回调集合的？

**环境前置条件**:
1. `celery.app.base` 被导入。
2. 关注的是导入阶段的注册行为，而不是 finalize 后的任务实例化。

**推理过程**:
1. `celery.app.base` 模块导入时会执行 `from . import backends, builtins`，从而触发 `celery.app.builtins` 顶层代码。
2. `builtins.py` 中多个函数（如 `add_map_task`）带有 `@connect_on_app_finalize` 装饰器。
3. 该装饰器来自 `celery._state.connect_on_app_finalize`，其行为是把 callback 加入 `_on_app_finalizers` 集合并返回 callback 本身。
4. 因为注册发生在模块导入阶段，这些函数不需要业务代码显式调用。
5. 后续 app finalize 时，它们会从全局回调集合中被统一取出执行。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery._state.connect_on_app_finalize"
    ],
    "indirect_deps": [
      "celery.app.builtins.add_map_task",
      "celery.app.builtins.add_backend_cleanup_task"
    ],
    "implicit_deps": [
      "celery._state._on_app_finalizers",
      "celery.app.base"
    ]
  }
}
```

### Few-shot B04: `shared_task` Proxy 首次解引用触发 auto-finalize

**问题**: `@shared_task` 返回的 Proxy 在首次解引用时，哪个 app 级入口会被访问并触发 `auto-finalize`，从而让后续查表可用？

**环境前置条件**:
1. 使用 `@shared_task` 且未显式传 `name`。
2. 首次访问该任务 Proxy 时，当前 app 仍可能未 finalized。

**推理过程**:
1. `shared_task` 返回 `Proxy(task_by_cons)`，真正求值时才执行 `task_by_cons()`。
2. `task_by_cons()` 先取当前 app，再构造 key：`name or app.gen_task_name(fun.__name__, fun.__module__)`。
3. 接着它访问 `app.tasks[key]`；关键点是 `app.tasks` 是 `Celery.tasks` 的 `cached_property`。
4. `Celery.tasks` 属性内部会调用 `self.finalize(auto=True)`，这是首次解引用时触发 finalize 的稳定入口。
5. finalize 完成后任务注册表稳定，`app.tasks[key]` 才能可靠返回任务对象。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.tasks"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.finalize",
      "celery.app.base.Celery.gen_task_name",
      "celery.utils.imports.gen_task_name"
    ],
    "implicit_deps": [
      "celery.app.shared_task"
    ]
  }
}
```

### Few-shot B05: （待补充）

---

## Type C 再导出（5 条）

### Few-shot C01: celery.Celery 再导出

**问题**: `celery.Celery` 最终映射到哪个真实类？

**推理过程**:
1. Step 1: 定位 `celery/__init__.py`
2. Step 2: 发现 `Celery` 通过 `recreate_module` 懒加载
3. Step 3: 追踪到 `celery.app.Celery`
4. Step 4: 最终实现在 `celery.app.base.Celery`

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery"],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

### Few-shot C02: bugreport 多跳再导出

**问题**: 调用顶层 `celery.bugreport()`（不传 app）时，最终生成报告字符串的真实函数是哪一个？

**环境前置条件**: 无

**推理过程**:
1. `celery/__init__.py` 通过 `recreate_module` 把顶层 `bugreport` 再导出到 `celery.app.bugreport`。
2. `celery.app.bugreport(app=None)` 内部会走 `(app or _state.get_current_app()).bugreport()`。
3. `Celery.bugreport` 再调用 `bugreport(self)`。
4. 这里的 `bugreport` 来自 `celery.app.utils`，实际字符串拼装逻辑在 `celery.app.utils.bugreport`。
5. 因为题设不传 app，链路里包含一次隐式 `current_app` 解析。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.utils.bugreport"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.bugreport",
      "celery.app.bugreport"
    ],
    "implicit_deps": [
      "celery._state.get_current_app"
    ]
  }
}
```

### Few-shot C03: `subtask -> signature` 兼容别名链

**问题**: 顶层 `celery.subtask` 最终映射到哪个真实可调用入口？

**环境前置条件**: 无

**推理过程**:
1. `celery/__init__.py` 的 `recreate_module` 将顶层 `subtask` 再导出自 `celery.canvas`。
2. `celery.canvas` 内并没有独立实现 `def subtask`，而是兼容别名：`subtask = signature`。
3. 因此顶层 `celery.subtask` 实际指向 `celery.canvas.signature`。
4. `signature(...)` 再根据输入类型构造或规范化 `Signature` 对象。
5. 这是一条“顶层再导出 + 模块内别名”的两段链，而不是单层映射。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.canvas.signature"
    ],
    "indirect_deps": [
      "celery.canvas.subtask",
      "celery.canvas.Signature"
    ],
    "implicit_deps": []
  }
}
```

### Few-shot C04-C05: （待补充）

---

## Type D 命名空间（4 条）

### Few-shot D01-D04: （待从 bad case 中补充）

---

## Type E 动态加载（4 条）

### Few-shot E01: symbol_by_name 动态解析

**问题**: `symbol_by_name('celery.app.trace.build_tracer')` 最终返回什么？

**推理过程**:
1. Step 1: 定位 `symbol_by_name` 在 `celery/utils/imports.py`
2. Step 2: 发现它使用 `importlib.import_module` 动态加载模块
3. Step 3: 然后使用 `getattr` 获取符号
4. Step 4: 最终返回 `celery.app.trace.build_tracer` 函数

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": ["celery.app.trace.build_tracer"],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

### Few-shot E02: Django fixup 字符串入口解析与执行

**问题**: 在满足 Django 前置条件时，`BUILTIN_FIXUPS` 中的字符串 `'celery.fixups.django:fixup'` 如何被解析并执行，最终返回什么对象？

**环境前置条件**:
1. `DJANGO_SETTINGS_MODULE` 已设置。
2. 运行环境可导入 `django` 且版本满足要求。
3. `app.loader_cls.lower()` 不包含 `django`。

**推理过程**:
1. `Celery` 初始化时默认 `self.fixups` 含有 `'celery.fixups.django:fixup'`。
2. `Celery.__init__` 执行：`self._fixups = [symbol_by_name(fixup)(self) for fixup in self.fixups]`。
3. 这里的 `symbol_by_name` 来自 `celery.utils.imports`，把字符串解析为 `celery.fixups.django.fixup`。
4. 解析后立即执行 `fixup(self)`；在前置条件成立时，函数返回 `DjangoFixup(app).install()`。
5. 若前置条件不成立，该分支可能返回 `None`，因此题目必须显式带条件。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.fixups.django.fixup",
      "celery.fixups.django.DjangoFixup.install"
    ],
    "indirect_deps": [
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": []
  }
}
```

### Few-shot E03: （重写中，暂不入正式池）

### Few-shot E04: 导入时注入 alias 的时序依赖

**问题**: 满足环境变量与导入时机前置后，`get_implementation('custom')` 最终解析到哪个类？

**环境前置条件**:
1. 在首次导入 `celery.concurrency` 之前设置：`CELERY_CUSTOM_WORKER_POOL='celery.concurrency.thread:TaskPool'`。
2. 若在导入之后才设置该变量，需要 reload 模块，否则 `ALIASES['custom']` 不会自动更新。

**推理过程**:
1. `celery.concurrency.__init__` 在模块导入阶段读取 `os.environ.get('CELERY_CUSTOM_WORKER_POOL')`。
2. 若读到值，则在导入时执行 `ALIASES['custom'] = custom`。
3. `get_implementation('custom')` 调用 `symbol_by_name(cls, ALIASES)`。
4. `symbol_by_name` 先从 `ALIASES` 取字符串 `'celery.concurrency.thread:TaskPool'`，再导入并取符号。
5. 返回真实类 `celery.concurrency.thread.TaskPool`。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.concurrency.thread.TaskPool"
    ],
    "indirect_deps": [
      "celery.concurrency.get_implementation",
      "kombu.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.concurrency.ALIASES"
    ]
  }
}
```

---

## Type A 长上下文（2 条）

### Few-shot A01-A02: （待从 bad case 中补充）

---

## 使用说明

1. 这些 few-shot 示例应该写入 `pe/prompt_templates_v2.py`
2. 每条示例必须包含完整的推理过程（CoT 风格）
3. 优先从 Day 2 的 bad case 中提取真实案例
4. 保持 20 条的配比，不要偏向 Easy 样本

## 后续工作

- [ ] 从 bad case 中补充完整的 20 条示例（当前已稳定回填 8 条）
- [ ] 每条示例验证在 Celery 源码中可复现
- [ ] 写入 `pe/prompt_templates_v2.py`
- [ ] 创建 `data/fewshot_examples_20.json` 文件
