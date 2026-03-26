# Eval Hard Round 1 (Worker B)

> 已按最新 `docs/dataset_schema.md` 调整：以下草稿统一使用新 schema 核心字段  
> `id, difficulty, category, failure_type, implicit_level, question, source_file, source_commit, ground_truth.direct_deps, ground_truth.indirect_deps, ground_truth.implicit_deps, reasoning_hint, source_note`。

## 总表（8 条新增 Hard 草稿）

| id | category | failure_type | implicit_level | source_file | question 摘要 |
|---|---|---|---:|---|---|
| celery_hard_013 | shared_task_proxy_autofinalize | Type B | 5 | celery/app/__init__.py | shared_task 的 Proxy 首次取值时由谁触发 finalize 回调链 |
| celery_hard_014 | builtin_finalize_registration | Type B | 4 | celery/app/builtins.py | celery.backend_cleanup 最终由哪个方法创建任务实例 |
| celery_hard_015 | autodiscovery_signal_chain | Type B | 4 | celery/app/base.py | force=False 的 autodiscover_tasks 真正由谁触发执行 |
| celery_hard_016 | autodiscovery_fixup_import | Type E | 5 | celery/app/base.py | fixup 产出的包名最终由哪个函数执行 importlib 导入 |
| celery_hard_017 | fixup_string_entry_resolution | Type E | 4 | celery/app/base.py | builtin_fixups 字符串入口最终解析到哪个真实函数 |
| celery_hard_018 | django_task_cls_string_resolution | Type E | 5 | celery/fixups/django.py | Django fixup 生效后 app.Task 最终基类解析到哪里 |
| celery_hard_019 | loader_smart_import_fallback | Type E | 4 | celery/loaders/base.py | config_from_object 字符串回退分支最终由谁解析符号 |
| celery_hard_020 | default_app_loader_alias_chain | Type E | 4 | celery/_state.py | fallback app 的 `loader='default'` 最终实例化哪个 Loader |

## 逐条 JSON 草稿

### celery_hard_013

```json
{
  "id": "celery_hard_013",
  "difficulty": "hard",
  "category": "shared_task_proxy_autofinalize",
  "failure_type": "Type B",
  "implicit_level": 5,
  "question": "`celery.app.shared_task` 返回的 Proxy 在首次按任务名取值时，会通过哪个关键方法触发 finalize 并执行注册回调链？",
  "source_file": "celery/app/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.finalize"
    ],
    "indirect_deps": [
      "celery._state._announce_app_finalized"
    ],
    "implicit_deps": [
      "celery._state.connect_on_app_finalize",
      "celery.app.base.Celery._task_from_fun"
    ]
  },
  "reasoning_hint": "`shared_task` 返回的 `task_by_cons` 会访问 `current_app.tasks`；`tasks` 属性会自动 `finalize(auto=True)`，并在 finalize 里执行 finalizer 回调，最终触发 `_task_from_fun`。",
  "source_note": "See celery/app/__init__.py:24-71, celery/app/base.py:1517-1524 and 654-670, celery/_state.py:43-52."
}
```

### celery_hard_014

```json
{
  "id": "celery_hard_014",
  "difficulty": "hard",
  "category": "builtin_finalize_registration",
  "failure_type": "Type B",
  "implicit_level": 4,
  "question": "`celery.backend_cleanup` 这个内置任务在 app finalize 阶段最终由哪个方法完成实际 Task 实例创建？",
  "source_file": "celery/app/builtins.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery.app.builtins.add_backend_cleanup_task",
      "celery.app.base.Celery.task"
    ],
    "implicit_deps": [
      "celery._state.connect_on_app_finalize",
      "celery._state._announce_app_finalized"
    ]
  },
  "reasoning_hint": "`add_backend_cleanup_task` 先被 `connect_on_app_finalize` 注册，finalize 时执行该回调；回调内部的 `@app.task(..., lazy=False)` 立即落到 `Celery._task_from_fun` 创建任务。",
  "source_note": "See celery/app/builtins.py:12-23, celery/_state.py:43-52, celery/app/base.py:654-670 and 551-563."
}
```

### celery_hard_015

```json
{
  "id": "celery_hard_015",
  "difficulty": "hard",
  "category": "autodiscovery_signal_chain",
  "failure_type": "Type B",
  "implicit_level": 4,
  "question": "`app.autodiscover_tasks(..., force=False)` 不会立即扫描；后续真正触发 `_autodiscover_tasks` 执行的调用点是哪个函数？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.base.BaseLoader.import_default_modules"
    ],
    "indirect_deps": [
      "celery.app.base.Celery._autodiscover_tasks",
      "celery.loaders.base.BaseLoader.init_worker"
    ],
    "implicit_deps": [
      "celery.signals.import_modules",
      "vine.starpromise"
    ]
  },
  "reasoning_hint": "`autodiscover_tasks(force=False)` 只注册 `signals.import_modules` 回调；worker 启动路径调用 `loader.init_worker -> import_default_modules -> signals.import_modules.send` 时才真正触发 `_autodiscover_tasks`。",
  "source_note": "See celery/app/base.py:819-824, celery/loaders/base.py:97-111, celery/worker/worker.py:90-95."
}
```

