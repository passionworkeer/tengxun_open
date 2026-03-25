# Eval Easy/Medium Round 1 (Worker A)

> 已按最新 `docs/dataset_schema.md` 口径调整：以下草稿统一使用新 schema 核心字段  
> `id、difficulty、category、failure_type、implicit_level、question、source_file、source_commit、ground_truth.direct_deps、ground_truth.indirect_deps、ground_truth.implicit_deps、reasoning_hint、source_note`。

## 总表（8 条：Easy 4 + Medium 4）

| id | difficulty | category | source_file | 目标核心符号（摘要） | 与现有12条差异 |
|---|---|---|---|---|---|
| easy_005 | easy | re_export_proxy | celery/__init__.py | celery._state.current_app | 不是 `celery.Celery/shared_task`，改测顶层 Proxy 导出 |
| easy_006 | easy | re_export_proxy | celery/__init__.py | celery._state.current_task | 不是类/函数导出，改测 task 上下文 Proxy |
| easy_007 | easy | re_export | celery/__init__.py | celery.app.task.Task | 与 `easy_001` 同属 re-export，但目标从 App 类换成 Task 基类 |
| easy_008 | easy | re_export | celery/__init__.py | celery.canvas.group | 非 loader/concurrency 别名链，改测 canvas 导出 |
| medium_005 | medium | loader_default_resolution | celery/app/base.py | celery.loaders.app.AppLoader | 与 `medium_002` 不同：入口改为 `Celery.loader` 默认分支 + 实例化 |
| medium_006 | medium | backend_url_alias | celery/app/base.py | celery.backends.rpc.RPCBackend | 与 `medium_001` 不同：走 `_get_backend -> by_url` 的 URL scheme 解析 |
| medium_007 | medium | subclass_with_self | celery/app/base.py | celery.apps.worker.Worker | 新增字符串 FQN 解析 + 动态子类包装路径 |
| medium_008 | medium | strategy_string_resolution | celery/app/task.py | celery.worker.strategy.default | 与 `hard_004` 不同：这里解析 `Task.Strategy`，不是 `task.Request` |

## JSON 草稿（新 schema）

### easy_005

```json
{
  "id": "easy_005",
  "difficulty": "easy",
  "category": "re_export_proxy",
  "failure_type": "Type C",
  "implicit_level": 2,
  "question": "在顶层懒加载 API 中，`celery.current_app` 最终对应到哪个真实符号？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery._state.current_app"
    ],
    "indirect_deps": [
      "celery._state.get_current_app"
    ],
    "implicit_deps": [
      "celery.local.Proxy"
    ]
  },
  "reasoning_hint": "`celery.__init__` 通过 `recreate_module` 将 `current_app` 从 `celery._state` 暴露出来，而 `_state.current_app` 本身是 `Proxy(get_current_app)`。",
  "source_note": "与已有 easy_001/easy_002 的差异：本题不是 `Celery/shared_task`，而是顶层运行时 app 指针的 Proxy 导出链。"
}
```

### easy_006

```json
{
  "id": "easy_006",
  "difficulty": "easy",
  "category": "re_export_proxy",
  "failure_type": "Type C",
  "implicit_level": 2,
  "question": "在顶层懒加载 API 中，`celery.current_task` 最终对应到哪个真实符号？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery._state.current_task"
    ],
    "indirect_deps": [
      "celery._state.get_current_task"
    ],
    "implicit_deps": [
      "celery.local.Proxy"
    ]
  },
  "reasoning_hint": "`celery.__init__` 把 `current_task` 从 `celery._state` 暴露到顶层，而 `_state.current_task` 由 `Proxy(get_current_task)` 构造。",
  "source_note": "与已有 easy 样本差异：关注“当前任务上下文”代理对象，不是类导出或 alias 字典。"
}
```

### easy_007

```json
{
  "id": "easy_007",
  "difficulty": "easy",
  "category": "re_export",
  "failure_type": "Type C",
  "implicit_level": 1,
  "question": "顶层符号 `celery.Task` 最终映射到哪个真实类？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.task.Task"
    ],
    "indirect_deps": [],
    "implicit_deps": []
  },
  "reasoning_hint": "`celery.__init__` 的 `recreate_module` 直接将 `Task` 指向 `celery.app.task` 模块中的 `Task` 类。",
  "source_note": "与 easy_001 相近但不重复：同为顶层 re-export，目标从 `Celery` 类改为任务基类 `Task`。"
}
```

