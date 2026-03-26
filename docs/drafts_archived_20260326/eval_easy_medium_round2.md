# Eval Easy/Medium Round 2 Revision (Worker A)

仅处理 challenge reviewer 指定条目：`easy_005`、`easy_006`、`easy_008`、`medium_006`、`medium_007`。  
不重复 round1 已通过条目：`easy_007` / `medium_005` / `medium_008`。  
本稿继续使用最新 schema 核心字段：`id、difficulty、category、failure_type、implicit_level、question、source_file、source_commit、ground_truth.direct_deps、ground_truth.indirect_deps、ground_truth.implicit_deps、reasoning_hint、source_note`。

---

## easy_005（hold -> revised）

**Reviewer objection 回应**
- objection 1：`direct_deps` 不应落在 Proxy 对象本身。  
回应：本次将 direct 改为 `celery._state.get_current_app`，把 `Proxy` 下沉为 implicit。
- objection 2：`implicit_level=2` 偏低。  
回应：调高到 `implicit_level=3`，并显式补上 default app fallback 相关依赖。

**修订后 JSON**
```json
{
  "id": "easy_005",
  "difficulty": "easy",
  "category": "re_export_proxy",
  "failure_type": "Type B",
  "implicit_level": 3,
  "question": "在顶层懒加载 API 中，`celery.current_app` 这个 Proxy 在取值时会直接调用哪个函数来获得 app 对象？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery._state.get_current_app"
    ],
    "indirect_deps": [
      "celery._state._get_current_app"
    ],
    "implicit_deps": [
      "celery.local.Proxy",
      "celery._state.default_app",
      "celery.app.base.Celery"
    ]
  },
  "reasoning_hint": "`celery.__init__` 将 `current_app` 从 `celery._state` 暴露到顶层；`celery._state.current_app = Proxy(get_current_app)`，首次无默认 app 时由 `_get_current_app` 创建 fallback `Celery(...)`。",
  "source_note": "与现有 easy_001/easy_002 区分：本题关注 Proxy -> getter -> fallback app 的运行时链路，不是类/函数静态 re-export。"
}
```

**简短 rebuttal**
- 现在 direct 明确对应“取值时被调用的函数”，避免把 Proxy 本体当最终目标；同时 implicit 链覆盖了 reviewer 指出的 fallback 深度。

---

## easy_006（hold -> revised）

**Reviewer objection 回应**
- objection 1：direct 不应停在 Proxy，需落到最终数据提供点。  
回应：direct 调整为 `celery._state.get_current_task`，并把 `_task_stack.top` 放进 indirect，体现真实读取位置。
- objection 2：failure_type 与 implicit 拆分不一致。  
回应：改为 `Type B`（隐式运行时依赖），并补齐 `LocalStack` 相关 implicit。

**修订后 JSON**
```json
{
  "id": "easy_006",
  "difficulty": "easy",
  "category": "re_export_proxy",
  "failure_type": "Type B",
  "implicit_level": 3,
  "question": "在顶层懒加载 API 中，`celery.current_task` 在取值时直接调用哪个函数，并最终从哪个状态槽位读取当前任务？",
  "source_file": "celery/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery._state.get_current_task"
    ],
    "indirect_deps": [
      "celery._state._task_stack.top"
    ],
    "implicit_deps": [
      "celery.local.Proxy",
      "celery.utils.threads.LocalStack"
    ]
  },
  "reasoning_hint": "`celery.__init__` 暴露 `current_task`；`celery._state.current_task = Proxy(get_current_task)`，而 `get_current_task` 返回 `_task_stack.top`。",
  "source_note": "与 round1 版本差异：本次 direct 明确落到 getter 函数，避免把 Proxy 本体当终点。"
}
```

**简短 rebuttal**
- direct/indirect/implicit 现在按“调用函数 -> 数据槽位 -> 代理机制”拆开，语义更清晰，也更符合 Type B 的判定。

---

## easy_008（hold -> revised）

**Reviewer objection 回应**
- objection 1：问题表述未区分“类定义”与“可调用入口”。  
回应：问题明确为“类定义 FQN”，避免 callable 语义歧义。
- objection 2：`implicit_level=2` 偏高。  
回应：下调为 `implicit_level=1`，并保持 easy 定位。