### celery_hard_016

```json
{
  "id": "celery_hard_016",
  "difficulty": "hard",
  "category": "autodiscovery_fixup_import",
  "failure_type": "Type E",
  "implicit_level": 5,
  "question": "当 `packages=None` 时，`Celery._autodiscover_tasks_from_fixups` 收集到的包名最终由哪个函数执行真实 `importlib.import_module` 导入？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.base.find_related_module"
    ],
    "indirect_deps": [
      "celery.app.base.Celery._autodiscover_tasks_from_fixups",
      "celery.fixups.django.DjangoFixup.autodiscover_tasks",
      "celery.loaders.base.autodiscover_tasks"
    ],
    "implicit_deps": [
      "importlib.import_module"
    ]
  },
  "reasoning_hint": "fixup 先给出包名列表，再经 `loader.autodiscover_tasks -> loaders.base.autodiscover_tasks -> find_related_module`，最终在 `find_related_module` 内调用 `importlib.import_module`。",
  "source_note": "See celery/app/base.py:825-841, celery/fixups/django.py:121-123, celery/loaders/base.py:218-221 and 239-270."
}
```

### celery_hard_017

```json
{
  "id": "celery_hard_017",
  "difficulty": "hard",
  "category": "fixup_string_entry_resolution",
  "failure_type": "Type E",
  "implicit_level": 4,
  "question": "默认 `builtin_fixups` 中字符串入口 `'celery.fixups.django:fixup'` 在 app 初始化时最终解析到哪个真实函数？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.fixups.django.fixup"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.__init__",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.fixups.django.DjangoFixup.install"
    ]
  },
  "reasoning_hint": "`Celery.__init__` 会遍历 `self.fixups` 并执行 `symbol_by_name(fixup)(self)`；默认字符串 fixup 入口会解析到 `celery.fixups.django.fixup`。",
  "source_note": "See celery/app/base.py:79-80 and 407-410, celery/fixups/django.py:52-63."
}
```

### celery_hard_018

```json
{
  "id": "celery_hard_018",
  "difficulty": "hard",
  "category": "django_task_cls_string_resolution",
  "failure_type": "Type E",
  "implicit_level": 5,
  "question": "在 Django fixup 生效且未自定义 `task_cls` 时，`app.Task` 的最终基类会解析到哪个真实类？",
  "source_file": "celery/fixups/django.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.contrib.django.task.DjangoTask"
    ],
    "indirect_deps": [
      "celery.fixups.django.DjangoFixup.install",
      "celery.app.base.Celery.Task",
      "celery.app.base.Celery.create_task_cls",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`DjangoFixup.install` 在条件满足时把 `app.task_cls` 改为字符串 `'celery.contrib.django.task:DjangoTask'`；`app.Task` 访问时经 `create_task_cls/subclass_with_self` 用 `symbol_by_name` 解析该字符串。",
  "source_note": "See celery/fixups/django.py:84-86, celery/app/base.py:1373-1375, 1250-1254, 1276, celery/contrib/django/task.py:8."
}
```

### celery_hard_019

```json
{
  "id": "celery_hard_019",
  "difficulty": "hard",
  "category": "loader_smart_import_fallback",
  "failure_type": "Type E",
  "implicit_level": 4,
  "question": "`BaseLoader.config_from_object` 接收不含冒号且不能被直接当模块导入的字符串（如 `pkg.mod.CONF`）时，最终由哪个函数完成符号解析？",
  "source_file": "celery/loaders/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.utils.imports.symbol_by_name"
    ],
    "indirect_deps": [
      "celery.loaders.base.BaseLoader.config_from_object",
      "celery.loaders.base.BaseLoader._smart_import"
    ],
    "implicit_deps": [
      "celery.utils.imports.import_from_cwd",
      "importlib.import_module"
    ]
  },
  "reasoning_hint": "`config_from_object` 对字符串调用 `_smart_import`；无冒号路径先尝试 `imp(path)`（底层经 importlib），失败后回退到 `symbol_by_name(path, imp=imp)`。",
  "source_note": "See celery/loaders/base.py:119-123 and 132-145, celery/utils/imports.py:96-106."
}
```

### celery_hard_020

