# Few-shot Round 2 Draft (Only Challenged Items)

范围说明：本文件仅处理 challenge reviewer 指定的 8 条（B02/B03/B04/C02/C03/E02/E03/E04），不修改正式文档。  
回填目标：`docs/fewshot_examples.md` 对应空位。  
答案结构：继续兼容新版 schema（`ground_truth.direct_deps / indirect_deps / implicit_deps`）。

---

## B02（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B02`  
**Reviewer objection（摘要）**：与 `hard_002` 主链过近；未把 `lazy/pending` 分支写成清晰的 few-shot 输出口径。  
**Round2 响应**：把题干重心从“最终注册是谁”改为“pending 队列在 finalize 时如何兑现”，显式写出 `PromiseProxy -> maybe_evaluate -> _task_from_fun` 路径。

**环境前置条件**：无。

**修订版问题**：当 `@app.task(shared=True, lazy=True)` 装饰函数且 app 尚未 finalized 时，`self._pending` 里的代理对象在 finalize 阶段通过哪个关键链路被兑现为真实任务？

**推理过程（>=4步）**：
1. `Celery.task` 在 `lazy=True` 且未 finalized 分支中返回 `PromiseProxy(self._task_from_fun, ...)` 并压入 `self._pending`。
2. 同时，`shared=True` 分支还会 `connect_on_app_finalize(cons)`，其中 `cons(app)` 也会调用 `app._task_from_fun(...)`。
3. `Celery.finalize` 执行时先触发 `_announce_app_finalized(self)`，运行 finalize callbacks。
4. 随后 `finalize` 进入 `while pending: maybe_evaluate(pending.popleft())`，把 `PromiseProxy` 兑现为真实调用。
5. 两条路径最终都汇聚到 `Celery._task_from_fun` 完成任务实例创建/注册。

**标准答案**：
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

**对抗的失效类型**：Type B（装饰器延迟路径和 pending 兑现路径被漏掉/混淆）。  
**为什么比 round1 更不重复**：`hard_002` 只强调 `_task_from_fun` 终点；本题新增“pending 队列兑现”这一独立失败模式。

---

## B03（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B03`  
**Reviewer objection（摘要）**：与 `hard_002/hard_014` 终点重合；缺少 `@connect_on_app_finalize -> _announce_app_finalized` 闭环细节。  
**Round2 响应**：改成“内置任务注册机制”题，强调 builtins callback 被执行的路径，而非普通用户任务装饰器路径。

**环境前置条件**：无。

**修订版问题**：`add_backend_cleanup_task` 不是业务代码显式调用的函数，它是如何在 app finalize 时被执行并注册成 `celery.backend_cleanup` 任务的？

**推理过程（>=4步）**：
1. `add_backend_cleanup_task` 在定义处带 `@connect_on_app_finalize`，因此它先被存入 `_on_app_finalizers`。
2. `Celery.finalize` 中调用 `_announce_app_finalized(self)`，统一执行这些回调。
3. 回调运行后，函数体内部定义 `@app.task(name='celery.backend_cleanup', shared=False, lazy=False)`。
4. 由于 `lazy=False`，`app.task` 不走代理延迟分支，直接调用 `app._task_from_fun(...)`。
5. 最终任务被写入当前 app 的任务注册表，名字为 `celery.backend_cleanup`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery._state._announce_app_finalized",
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery._state.connect_on_app_finalize",
      "celery.app.base.Celery.task"
    ],
    "implicit_deps": [
      "celery.app.builtins.add_backend_cleanup_task"
    ]
  }
}
```

**对抗的失效类型**：Type B（把“内置 callback 注册”误判为“显式调用注册”）。  
**为什么比 round1 更不重复**：不再仅复述 `_task_from_fun` 终点，新增“builtins finalize callback 执行机制”这个差异点（内置任务 vs 用户任务）。

---

## B04（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B04`  
**Reviewer objection（摘要）**：未把“未显式 name 时的命名与查表路径”讲清；与 `hard_001` 差异不充分。  
**Round2 响应**：把题干改为“查表键如何生成并保证命中”，显式加入 `gen_task_name` 与 `app.tasks` 的触发顺序。

**环境前置条件**：无。

**修订版问题**：`@shared_task` 未显式传 `name` 时，Proxy 首次解引用时如何生成任务名并保证 `app.tasks[...]` 查表成功？

