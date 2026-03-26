# Eval Hard Round 2 (Challenge Fixes)

> 本轮只修订 challenge 指定的 4 条：`celery_hard_013`、`celery_hard_015`、`celery_hard_018`、`celery_hard_020`。  
> 字段口径已对齐最新 `docs/dataset_schema.md`。

---

## celery_hard_013

### Reviewer objection 回应

- 已把“首次触发点”从单一 `Celery.finalize` 调整为 `Celery.tasks -> Celery.finalize` 组合，避免 direct 与问题错位。  
- `implicit_level` 从 5 下调到 4，匹配“属性访问触发 finalize + 回调执行”复杂度。

### 修订后 JSON

```json
{
  "id": "celery_hard_013",
  "difficulty": "hard",
  "category": "shared_task_proxy_autofinalize",
  "failure_type": "Type B",
  "implicit_level": 4,
  "question": "`celery.app.shared_task` 返回的 Proxy 首次解析任务对象时，触发 finalize 回调链的关键入口符号是什么？",
  "source_file": "celery/app/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.tasks",
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
  "reasoning_hint": "shared_task 的 Proxy 闭包会访问 `current_app.tasks`；`tasks` 属性内部触发 `finalize(auto=True)`，再通过 `_announce_app_finalized` 执行已登记的 finalizer，最终落到 `_task_from_fun`。",
  "source_note": "See celery/app/__init__.py:50-71, celery/app/base.py:1517-1524 and 654-666, celery/_state.py:43-52."
}
```

### Evidence Chain（补强）

1. `shared_task.__inner` 返回 `Proxy(task_by_cons)`，`task_by_cons` 中直接访问 `app.tasks[...]`（`celery/app/__init__.py:64-71`）。  
2. `Celery.tasks` 属性访问会执行 `self.finalize(auto=True)`（`celery/app/base.py:1517-1524`）。  
3. `finalize` 在首次执行时调用 `_announce_app_finalized(self)`（`celery/app/base.py:654-666`）。  
4. `_announce_app_finalized` 遍历 `connect_on_app_finalize` 登记回调并调用（`celery/_state.py:43-52`）。  
5. shared_task 之前登记的 finalize 回调是 `lambda app: app._task_from_fun(fun, **options)`（`celery/app/__init__.py:54-56`），完成任务注册。

### 简短 Rebuttal

这条样本核心不是“最终注册函数是什么”，而是“Proxy 首次解引用时谁触发 finalize 链”；因此 direct 以 `tasks/finalize` 为主，`_task_from_fun` 下沉到 implicit 更符合问题语义。

---

## celery_hard_015

### Reviewer objection 回应

- 已把 `Celery._autodiscover_tasks` 调整为 direct 目标；`import_default_modules` 改为触发路径中的 indirect。  
- 补上 `signals.import_modules.send -> receiver(...)` 执行闭环，避免链路停在 loader 层。

### 修订后 JSON

```json
{
  "id": "celery_hard_015",
  "difficulty": "hard",
  "category": "autodiscovery_signal_chain",
  "failure_type": "Type B",
  "implicit_level": 4,
  "question": "在 `app.autodiscover_tasks(..., force=False)` 的 lazy 路径下，真正被触发执行的目标函数是什么，以及它由哪条调用链触发？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._autodiscover_tasks"
    ],
    "indirect_deps": [
      "celery.loaders.base.BaseLoader.init_worker",
      "celery.loaders.base.BaseLoader.import_default_modules",
      "celery.utils.dispatch.signal.Signal.send"
    ],
    "implicit_deps": [
      "celery.signals.import_modules",
      "vine.starpromise"
    ]
  },
  "reasoning_hint": "force=False 时只注册 `starpromise(self._autodiscover_tasks, ...)` 为 `import_modules` receiver；worker 启动经 `init_worker -> import_default_modules -> Signal.send` 才实际调用该 receiver 并执行 `_autodiscover_tasks`。",
  "source_note": "See celery/app/base.py:819-825, celery/loaders/base.py:97-111, celery/utils/dispatch/signal.py:258-280, celery/worker/worker.py:90-95."
}
```

### Evidence Chain（补强）

1. `autodiscover_tasks(force=False)` 不执行扫描，仅连接 receiver：`signals.import_modules.connect(starpromise(self._autodiscover_tasks, ...), sender=self)`（`celery/app/base.py:819-824`）。  
2. worker 初始化路径调用 `self.app.loader.init_worker()`（`celery/worker/worker.py:90-95`）。  
3. `BaseLoader.init_worker` 调用 `import_default_modules`（`celery/loaders/base.py:107-111`）。  
4. `import_default_modules` 里执行 `signals.import_modules.send(sender=self.app)`（`celery/loaders/base.py:97-99`）。  
5. `Signal.send` 会遍历 live receivers 并逐个执行 `response = receiver(...)`（`celery/utils/dispatch/signal.py:258-280`），从而触发 `starpromise` 封装的 `_autodiscover_tasks`。

### 简短 Rebuttal

修订后 direct 明确命中被触发函数 `_autodiscover_tasks`，trigger 链则完整落在 indirect + implicit，字段分层已与问题语义对齐。

---

## celery_hard_018