### easy_008

```json
{
  "id": "easy_008",
  "difficulty": "easy",
  "category": "re_export",
  "failure_type": "Type C",
  "implicit_level": 2,
  "question": "顶层符号 `celery.group` 最终映射到哪个真实实现？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.canvas.group"
    ],
    "indirect_deps": [
      "celery.canvas.Signature"
    ],
    "implicit_deps": []
  },
  "reasoning_hint": "顶层 `celery.group` 由 `recreate_module` 从 `celery.canvas` 暴露；在 `canvas.py` 中 `group` 定义为 `class group(Signature)`。",
  "source_note": "与现有 12 条差异：不涉及 loader/backend/concurrency alias，改测 canvas 导出链。"
}
```

### medium_005

```json
{
  "id": "medium_005",
  "difficulty": "medium",
  "category": "loader_default_resolution",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "在未设置 `CELERY_LOADER` 且未显式传入 loader 参数时，`Celery.loader` 属性最终实例化哪个 Loader 类？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.app.AppLoader"
    ],
    "indirect_deps": [
      "celery.app.base.Celery._get_default_loader",
      "celery.loaders.get_loader_cls"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`_get_default_loader` 在默认分支返回字符串 `celery.loaders.app:AppLoader`；`loader` 属性再经 `get_loader_cls(...)->symbol_by_name` 解析并实例化。",
  "source_note": "与 medium_002 的差异：medium_002 直接问 `get_loader_cls('app')`，本题入口是 `Celery.loader` 默认链路，包含默认值决策与实例化。"
}
```

### medium_006