**推理过程（>=4步）**：
1. `shared_task` 返回 `Proxy(task_by_cons)`，真正取值时才执行 `task_by_cons()`。
2. `task_by_cons()` 先取 `app = _state.get_current_app()`，然后构造查表键：`name or app.gen_task_name(fun.__name__, fun.__module__)`。
3. `app.gen_task_name` 委托 `celery.utils.imports.gen_task_name`，补齐模块名前缀并生成标准任务名。
4. `task_by_cons` 接着访问 `app.tasks[...]`；而 `app.tasks` 属性会先触发 `finalize(auto=True)`。
5. finalize 期间该 shared task 已通过回调路径注册进表，查表因此命中并返回真实任务对象。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.gen_task_name",
      "celery.app.base.Celery.tasks"
    ],
    "indirect_deps": [
      "celery.utils.imports.gen_task_name",
      "celery.app.base.Celery.finalize"
    ],
    "implicit_deps": [
      "celery.app.base.Celery._task_from_fun"
    ]
  }
}
```

**对抗的失效类型**：Type B（只看到 shared_task 装饰器，不理解“命名+查表+finalize”联动）。  
**为什么比 round1 更不重复**：与 `hard_001` 的区别是本题核心在“未命名任务的 key 生成与查表命中条件”，不是单纯注册终点。

---

## C02（reject -> replaced with new Type C）

**回填空位**：`docs/fewshot_examples.md` -> `Type C` -> `Few-shot C02`  
**Reviewer objection（摘要）**：旧题与 eval 的 `easy_007` 重复，且链路过短。  
**Round2 响应**：完全替换为新题，改为“顶层再导出 + 中间函数转发 + 实现函数”三跳链路。

**环境前置条件**：无。

**全新问题**：调用顶层 `celery.bugreport()`（不传 app）时，最终生成报告字符串的真实函数是哪一个？

**推理过程（>=4步）**：
1. `celery/__init__.py` 通过 `recreate_module` 把顶层 `bugreport` 再导出到 `celery.app.bugreport`。
2. `celery.app.bugreport(app=None)` 内部会走 `(app or _state.get_current_app()).bugreport()`。
3. `Celery.bugreport`（`celery.app.base.Celery.bugreport`）再调用 `bugreport(self)`。
4. 这里的 `bugreport` 来自 `celery.app.utils`，即实际字符串拼装逻辑在 `celery.app.utils.bugreport`。
5. 因为题设不传 app，链路含有一次隐式 current_app 解析。

**标准答案**：
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

**对抗的失效类型**：Type C（多跳再导出链中断，只停在顶层别名）。  
**为什么比 round1 更不重复**：不再使用 `celery.Task` 单跳映射，改为三跳链路且不与现有 eval 条目同题。

---

## C03（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type C` -> `Few-shot C03`  
**Reviewer objection（摘要）**：旧题与 `easy_005`（`current_app`）主题重叠，且 implicit 细节不足。  
**Round2 响应**：改题为 `subtask` 兼容别名链，避免继续复用 current_app 主题。

**环境前置条件**：无。

**修订版问题**：顶层 `celery.subtask` 最终映射到哪个真实可调用入口？

**推理过程（>=4步）**：
1. `celery/__init__.py` 的 `recreate_module` 将顶层 `subtask` 再导出自 `celery.canvas`。
2. `celery.canvas` 内并没有独立实现 `def subtask`，而是兼容别名：`subtask = signature`。
3. 因此顶层 `celery.subtask` 实际指向 `celery.canvas.signature`。
4. `signature(...)` 再根据输入类型构造/规范化 `Signature` 对象（例如 `Signature.from_dict` 或 `Signature(...)`）。
5. 也就是说这是“再导出 + 模块内别名”的两段链，而不是单层映射。

**标准答案**：
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

**对抗的失效类型**：Type C（忽略兼容别名导致映射终点错误）。  
**为什么比 round1 更不重复**：从 `current_app` Proxy 主题切到 `subtask -> signature` 的别名链，与 eval 的 current_app/current_task 系列解耦。

---

## E02（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E02`  
**Reviewer objection（摘要）**：`symbol_by_name` 来源 FQN 写错；未说明 Django fixup 前置条件和返回对象。  
**Round2 响应**：修正为 `celery.utils.imports.symbol_by_name`，并把“条件满足才返回 `DjangoFixup(app).install()`”写入题干与推理。

**环境前置条件（必须满足）**：
1. `DJANGO_SETTINGS_MODULE` 已设置。  
2. 运行环境可导入 `django` 且版本满足要求。  
3. `app.loader_cls.lower()` 不包含 `'django'`（满足 `fixup` 分支条件）。

**修订版问题**：在满足上述 Django 前置条件时，`BUILTIN_FIXUPS` 中的字符串 `'celery.fixups.django:fixup'` 如何被解析并执行，最终返回什么对象？