### Reviewer objection 回应

- 已在 question/source_note 明确前置条件：`DJANGO_SETTINGS_MODULE` 已设置、`django` 可导入、且 `app.loader_cls` 不含 `'django'`。  
- implicit 增加环境与 settings 解析依赖，避免只剩 `symbol_by_name` 一条。

### 修订后 JSON

```json
{
  "id": "celery_hard_018",
  "difficulty": "hard",
  "category": "django_task_cls_string_resolution",
  "failure_type": "Type E",
  "implicit_level": 5,
  "question": "在满足 Django fixup 前置条件（`DJANGO_SETTINGS_MODULE` 已设置、`django` 可导入、且 `app.loader_cls` 不含 `django`）且未自定义 `task_cls` 时，`app.Task` 的最终基类解析到哪个真实类？",
  "source_file": "celery/fixups/django.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.contrib.django.task.DjangoTask"
    ],
    "indirect_deps": [
      "celery.fixups.django.fixup",
      "celery.fixups.django.DjangoFixup.install",
      "celery.app.base.Celery.Task",
      "celery.app.base.Celery.create_task_cls",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "os.environ.get",
      "celery.utils.imports.symbol_by_name",
      "django.conf.settings"
    ]
  },
  "reasoning_hint": "fixup 先基于环境条件决定是否安装；安装后把 `app.task_cls` 改写为字符串 `celery.contrib.django.task:DjangoTask`，随后在 `app.Task` 访问时经 `subclass_with_self` 调用 `symbol_by_name` 解析为真实类。",
  "source_note": "Conditional sample: only valid when fixup preconditions hold. If preconditions fail, this case should not be integrated as an unconditional eval item."
}
```

### Evidence Chain（补强）

1. `fixup` 先检查 `SETTINGS_MODULE = os.environ.get('DJANGO_SETTINGS_MODULE')`，并要求 `'django' not in app.loader_cls.lower()`（`celery/fixups/django.py:52-56`）。  
2. 条件满足且 `import django` 成功后，执行 `DjangoFixup(app).install()`（`celery/fixups/django.py:57-63`）。  
3. `install` 内在未自定义 task_cls 时执行 `self.app.task_cls = 'celery.contrib.django.task:DjangoTask'`（`celery/fixups/django.py:84-86`）。  
4. 后续访问 `app.Task` 会走 `create_task_cls -> subclass_with_self(self.task_cls, ...)`（`celery/app/base.py:1373-1375`, `1250-1254`）。  
5. `subclass_with_self` 中 `Class = symbol_by_name(Class)` 将字符串解析到真实类 `celery.contrib.django.task.DjangoTask`（`celery/app/base.py:1276`; `celery/contrib/django/task.py:8`）。

### 简短 Rebuttal

本条保留 hard，但改成“显式条件样本”：只有前置条件成立才入库；这样既保留 Type E 字符串入口价值，也避免不可复核。

---

## celery_hard_020（建议降级）

### Reviewer objection 回应

- 接受 challenge 结论：该链复杂度更接近 medium。  
- 已降级为 `difficulty=medium`、`implicit_level=3`，并把“实例化触发点”补入 direct。

### 修订后 JSON

```json
{
  "id": "celery_hard_020",
  "difficulty": "medium",
  "category": "default_app_loader_alias_chain",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "`_state._get_current_app` 懒创建 fallback app 后，首次访问 `app.loader` 时由哪个触发点完成 loader 类解析并实例化？",
  "source_file": "celery/_state.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.loader",
      "celery.loaders.default.Loader"
    ],
    "indirect_deps": [
      "celery._state._get_current_app",
      "celery.loaders.get_loader_cls"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name",
      "celery.utils.imports.import_from_cwd"
    ]
  },
  "reasoning_hint": "`_get_current_app` 仅设置 `loader='default'`；真正触发解析的是 `Celery.loader` 属性访问，内部经 `get_loader_cls('default')` alias + `symbol_by_name` 解析后实例化 `celery.loaders.default.Loader`。",
  "source_note": "Round2 decision: downgrade from hard to medium due to limited implicit depth (alias resolution + lazy property access)."
}
```

### Evidence Chain（补强）

1. `_get_current_app` 在 `default_app is None` 时创建 `Celery(..., loader=os.environ.get('CELERY_LOADER') or 'default')`（`celery/_state.py:92-99`）。  
2. 真正实例化 loader 发生在 `Celery.loader` 属性：`return get_loader_cls(self.loader_cls)(app=self)`（`celery/app/base.py:1501-1504`）。  
3. `get_loader_cls` 对 `loader='default'` 使用 `LOADER_ALIASES` 解析（`celery/loaders/__init__.py:10-18`）。  
4. alias `'default'` 映射到 `'celery.loaders.default:Loader'`（`celery/loaders/__init__.py:10-13`）。  
5. 经 `symbol_by_name(..., imp=import_from_cwd)` 解析并实例化为 `celery.loaders.default.Loader`。

### 简短 Rebuttal

这条链有字符串 alias 与惰性属性访问，但缺少更深层回调/动态分支，降到 medium 更稳；建议后续集成时同步重命名 ID（如 `celery_medium_0xx`）。

