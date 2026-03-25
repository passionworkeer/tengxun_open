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
2. Step 2: 发现 `shared_task` 内部先通过 `connect_on_app_finalize(...)` 注册 finalize 回调
3. Step 3: 同时它会遍历 `_get_active_apps()`，让已 finalized 的 app 立刻执行同一注册动作
4. Step 4: 两条分支最终都落到 `app._task_from_fun(fun, **options)` 完成任务注册

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery._task_from_fun"],
    "indirect_deps": [
      "celery._state.connect_on_app_finalize",
      "celery._state._get_active_apps"
    ],
    "implicit_deps": ["celery.app.shared_task"]
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

### Few-shot B05: `@app.task` 在 execv 场景的首跳转发

**问题**：当进程处于 execv 兼容场景（`FORKED_BY_MULTIPROCESSING` 为真）且 `@app.task` 未显式关闭 lazy 时，装饰器流程会先转发到哪个入口，而不是直接走当前 app 的 `_task_from_fun`？

**环境前置条件**：
1. `FORKED_BY_MULTIPROCESSING` 对应的环境变量在导入 `celery.app.base` 之前已设置，使 `USING_EXECV` 为真。
2. 调用 `@app.task(...)` 时 `lazy` 未显式设为 `False`（保持默认可懒注册分支）。
3. 关注的是“首跳转发入口”，不是最终任务实例创建终点。

**推理过程**：
1. `celery.app.base` 在模块导入阶段就把 `USING_EXECV` 绑定为 `os.environ.get('FORKED_BY_MULTIPROCESSING')`。
2. `Celery.task` 开头先判断 `if USING_EXECV and opts.get('lazy', True): ...`。
3. 条件成立时，代码不会继续走当前 app 的 `inner_create_task_cls` 主分支。
4. 该分支显式 `from . import shared_task`，随后 `return shared_task(*args, lazy=False, **opts)`。
5. 因此 `@app.task` 在这个场景下的首跳入口是 `celery.app.shared_task`；后续 finalize / 注册逻辑已属于下一阶段链路。

**答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.shared_task"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.task"
    ],
    "implicit_deps": [
      "celery.app.base.USING_EXECV"
    ]
  }
}
```

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

### Few-shot C04: `celery.chord` 的再导出 + 兼容别名链

**问题**：顶层 `celery.chord` 最终落到 `celery.canvas` 中哪个真实类定义，而不是停在兼容别名符号名上？

**环境前置条件**：
1. 使用当前 Celery 源码快照（`b8f85213f45c937670a6a6806ce55326a0eb537f`）。
2. 按正常导入路径访问顶层 `celery.chord`。

**推理过程**：
1. `celery/__init__.py` 通过 `local.recreate_module` 把顶层 `chord` 懒导出到 `celery.canvas`。
2. 在 `celery.canvas` 中，公开名 `chord` 不是独立定义的新类，而是兼容别名赋值：`chord = _chord`。
3. 真正类定义位置是 `class _chord(Signature): ...`。
4. 因此顶层 `celery.chord` 的“真实定义落点”应追到 `celery.canvas._chord`，而不仅是别名名义上的 `celery.canvas.chord`。
5. 这类链路是“顶层再导出 + 模块内 back-compat alias”的两段式路径。

**答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.canvas._chord"
    ],
    "indirect_deps": [
      "celery.canvas.chord",
      "celery.local.recreate_module"
    ],
    "implicit_deps": []
  }
}
```

### Few-shot C05: `celery.uuid` 的跨模块再导出链

**问题**：顶层 `celery.uuid` 最终解析到哪个真实函数符号（跨到 `celery.utils` 之外的提供者）？

**环境前置条件**：
1. 正常导入顶层 `celery` 包。
2. 不对 `celery.utils` 做本地 monkey patch。