**推理过程（>=4步）**：
1. `Celery` 初始化时默认 `self.fixups` 含有 `'celery.fixups.django:fixup'`。
2. `Celery.__init__` 执行：`self._fixups = [symbol_by_name(fixup)(self) for fixup in self.fixups]`。
3. 这里的 `symbol_by_name` 来自 `celery.utils.imports`，把字符串解析为 `celery.fixups.django.fixup`。
4. 解析后立即执行 `fixup(self)`；在前置条件成立时，函数返回 `DjangoFixup(app).install()`。
5. 若前置条件不成立，该分支可能返回 `None`，链路不成立（需在样本中明确）。

**标准答案**：
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

**对抗的失效类型**：Type E（字符串符号解析后“立即执行”步骤被漏掉）。  
**为什么比 round1 更不重复**：新增“前置条件 + 返回对象 + 失败分支”三要素，不再是单纯字符串到函数名映射。

---

## E03（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E03`  
**Reviewer objection（摘要）**：与 `medium_001` 过近；未突出 `by_url` 的拆分与二元返回。  
**Round2 响应**：改为“`by_url` + `loader.override_backends` 运行时覆盖”场景，显式输出 `(cls, url)`。

**环境前置条件（必须满足）**：
1. 传入的 `loader` 对象包含 `override_backends={'kv': 'celery.backends.redis:RedisBackend'}`。  
2. 调用：`by_url('kv+redis://localhost/0', loader=loader)`。

**修订版问题**：在上述前置下，`by_url('kv+redis://localhost/0', loader=loader)` 最终返回什么（类与 URL）？

**推理过程（>=4步）**：
1. `by_url` 先识别 `://`，再把 scheme `kv+redis` 按 `+` 拆成 `backend='kv'` 与 `url='redis://localhost/0'`。
2. `by_url` 调用 `by_name('kv', loader)` 解析 backend 类。
3. `by_name` 构造别名字典：`dict(BACKEND_ALIASES, **loader.override_backends)`，`override_backends` 可覆盖默认别名。
4. `symbol_by_name` 把 `'kv'` 解析为 `celery.backends.redis.RedisBackend`。
5. `by_url` 最终返回二元组 `(celery.backends.redis.RedisBackend, 'redis://localhost/0')`。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.backends.redis.RedisBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_name",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.app.backends.BACKEND_ALIASES"
    ]
  },
  "expected_return": [
    "celery.backends.redis.RedisBackend",
    "redis://localhost/0"
  ]
}
```

**对抗的失效类型**：Type E（URL 拆分与运行时 alias 覆盖路径丢失）。  
**为什么比 round1 更不重复**：不再是“固定 alias 取类”单点题，而是“by_url 拆分 + 覆盖 alias + tuple 返回”三段链。

---

## E04（hold -> revised）

**回填空位**：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E04`  
**Reviewer objection（摘要）**：缺少环境前置与“模块导入时机”说明；隐式链不完整。  
**Round2 响应**：把“必须在导入前设置 env”写成硬前提，并在推理中加入 import-time alias 注入。

**环境前置条件（必须满足）**：
1. 在首次导入 `celery.concurrency` 之前设置：`CELERY_CUSTOM_WORKER_POOL='celery.concurrency.thread:TaskPool'`。  
2. 若在导入之后才设置该变量，需要 reload 模块，否则 `ALIASES['custom']` 不会自动更新。

**修订版问题**：满足上述前置时，`get_implementation('custom')` 最终解析到哪个类？

**推理过程（>=4步）**：
1. `celery.concurrency.__init__` 在模块导入阶段读取 `os.environ.get('CELERY_CUSTOM_WORKER_POOL')`。
2. 若读到值，则在导入时执行 `ALIASES['custom'] = custom`（这是关键隐式步骤）。
3. `get_implementation('custom')` 调用 `symbol_by_name(cls, ALIASES)`。
4. `symbol_by_name` 先从 `ALIASES` 取字符串 `'celery.concurrency.thread:TaskPool'`，再导入并取符号。
5. 返回真实类 `celery.concurrency.thread.TaskPool`。

**标准答案**：
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

**对抗的失效类型**：Type E（忽略“导入时注入 alias”的时序依赖）。  
**为什么比 round1 更不重复**：新增“导入时机”这条硬条件，避免把它误当静态恒成立映射。

---

## Round2 备注

1. 本轮对 8 条都逐条回应了 objection。  
2. 所有条目都显式给出“环境前置条件”（无条件场景也明确写了“无”）。  
3. C02 已按要求完全替换为全新 Type C 多跳再导出题，不再修补旧题。