**修订后 JSON**
```json
{
  "id": "easy_008",
  "difficulty": "easy",
  "category": "re_export",
  "failure_type": "Type C",
  "implicit_level": 1,
  "question": "从源码“类定义”角度看，顶层符号 `celery.group` 对应的真实类定义 FQN 是什么？",
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
  "reasoning_hint": "`celery.__init__` 通过 lazy re-export 暴露 `group`；`celery.canvas` 中对应定义为 `class group(Signature)`。",
  "source_note": "本题刻意限定为“类定义 FQN”，不讨论运行时 callable 入口，避免与函数式调用语义混淆。"
}
```

**简短 rebuttal**
- 这版把问题边界收紧到“类定义”，并把 implicit_level 调整到与一跳 re-export 链一致的 1。

---

## medium_006（hold -> revised）

**Reviewer objection 回应**
- objection 1：direct/indirect 对“实例化触发点”表达不清。  
回应：direct 同时给出触发点 `Celery._get_backend` 与最终类 `RPCBackend`，并在 hint 中明确实例化发生在 `_get_backend` 的 `return backend(app=self, url=url)`。
- objection 2：与 `medium_001` 可能重叠，implicit_level 偏高。  
回应：将 `implicit_level` 下调为 2，并在 `source_note` 明确差异是 `by_url` 的 scheme 拆分与 `(cls, url)` 返回路径，而非 `by_name('redis')` 直查。

**修订后 JSON**
```json
{
  "id": "medium_006",
  "difficulty": "medium",
  "category": "backend_url_alias",
  "failure_type": "Type E",
  "implicit_level": 2,
  "question": "在 `Celery._get_backend` 调用路径里，当 `result_backend='rpc://...'` 时，哪个 backend 类会被解析并由该方法实例化？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._get_backend",
      "celery.backends.rpc.RPCBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_url",
      "celery.app.backends.by_name"
    ],
    "implicit_deps": [
      "celery.app.backends.BACKEND_ALIASES",
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`_get_backend` 调 `backends.by_url(...)` 并最终执行 `return backend(app=self, url=url)`；`by_url` 先拆 `rpc://` 的 scheme，再进入 `by_name`，通过 alias+`symbol_by_name` 定位 `RPCBackend`。",
  "source_note": "与 medium_001 的差异：medium_001 是 `by_name('redis')` 直查；本题必须经过 `by_url` 的 URL 解析与 `(cls, url)` 返回路径。"
}
```

**简短 rebuttal**
- 这次把“解析+实例化”两部分都绑定到可追踪节点，且明确区分了与 `medium_001` 的入口差异，避免重复。

---

## medium_007（reject -> 重写）

**处理决策**
- 选择“彻底重写成一个可成立的新样本”，不沿用原 `subclass_with_self` 版本。

**为什么重写**
- 原题核心冲突在于“最终返回对象是动态生成子类”，而静态 FQN 不好直接稳定表达，容易持续在 direct 口径上被 challenge。
- 新题改为可稳定落地的 fallback + loader alias 解析链，仍覆盖中等难度隐式链路，但目标符号单一、可复核。

**重写后 JSON（保留 id=medium_007）**
```json
{
  "id": "medium_007",
  "difficulty": "medium",
  "category": "fallback_loader_alias",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "当线程中没有 current app 且未设置 `CELERY_LOADER` 时，首次访问 `celery.current_app.loader` 最终会实例化哪个 Loader 类？",
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
      "celery.local.Proxy",
      "celery.loaders.LOADER_ALIASES",
      "celery.utils.imports.symbol_by_name"
    ]
  },
  "reasoning_hint": "`celery.current_app` 是 `Proxy(get_current_app)`；无默认 app 时 `_get_current_app` 会创建 `Celery(..., loader=os.environ.get('CELERY_LOADER') or 'default')`；随后 `app.loader` 经 `get_loader_cls('default')` + `symbol_by_name` 解析到 `celery.loaders.default.Loader` 并实例化。",
  "source_note": "与 easy_003 区分：easy_003 直接问 `get_loader_cls('default')`；本题入口是 `current_app` fallback 运行时链。与 medium_005 区分：medium_005 走 `_get_default_loader -> app:AppLoader` 默认分支。"
}
```

**简短 rebuttal**
- 新版 `medium_007` 不再依赖“动态子类 FQN”这一争议点，最终目标单一且可通过 `_state.py` + `base.py` + `loaders/__init__.py` 稳定复核。