**推理过程**：
1. `celery/__init__.py` 的 `recreate_module` 将顶层 `uuid` 映射到 `celery.utils` 模块下的同名符号。
2. `celery/utils/__init__.py` 并未在本地实现 `uuid`，而是 `from kombu.utils.uuid import uuid`。
3. 因此 `celery.utils.uuid` 本身是一次转发引用。
4. 顶层 `celery.uuid` 继续沿该转发链，最终真实提供者落到 `kombu.utils.uuid.uuid`。
5. 这是“顶层懒再导出 + 子模块二次再导出（跨包）”的复合链路。

**答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "kombu.utils.uuid.uuid"
    ],
    "indirect_deps": [
      "celery.utils.uuid",
      "celery.local.recreate_module"
    ],
    "implicit_deps": []
  }
}
```

---

## Type D 命名空间（4 条）

### Few-shot D01: TaskRegistry 同名注册冲突

**问题**: 在同一个 `TaskRegistry` 实例里，先后 `register` 两个 `task.name` 相同、但 `run` 实现不同的 Task，最终 `registry[name]` 指向哪一个？

**环境前置条件**:
1. 两次注册发生在同一个 `TaskRegistry` 对象上。
2. 两个 Task 都有合法 `name`，不会触发 `InvalidTaskError`。
3. 第二次注册确实发生，且不是并发未完成状态。

**推理过程**:
1. `TaskRegistry.register` 先校验 `task.name` 非空，否则抛 `InvalidTaskError`。
2. 如果传入的是类，`register` 会先实例化，再继续处理。
3. 随后它执行 `self[task.name] = task`，把任务写入注册表。
4. `TaskRegistry` 底层是 dict 语义；相同 key 的再次赋值会覆盖旧值。
5. 因此在“同名冲突”场景下，最终 `registry[name]` 指向后注册的 task，也就是 `last write wins`。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.registry.TaskRegistry.register"
    ],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

### Few-shot D02: `@app.task` 自动命名后的同名冲突

**问题**: 同一个 app 中，两个函数都用 `@app.task(lazy=False, shared=False)` 且未显式传 `name`，并且推导出的 `task.name` 相同。第二次装饰时会覆盖第一次，还是复用第一次任务对象？

**环境前置条件**:
1. 两个函数在同一个 app 下注册。
2. 两次注册都走 `lazy=False, shared=False`，避免 pending 与 finalize callback 支路干扰，直接考察同步注册路径。
3. 两个函数推导出的任务名相同。

**推理过程**:
1. `Celery.task` 在 `lazy=False, shared=False` 条件下，不经过 pending 队列，也不注册 `connect_on_app_finalize(cons)` 支路。
2. 该分支直接调用 `self._task_from_fun(fun, **opts)`。
3. `_task_from_fun` 会先确定任务名：`name = name or self.gen_task_name(fun.__name__, fun.__module__)`。
4. `gen_task_name` 最终委托 `celery.utils.imports.gen_task_name` 生成规范任务名。
5. `_task_from_fun` 只有在 `name not in self._tasks` 时才创建新任务；否则直接返回 `self._tasks[name]`。
6. 因此在“同名冲突”场景下，第二次不会覆盖，而是复用第一次已经存在的任务对象，也就是这条路径上 `first wins`。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.gen_task_name",
      "celery.utils.imports.gen_task_name"
    ],
    "implicit_deps": [
      "celery.app.base.Celery._tasks"
    ]
  }
}
```

### Few-shot D03: remote control 命令同名冲突

**问题**: 当自定义 remote control 命令与已有命令同名时，以 pidbox `handlers` 分发结果为准，worker 运行时最终采用哪一个实现？

**环境前置条件**:
1. 两个命令都通过 `@control_command` 或 `@inspect_command` 注册到同一个 `Panel`。
2. 后注册命令发生在前注册命令之后。
3. 两者使用相同 `name`，或函数名推导得到相同 `control_name`。

