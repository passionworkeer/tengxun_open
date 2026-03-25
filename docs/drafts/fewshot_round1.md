# Few-shot Round 1 Draft (Worker C)

说明：本草稿只用于回填 `docs/fewshot_examples.md` 的空位，不修改正式文档。  
答案组织统一采用新版 schema 兼容形式：

```json
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

---

## Type B（3 条）

### Few-shot B02（回填空位：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B02`）

**问题**：当 `@app.task(shared=True, lazy=True)` 装饰一个函数且 app 尚未 finalized 时，最终是谁真正创建并注册任务实例？

**推理过程（>=4步）**：
1. 在 `celery.app.base.Celery.task` 里进入 `inner_create_task_cls`，`shared=True` 分支定义 `cons(app)`。
2. `cons(app)` 的核心调用是 `app._task_from_fun(fun, **opts)`，但该调用先通过 `connect_on_app_finalize(cons)` 挂到 finalize 回调中。
3. `lazy=True` 且 app 未 finalized 时，当前 app 先返回 `PromiseProxy(self._task_from_fun, ...)` 并压入 `self._pending`。
4. `Celery.finalize` 执行时会先触发 `_announce_app_finalized(self)`，从而运行前面注册的 `cons(app)`。
5. 随后 `finalize` 还会 `maybe_evaluate` pending 代理；两条路径最终都汇聚到 `_task_from_fun` 做真实注册。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery._state.connect_on_app_finalize",
      "celery.app.base.Celery.finalize"
    ],
    "implicit_deps": [
      "celery._state._announce_app_finalized"
    ]
  }
}
```

**对抗的失效类型**：Type B（把装饰器包装层误判为最终注册点，或漏掉 finalize 回调链）。

---

### Few-shot B03（回填空位：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B03`）

**问题**：`celery.app.builtins.add_backend_cleanup_task` 没有被业务代码直接调用，它是如何被注册到每个 app 的任务表中的？

**推理过程（>=4步）**：
1. `add_backend_cleanup_task` 在 `celery/app/builtins.py` 上带有 `@connect_on_app_finalize`。
2. 该装饰器会把函数加入 `_on_app_finalizers`（而不是立刻执行）。
3. 当任意 app 调用 `Celery.finalize` 时，`_announce_app_finalized(self)` 会遍历并执行这些回调。
4. 回调函数体内部再定义 `@app.task(name='celery.backend_cleanup', shared=False, lazy=False)` 的 `backend_cleanup`。
5. `lazy=False` 让 `app.task` 立即走到 `app._task_from_fun(...)`，真正写入 `app._tasks`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery._state.connect_on_app_finalize",
      "celery.app.base.Celery.task"
    ],
    "implicit_deps": [
      "celery._state._announce_app_finalized"
    ]
  }
}
```

**对抗的失效类型**：Type B（误以为 builtins 任务“显式 import 即注册”，忽略 finalize 时机和二次装饰器）。

---

### Few-shot B04（回填空位：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B04`）

**问题**：`@shared_task` 未显式传 `name` 时，返回的 Proxy 在首次访问时如何定位到当前 app 的真实任务对象？

**推理过程（>=4步）**：
1. `shared_task` 返回 `Proxy(task_by_cons)`，并在回调中安排 `app._task_from_fun(fun, **options)`。
2. Proxy 真正取值时执行 `task_by_cons()`，先通过 `_state.get_current_app()` 获取“当前 app”。
3. `task_by_cons` 使用 `name or app.gen_task_name(fun.__name__, fun.__module__)` 作为键去查 `app.tasks[...]`。
4. `app.gen_task_name` 又委托给 `celery.utils.imports.gen_task_name` 生成标准任务名。
5. 对应键的任务实例本身由 `_task_from_fun` 预先创建并注册。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery._state.get_current_app",
      "celery.app.base.Celery.gen_task_name",
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery.utils.imports.gen_task_name"
    ],
    "implicit_deps": []
  }
}
```

**对抗的失效类型**：Type B（把 Proxy 返回值当作“最终任务对象”，忽略运行时解析和命名生成链）。

---

## Type C（2 条）

### Few-shot C02（回填空位：`docs/fewshot_examples.md` -> `Type C` -> `Few-shot C02`）

**问题**：顶层符号 `celery.Task` 最终映射到哪个真实类？

**推理过程（>=4步）**：
1. 在 `celery/__init__.py` 中，顶层导出使用 `local.recreate_module(...)` 做惰性再导出。
2. `by_module` 映射里把 `'Task'` 挂在 `'celery.app.task'` 下。
3. 因此访问 `celery.Task` 时会按映射转发到 `celery.app.task` 模块取同名符号。
4. `celery/app/task.py` 中的真实定义是 `class Task`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.task.Task"
    ],
    "indirect_deps": [
      "celery.local.recreate_module"
    ],
    "implicit_deps": []
  }
}
```

**对抗的失效类型**：Type C（多层再导出链中断，只停留在顶层符号名）。

---

### Few-shot C03（回填空位：`docs/fewshot_examples.md` -> `Type C` -> `Few-shot C03`）

**问题**：顶层 `celery.current_app` 不是普通变量，它最终指向什么对象/入口？