```json
{
  "id": "celery_hard_020",
  "difficulty": "hard",
  "category": "default_app_loader_alias_chain",
  "failure_type": "Type E",
  "implicit_level": 4,
  "question": "`_state._get_current_app` 创建 fallback app 时使用 `loader='default'`；当首次访问 `app.loader` 时，最终会实例化哪个具体 Loader 类？",
  "source_file": "celery/_state.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.default.Loader"
    ],
    "indirect_deps": [
      "celery._state._get_current_app",
      "celery.app.base.Celery.loader",
      "celery.loaders.get_loader_cls"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name",
      "celery.utils.imports.import_from_cwd"
    ]
  },
  "reasoning_hint": "`_get_current_app` 懒创建 `Celery(... loader='default')`；`app.loader` 属性通过 `get_loader_cls(self.loader_cls)` 走 alias 解析，`default -> celery.loaders.default:Loader`。",
  "source_note": "See celery/_state.py:92-100, celery/app/base.py:1501-1504, celery/loaders/__init__.py:10-18."
}
```

## 逐条 Evidence Chain（每条 >= 4 步）

### celery_hard_013 evidence chain

1. `shared_task.__inner` 返回 `Proxy(task_by_cons)`，`task_by_cons` 里访问 `app.tasks[...]`（`celery/app/__init__.py:64-71`）。
2. `Celery.tasks` 是 `cached_property`，访问时先 `self.finalize(auto=True)`（`celery/app/base.py:1517-1524`）。
3. `finalize` 内部调用 `_announce_app_finalized(self)`（`celery/app/base.py:654-666`）。
4. `_announce_app_finalized` 遍历 `connect_on_app_finalize` 收集的回调并执行（`celery/_state.py:43-52`）；shared_task 之前注册的 lambda 回调会调用 `app._task_from_fun`（`celery/app/__init__.py:54-56`）。
5. 因此 Proxy 首次解析任务对象时，链路关键触发点是 `Celery.finalize`，并隐式触发 shared_task 注册回调。

为何属于 hard：装饰器闭包 + Proxy 延迟求值 + 属性副作用（auto-finalize）叠加，必须跨文件拼接运行时链路才能得到结论。

### celery_hard_014 evidence chain

1. `add_backend_cleanup_task` 被 `@connect_on_app_finalize` 装饰，回调被登记到全局 finalizer 集（`celery/app/builtins.py:12-13`, `celery/_state.py:43-46`）。
2. 回调函数内部定义 `@app.task(name='celery.backend_cleanup', shared=False, lazy=False)`（`celery/app/builtins.py:20-23`）。
3. app finalize 时调用 `_announce_app_finalized`，触发该回调执行（`celery/app/base.py:654-666`, `celery/_state.py:49-52`）。
4. `Celery.task` 在 `lazy=False` 分支直接走 `self._task_from_fun(...)`（`celery/app/base.py:551-563`），完成任务实例创建与注册。
5. 所以内置任务 `celery.backend_cleanup` 的实例创建最终落在 `Celery._task_from_fun`。

为何属于 hard：并非显式 import 可见，而是“模块导入副作用 + finalize 时机 + 装饰器参数分支（lazy=False）”共同决定。

### celery_hard_015 evidence chain

1. `app.autodiscover_tasks(..., force=False)` 不立即执行扫描，而是向 `signals.import_modules` 注册 `starpromise(self._autodiscover_tasks, ...)`（`celery/app/base.py:819-824`）。
2. worker 启动时调用 `self.app.loader.init_worker()`（`celery/worker/worker.py:90-95`）。
3. `BaseLoader.init_worker` 调用 `import_default_modules`（`celery/loaders/base.py:107-111`）。
4. `import_default_modules` 先执行 `signals.import_modules.send(sender=self.app)`，从而触发前面挂上的 autodiscover 回调（`celery/loaders/base.py:97-105`）。
5. 因此 lazy autodiscover 的真正触发点是 `BaseLoader.import_default_modules`。

为何属于 hard：入口函数本身不执行核心逻辑，真实执行点发生在另一路 worker 启动链，属于典型“延迟回调触发点漂移”。

### celery_hard_016 evidence chain

1. `Celery._autodiscover_tasks` 在 `packages` 为空时走 `_autodiscover_tasks_from_fixups`（`celery/app/base.py:825-829`）。
2. `_autodiscover_tasks_from_fixups` 从 fixup 对象上收集 `autodiscover_tasks()` 返回的包名（`celery/app/base.py:836-841`）。
3. Django fixup 的 `autodiscover_tasks` 返回 Django app config 名称列表（`celery/fixups/django.py:121-123`）。
4. 这些包名交给 `loader.autodiscover_tasks`，再进入 `loaders.base.autodiscover_tasks`（`celery/app/base.py:830-834`, `celery/loaders/base.py:218-221`, `239-247`）。
5. 最终每个包由 `find_related_module` 调用 `importlib.import_module(package)` / `importlib.import_module(f'{package}.{related_name}')` 实际导入（`celery/loaders/base.py:251-270`）。