**推理过程**:
1. `@control_command` / `@inspect_command` 都会转发到 `Panel.register(...)`，再进入 `Panel._register(...)`。
2. `Panel._register` 在内部执行 `Panel.data[control_name] = fun`，把命令实现写入全局 handlers 映射。
3. `Panel.data` 是全局 dict；相同 key 的再次赋值会覆盖旧值，所以同名冲突时“后注册覆盖先注册”。
4. worker pidbox 初始化时把 `handlers=control.Panel.data` 传给 mailbox 节点。
5. 因此运行时命令分发最终采用的是最后一次写入 `Panel.data[control_name]` 的实现。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.worker.control.Panel._register",
      "celery.worker.control.Panel.data"
    ],
    "indirect_deps": [
      "celery.worker.control.control_command",
      "celery.worker.control.inspect_command",
      "celery.worker.pidbox.Pidbox.__init__"
    ],
    "implicit_deps": []
  }
}
```

### Few-shot D04: `dispatch_uid` 冲突下的去重键判定

**问题**: 在同一个 `Signal` 上，对同一 `sender` 重复 `connect` 两个 receiver 且使用同一个 `dispatch_uid` 时，哪个 helper 链路负责生成去重键并阻止第二次 receiver 被追加？

**环境前置条件**:
1. 两次 `connect` 作用于同一个 `Signal` 实例。
2. `sender` 相同，且显式传入相同 `dispatch_uid`。
3. 第二次 `connect` 前未执行 `disconnect`。
4. 关注的是“去重判定发生在哪个 helper 链路”，不是发送阶段的运行时触发次数。

**推理过程**:
1. `Signal.connect(...)` 最终进入 `Signal._connect_signal(...)`。
2. `_connect_signal` 用 `_make_lookup_key(receiver, sender, dispatch_uid)` 生成去重键；当 `dispatch_uid` 存在时，key 由 `(dispatch_uid, sender_id)` 组成，不看 receiver 对象身份。
3. `_connect_signal` 在写入前会清理 dead receivers，然后遍历 `self.receivers`；如果发现相同 key，就不会 append 新 receiver。
4. 因而稳定的“去重判定点”是 `_make_lookup_key` 生成键，再由 `_connect_signal` 检查并阻止追加。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.utils.dispatch.signal.Signal._connect_signal",
      "celery.utils.dispatch.signal._make_lookup_key"
    ],
    "indirect_deps": [
      "celery.utils.dispatch.signal.Signal.connect"
    ],
    "implicit_deps": [
      "celery.utils.dispatch.signal.Signal.receivers"
    ]
  }
}
```

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

### Few-shot E03: by_url + override_backends 的 backend 解析

**问题**: 在提供 `loader.override_backends = {'kv': 'celery.backends.redis:RedisBackend'}` 的前提下，`by_url('kv+redis://localhost/0', loader=loader)` 会把 backend 部分最终解析成哪个类？

**环境前置条件**:
1. `loader.override_backends = {'kv': 'celery.backends.redis:RedisBackend'}`。
2. 调用入口为：`celery.app.backends.by_url('kv+redis://localhost/0', loader=loader)`。