**推理过程（>=4步）**：
1. `celery/__init__.py` 的 `recreate_module` 映射把 `current_app` 指到 `celery._state`。
2. 在 `celery/_state.py` 中，`current_app` 定义为 `Proxy(get_current_app)`。
3. `get_current_app` 在默认配置下别名到 `_get_current_app`。
4. `_get_current_app` 返回 `_tls.current_app or default_app`，必要时会先初始化默认 Celery app。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery._state.current_app"
    ],
    "indirect_deps": [
      "celery._state.get_current_app"
    ],
    "implicit_deps": [
      "celery._state._get_current_app"
    ]
  }
}
```

**对抗的失效类型**：Type C（把顶层别名当静态对象，漏掉 Proxy 与再导出层）。

---

## Type E（3 条）

### Few-shot E02（回填空位：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E02`）

**问题**：Celery app 初始化时，默认 fixup 字符串 `'celery.fixups.django:fixup'` 如何变成可调用对象并被执行？

**推理过程（>=4步）**：
1. `Celery` 类常量 `BUILTIN_FIXUPS` 包含 `'celery.fixups.django:fixup'` 字符串。
2. `Celery.__init__` 中将 `self.fixups` 设为该集合（若未显式覆盖）。
3. 随后执行列表推导：`self._fixups = [symbol_by_name(fixup)(self) for fixup in self.fixups]`。
4. `symbol_by_name` 把字符串路径解析为真实函数对象 `celery.fixups.django.fixup`。
5. 该函数立即以 `self`（app）为参数执行，完成 fixup 安装逻辑。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.fixups.django.fixup"
    ],
    "indirect_deps": [
      "kombu.utils.imports.symbol_by_name"
    ],
    "implicit_deps": []
  }
}
```

**对抗的失效类型**：Type E（字符串符号加载链断裂，或把字符串常量误当不可执行配置）。

---

### Few-shot E03（回填空位：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E03`）

**问题**：`celery.app.backends.by_url('db+sqlite:///tmp/celery.db')` 最终 backend 类如何确定？

**推理过程（>=4步）**：
1. `by_url` 先解析 URL scheme，检测到 `'db+sqlite...'` 里含 `'+'`，拆成 `backend='db'` 与 `url='sqlite:///tmp/celery.db'`。
2. `by_url` 调用 `by_name(backend, loader)` 去做类解析。
3. `by_name` 从 `BACKEND_ALIASES` 找到 `'db' -> 'celery.backends.database:DatabaseBackend'`。
4. `symbol_by_name` 把该字符串解析为真实类对象。
5. 最终返回 `(celery.backends.database.DatabaseBackend, 'sqlite:///tmp/celery.db')`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.backends.database.DatabaseBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_name",
      "kombu.utils.imports.symbol_by_name"
    ],
    "implicit_deps": []
  }
}
```

**对抗的失效类型**：Type E（URL 字符串到别名再到类对象的多跳映射失败）。

---

### Few-shot E04（回填空位：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E04`）

**问题**：若环境变量 `CELERY_CUSTOM_WORKER_POOL='celery.concurrency.thread:TaskPool'`，调用 `get_implementation('custom')` 时最终解析到什么？

**推理过程（>=4步）**：
1. `celery.concurrency.__init__` 导入时读取环境变量 `CELERY_CUSTOM_WORKER_POOL`。
2. 若变量存在，则把 `ALIASES['custom']` 设为该字符串值。
3. `get_implementation('custom')` 调用 `symbol_by_name(cls, ALIASES)`。
4. `symbol_by_name` 先经别名字典取到 `'celery.concurrency.thread:TaskPool'`，再导入并取符号。
5. 返回真实类 `celery.concurrency.thread.TaskPool`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.concurrency.thread.TaskPool"
    ],
    "indirect_deps": [
      "kombu.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "os.environ.CELERY_CUSTOM_WORKER_POOL"
    ]
  }
}
```

**对抗的失效类型**：Type E（环境变量驱动的动态别名注入被忽略，导致把 `custom` 误判为固定实现）。

---

## 自审（重复风险与 hard 程度）

### 1) 最可能与现有评测集样本重复的 few-shot

- **B02**：与现有 `hard_002`（`@app.task` -> `_task_from_fun`）主链高度接近，只是补了 `lazy/pending/finalize` 双路径细节。
- **B04**：与现有 `hard_001`（`@shared_task` -> `_task_from_fun`）部分重叠，但本条强调 Proxy 取值与任务名生成。
- **E03**：与现有 `medium_001`（`by_name('redis')`）共享同一 backend alias 机制，只是改成 `by_url` 的 `+` 拆分场景。

### 2) 最可能“不够 hard”的 few-shot

- **C02**：`celery.Task` 再导出链较短，偏 easy/medium。
- **C03**：虽然含 Proxy，但路径清晰，整体仍偏 medium。
- **E04**：若只看静态代码，难度中等；真正 hard 点在“环境变量在模块导入时注入 alias”，建议评测时显式给定环境前提。

### 3) 建议的后续加硬方向（供下一轮）

- Type C 可加入跨两层 `__init__.py` 的别名转发链（不是单跳 re-export）。
- Type E 可加入 entry points（`load_extension_class_names`）与 fallback alias 同时存在的冲突解析题。
- Type B 可加入 `@connect_on_app_finalize` + `@app.task` 叠加且 `shared/lazy` 组合变化的对照题。