```json
{
  "id": "medium_006",
  "difficulty": "medium",
  "category": "backend_url_alias",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "当 `result_backend` 配置为 `rpc://...` 时，`Celery._get_backend` 最终解析并实例化的 backend 类是什么？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.backends.rpc.RPCBackend"
    ],
    "indirect_deps": [
      "celery.app.base.Celery._get_backend",
      "celery.app.backends.by_url",
      "celery.app.backends.by_name"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`_get_backend` 调 `backends.by_url`；`by_url` 先按 `://` 切 scheme 为 `rpc`，再进入 `by_name`；`BACKEND_ALIASES['rpc']` 指向 `celery.backends.rpc.RPCBackend`。",
  "source_note": "与 medium_001 的差异：medium_001 是 `by_name('redis')` 直接 alias，本题是 URL-scheme 入口（`by_url`）+ `_get_backend` 调用链。"
}
```

### medium_007

```json
{
  "id": "medium_007",
  "difficulty": "medium",
  "category": "subclass_with_self",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "`Celery.Worker` 这个缓存属性在解析字符串路径后，底层基类指向哪个真实类？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.apps.worker.Worker"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.Worker",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`Celery.Worker` 返回 `self.subclass_with_self('celery.apps.worker:Worker')`；`subclass_with_self` 先 `symbol_by_name` 解析，再动态 `type(...)` 生成绑定 app 的子类。",
  "source_note": "新增路径，现有 12 条未覆盖 `subclass_with_self` 动态子类模式。"
}
```

### medium_008

```json
{
  "id": "medium_008",
  "difficulty": "medium",
  "category": "strategy_string_resolution",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "`Task.start_strategy` 调用时，`Task.Strategy` 字符串最终会被解析为哪个可调用对象？",
  "source_file": "celery/app/task.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.worker.strategy.default"
    ],
    "indirect_deps": [
      "celery.app.task.Task.start_strategy",
      "celery.utils.imports.instantiate"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`Task.Strategy` 预设为 `'celery.worker.strategy:default'`，`start_strategy` 调 `instantiate(self.Strategy, ...)`，而 `instantiate` 内部调用 `symbol_by_name`。",
  "source_note": "与 hard_004 的差异：hard_004 关注 `worker.strategy.default` 内对 `task.Request` 的解析；本题关注 `Task.Strategy` 本身的字符串入口解析。"
}
```

## Evidence Chain（逐条 >=3 步）

### easy_005 evidence chain
1. `celery/__init__.py` 的 `recreate_module(... by_module=...)` 明确将 `current_app` 从 `celery._state` 暴露到顶层 `celery`。
2. `celery/_state.py` 定义 `current_app = Proxy(get_current_app)`，说明它不是普通对象而是代理。
3. 同文件中 `get_current_app`（默认分支指向 `_get_current_app`）提供了 `current_app` 的真实取值入口，因此最终目标符号是 `celery._state.current_app`，并隐含依赖 `Proxy/get_current_app`。

### easy_006 evidence chain
1. `celery/__init__.py` 的 `by_module` 同时将 `current_task` 从 `celery._state` 暴露到顶层。
2. `celery/_state.py` 定义 `current_task = Proxy(get_current_task)`。
3. `get_current_task` 返回 `_task_stack.top`，因此这是“当前执行任务”的代理访问链，最终符号命中 `celery._state.current_task`。

### easy_007 evidence chain
1. `celery/__init__.py` 在 `recreate_module` 的 `by_module` 里有 `'celery.app.task': ['Task']`。
2. 访问 `celery.Task` 时 lazy module 会导入 `celery.app.task` 并取同名符号。
3. `celery/app/task.py` 中 `class Task:` 给出最终定义，因此落点是 `celery.app.task.Task`。

### easy_008 evidence chain
1. `celery/__init__.py` 将 `group` 作为 `celery.canvas` 的导出符号暴露到顶层。
2. `celery/canvas.py` 的 `__all__` 包含 `group`，可被导出。
3. 同文件定义 `class group(Signature)`，因此顶层 `celery.group` 的真实实现符号是 `celery.canvas.group`。

### medium_005 evidence chain
1. `celery/app/base.py` 中 `__init__` 将 `self.loader_cls = loader or self._get_default_loader()`。
2. `_get_default_loader` 默认返回字符串 `'celery.loaders.app:AppLoader'`（在 `CELERY_LOADER` 未设置且无自定义 loader 时）。
3. `loader` 属性执行 `get_loader_cls(self.loader_cls)(app=self)`；而 `celery/loaders/__init__.py` 的 `get_loader_cls` 通过 `symbol_by_name` 解析字符串，最终实例化 `celery.loaders.app.AppLoader`。

### medium_006 evidence chain
1. `celery/app/base.py` 的 `_get_backend` 调用 `backends.by_url(self.backend_cls or self.conf.result_backend, self.loader)`。
2. `celery/app/backends.py` 的 `by_url` 在检测到 `://` 后提取 scheme（如 `rpc`），再调用 `by_name`。
3. `BACKEND_ALIASES` 中 `'rpc': 'celery.backends.rpc.RPCBackend'`，`by_name` 再经 `symbol_by_name` 解析，最终由 `_get_backend` 实例化该 backend 类。

### medium_007 evidence chain
1. `celery/app/base.py` 的 `Worker` 缓存属性返回 `self.subclass_with_self('celery.apps.worker:Worker')`。
2. `subclass_with_self` 首先执行 `Class = symbol_by_name(Class)`，把字符串路径解成真实类对象。
3. `celery/apps/worker.py` 定义 `class Worker(WorkController)`；随后 `subclass_with_self` 用 `type(...)` 生成绑定 app 的子类，因此底层基类目标为 `celery.apps.worker.Worker`。

### medium_008 evidence chain
1. `celery/app/task.py` 里 `Task.Strategy = 'celery.worker.strategy:default'`。
2. `Task.start_strategy` 调用 `instantiate(self.Strategy, self, app, consumer, **kwargs)`。
3. `celery/utils/imports.py` 中 `instantiate` 直接调用 `symbol_by_name(name)(...)`，因此字符串最终解析到 `celery.worker.strategy.default` 可调用对象。

## 简短自审（最不确定 2 条）

1. `medium_007`：`Celery.Worker` 实际返回的是“动态生成子类”，我在 `ground_truth.direct_deps` 里落到其基类 `celery.apps.worker.Worker`。如果评测希望把“动态生成类型本身”也当作目标，这条会有口径偏差。  
2. `easy_008`：`celery.group` 在语义上常被当作 canvas primitive（类/可调用对象），我按源码定义落到 `celery.canvas.group` 类；若后续评测口径更偏“调用入口函数形态”，可能需要在问题文本里再限定“真实实现符号（类定义）”。