**推理过程**:
1. `by_url` 先检测输入含 `://`，取出 scheme `kv+redis`。
2. `by_url` 再按 `+` 拆分 scheme，得到 `backend='kv'` 与 `url='redis://localhost/0'`。
3. 随后 `by_url` 调用 `by_name('kv', loader)` 去解析 backend 类。
4. `by_name` 会合并 `dict(BACKEND_ALIASES, **loader.override_backends)`，因此 `kv` 命中运行时覆盖映射。
5. `symbol_by_name` 最终把该字符串解析为 `celery.backends.redis.RedisBackend`。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.backends.redis.RedisBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_url",
      "celery.app.backends.by_name",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.app.backends.BACKEND_ALIASES"
    ]
  }
}
```

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

### Few-shot A01: CLI worker 启动长链

**问题**: 执行 `celery -A proj worker` 时，从 CLI 入口到真正启动 worker 的关键调用链是什么？最终负责“启动动作”的可调用对象是谁？

**环境前置条件**:
1. 使用当前 Celery Click CLI（`celery.bin.celery` + `celery.bin.worker`）流程。
2. `-A proj` 可被 `find_app` 成功解析为 app 实例。
3. 未对 `worker` 子命令做自定义替换。

**推理过程**:
1. CLI 入口 `celery.bin.celery.main()` 调用 Click group（`celery(...)`），并通过 `celery.add_command(worker)` 将 `worker` 子命令路由到 `celery.bin.worker.worker`。
2. `celery.bin.worker.worker(...)` 读取 `ctx.obj.app`，构造 `worker = app.Worker(...)`。
3. `app.Worker` 不是普通属性，而是 `Celery.Worker` cached_property；它通过 `subclass_with_self('celery.apps.worker:Worker')` 解析并生成绑定 app 的 Worker 子类。
4. `subclass_with_self` 内部依赖 `symbol_by_name` 将字符串路径解析为真实类 `celery.apps.worker.Worker`。
5. `celery.bin.worker.worker(...)` 随后调用 `worker.start()`；该 `start` 实现来自父类 `celery.worker.worker.WorkController.start`，这是实际执行启动流程的最终可调用对象。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.worker.worker.WorkController.start"
    ],
    "indirect_deps": [
      "celery.bin.celery.main",
      "celery.bin.worker.worker",
      "celery.app.base.Celery.Worker",
      "celery.apps.worker.Worker",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  }
}
```

### Few-shot A02: `current_app.tasks` 首访链路（分离 default app 与 finalize）

**问题**：在未显式创建全局 app 的前提下，首次访问 `celery.current_app.tasks` 时，哪一步只负责创建/返回 default app，哪一步才会触发 `finalize`？

**环境前置条件**：
1. 进程内尚未显式执行 `Celery(..., set_as_current=True)` 或其他等价的全局 app 绑定。
2. 使用默认 current_app 路径（未开启 `C_STRICT_APP` / `C_WARN_APP` 特殊分支）。
3. `autofinalize=True`（默认配置）。

**推理过程**：
1. `celery.current_app` 是 `Proxy(get_current_app)`；先发生的是 Proxy 解引用，而不是任务注册表访问。
2. 在默认分支中，`get_current_app` 绑定到 `_get_current_app`：若 `default_app is None`，会创建 fallback `Celery('default', fixups=[], set_as_current=False, loader=...)` 并 `set_default_app(...)`。
3. 到这一步为止，只完成“创建/返回 default app”；单独访问 `celery.current_app` 本身不会触发 `finalize`。
4. 随后访问 `.tasks` 才命中 `Celery.tasks`（cached_property），其内部显式执行 `self.finalize(auto=True)`，这是 finalize 的稳定触发点。
5. `finalize` 内部可能涉及 `_announce_app_finalized`、`maybe_evaluate` 等子步骤，但它们受内部状态影响，不应作为本题必经主链依赖。

**答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.tasks"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.finalize",
      "celery._state._get_current_app"
    ],
    "implicit_deps": [
      "celery._state.current_app",
      "celery.local.Proxy",
      "celery._state.default_app"
    ]
  }
}
```

---

## 使用说明

1. 这些 few-shot 示例应该写入 `pe/prompt_templates_v2.py`
2. 每条示例必须包含完整的推理过程（CoT 风格）
3. 优先从 Day 2 的 bad case 中提取真实案例
4. 保持 20 条的配比，不要偏向 Easy 样本

## 后续工作

- [x] 从 bad case 中补充完整的 20 条示例（当前正式文档已稳定 20 条；`A02 / B05 / C04 / C05` 已回填）
- [x] 每条示例验证在 Celery 源码中可复现
- [x] 写入 `pe/prompt_templates_v2.py`
- [x] 创建 `data/fewshot_examples_20.json` 文件