为何属于 hard：这条链跨 fixup、loader、全局函数与 importlib，且起点是“包名列表”而非静态符号，属于字符串入口 + 动态导入组合。

### celery_hard_017 evidence chain

1. `BUILTIN_FIXUPS` 定义了字符串入口 `'celery.fixups.django:fixup'`（`celery/app/base.py:79-80`）。
2. `Celery.__init__` 将 `self.fixups` 设为 builtin 集合，并执行 `self._fixups = [symbol_by_name(fixup)(self) for fixup in self.fixups]`（`celery/app/base.py:407-410`）。
3. `symbol_by_name` 将字符串解析为真实可调用对象，目标是 `celery.fixups.django.fixup`（`celery/fixups/django.py:52`）。
4. 解析后函数被立即调用（`(self)`），在条件满足时返回 `DjangoFixup(app).install()`（`celery/fixups/django.py:55-63`）。
5. 因此该字符串入口最终解析到的真实函数是 `celery.fixups.django.fixup`。

为何属于 hard：答案不是显式 import 给出，而是“字符串配置 -> symbol_by_name -> 条件执行”三段式动态链路。

### celery_hard_018 evidence chain

1. Django fixup 安装时，如果没有用户自定义 task 基类，执行 `self.app.task_cls = 'celery.contrib.django.task:DjangoTask'`（`celery/fixups/django.py:84-86`）。
2. 访问 `app.Task` 时会走 `create_task_cls()`（`celery/app/base.py:1373-1375`）。
3. `create_task_cls` 调用 `subclass_with_self(self.task_cls, ...)`（`celery/app/base.py:1250-1254`）。
4. `subclass_with_self` 首先做 `Class = symbol_by_name(Class)`，把字符串解析成真实类（`celery/app/base.py:1276`）。
5. 目标类定义在 `celery.contrib.django.task.DjangoTask`（`celery/contrib/django/task.py:8`）。

为何属于 hard：依赖 fixup 条件副作用动态改写 `task_cls`，再在后续属性访问时延迟解析，属于多阶段字符串入口解析。

### celery_hard_019 evidence chain

1. `config_from_object` 若收到字符串，会调用 `_smart_import(obj, imp=self.import_from_cwd)`（`celery/loaders/base.py:119-123`）。
2. `_smart_import` 对“无冒号字符串”先尝试 `imp(path)`（`celery/loaders/base.py:139-143`）。
3. 这里 `imp` 来自 `import_from_cwd`，其底层最终调用 `import_module`（`celery/loaders/base.py:90-95`, `celery/utils/imports.py:96-106`）。
4. 若 `imp(path)` 抛 `ImportError`，回退到 `symbol_by_name(path, imp=imp)`（`celery/loaders/base.py:144-145`）。
5. 因而回退分支里真正完成符号解析的是 `celery.utils.imports.symbol_by_name`。

为何属于 hard：这不是单一路径，而是“先模块导入、失败再符号解析”的双分支动态流程，容易被模型误判为固定路径。

### celery_hard_020 evidence chain

1. `_state._get_current_app` 在 `default_app is None` 时懒创建 `Celery('default', ..., loader=os.environ.get('CELERY_LOADER') or 'default')`（`celery/_state.py:92-99`）。
2. `app.loader` 属性首次访问时执行 `get_loader_cls(self.loader_cls)(app=self)`（`celery/app/base.py:1501-1504`）。
3. `get_loader_cls` 用 `LOADER_ALIASES` + `symbol_by_name(..., imp=import_from_cwd)` 解析 loader 字符串（`celery/loaders/__init__.py:10-18`）。
4. alias `'default'` 映射到 `'celery.loaders.default:Loader'`（`celery/loaders/__init__.py:10-13`）。
5. 因此最终实例化类是 `celery.loaders.default.Loader`。

为何属于 hard：入口位于全局状态惰性初始化，解析发生在另一个属性路径，还叠加 alias 与字符串类名映射。

## 简短自审（最可能被 reviewer 打回的 3 条）

1. `celery_hard_015`：可能被质疑“direct_deps 应该填 `_autodiscover_tasks` 而不是 `import_default_modules`”，因为题目问触发点，字段口径偏“执行触发函数”而非“被触发函数”。
2. `celery_hard_018`：依赖 Django fixup 生效前提（`DJANGO_SETTINGS_MODULE`、Django 可导入），如果 reviewer 要求“无环境前提的确定链”，可能要求降级或补条件描述。
3. `celery_hard_020`：虽然是惰性 + alias + 字符串解析链，但 reviewer 可能认为链路长度不够“硬”，倾向将其降到 medium。
