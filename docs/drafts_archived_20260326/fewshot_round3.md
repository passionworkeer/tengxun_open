# Few-shot Round 3 Draft (Only Unpassed Items)

范围说明：本文件只处理 `B03 / B04 / E03`，不重写其它已通过条目。  
结构说明：答案继续使用兼容 schema：

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

## B03（round3 重写）

**回填空位**：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B03`  
**针对 objection 的修订点**：彻底移除 `_task_from_fun` 终点，改成“装饰器注册回调”机制题。

**环境前置条件**：
1. `celery.app.base` 被导入（该模块会导入 `celery.app.builtins`）。  
2. 关注的是导入阶段的注册行为，而不是 finalize 后的任务实例化。

**修订版问题**：为什么 `celery.app.builtins` 里的 `add_map_task` 等函数在没有被显式调用时，仍能在 app finalize 阶段执行？它们在导入阶段是通过哪个注册入口接入全局回调集合的？

**推理过程（>=4步）**：
1. `celery.app.base` 模块导入时会执行 `from . import backends, builtins`，触发 `celery.app.builtins` 顶层代码。
2. `builtins.py` 中多个函数（如 `add_map_task`）带有 `@connect_on_app_finalize` 装饰器。
3. 该装饰器来自 `celery._state.connect_on_app_finalize`，其行为是把 callback 加入 `_on_app_finalizers` 集合并返回 callback 本身。
4. 因为注册发生在模块导入阶段，这些函数不需要业务代码显式调用，后续 app finalize 时即可被统一取出执行。
5. 这类失败模式的关键不是“最终任务如何创建”，而是“隐式回调如何被预注册”。

**标准答案**：
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

**对抗的失效类型**：Type B（把装饰器的“导入即注册”副作用漏掉）。  
**为什么和现有 eval/已通过 few-shot 不重复**：  
1. eval `hard_001/hard_002/hard_014` 聚焦任务实例创建终点（`_task_from_fun`），本题完全不以该终点作答。  
2. eval `hard_003` 聚焦“谁执行回调”（`_announce_app_finalized`），本题聚焦“回调何时被注册进集合”（导入阶段副作用）。  
3. 与已通过 few-shot `B02` 的 pending 兑现路径不同，本题是 pre-finalize 的注册路径。

---

## B04（round3 重写）

**回填空位**：`docs/fewshot_examples.md` -> `Type B` -> `Few-shot B04`  
**针对 objection 的修订点**：不再把 `_task_from_fun` 作为终点，改成“Proxy 首次解引用触发 auto-finalize”机制题。

**环境前置条件**：
1. 使用 `@shared_task` 且未显式传 `name`。  
2. 首次访问该任务 Proxy 时，当前 app 仍可能未 finalized。

**修订版问题**：`@shared_task` 返回的 Proxy 在首次解引用时，哪个 app 级入口会被访问并触发 `auto-finalize`，从而让后续查表可用？

**推理过程（>=4步）**：
1. `shared_task` 返回 `Proxy(task_by_cons)`，真正求值时才执行 `task_by_cons()`。
2. `task_by_cons()` 先取当前 app，再构造 key：`name or app.gen_task_name(fun.__name__, fun.__module__)`。
3. 接着它访问 `app.tasks[key]`；关键点是 `app.tasks` 是 `Celery.tasks` 的 `cached_property`。
4. `Celery.tasks` 属性内部会调用 `self.finalize(auto=True)`，这是首次解引用时触发 finalize 的稳定入口。
5. finalize 结束后任务注册表稳定，`app.tasks[key]` 才能可靠返回任务对象。

**标准答案**：
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

**对抗的失效类型**：Type B（忽略 Proxy 首次求值触发的隐式 finalize 路径）。  
**为什么和现有 eval/已通过 few-shot 不重复**：  
1. eval `hard_001/hard_002` 问的是“谁创建任务实例”，本题问的是“谁触发 auto-finalize 让查表成立”。  
2. 与已通过 few-shot `B02` 不同：`B02` 关注 pending 队列兑现，本题关注 `shared_task Proxy -> tasks property` 触发点。  
3. 全题不以 `_task_from_fun` 作为答案终点，规避了现有 eval 主链泄漏。

---

## E03（round3 修订）

**回填空位**：`docs/fewshot_examples.md` -> `Type E` -> `Few-shot E03`  
**针对 objection 的修订点**：去掉 `expected_return` 等扩展字段；保留 schema 内答案，同时把 tuple 返回语义写在解释文本中。

**环境前置条件**：
1. 提供 `loader.override_backends = {'kv': 'celery.backends.redis:RedisBackend'}`。  
2. 调用入口为：`celery.app.backends.by_url('kv+redis://localhost/0', loader=loader)`。

**修订版问题**：在上述前置下，`by_url` 如何完成“URL scheme 拆分 -> alias 覆盖解析 -> 返回值保留 URL payload”的动态链路？

**推理过程（>=4步）**：
1. `by_url` 发现输入含 `://`，先取 scheme `kv+redis`，再按 `+` 拆成 `backend='kv'` 与 `url='redis://localhost/0'`。
2. `by_url` 调用 `by_name('kv', loader)` 解析 backend 类，不直接做类加载。
3. `by_name` 先合并 `dict(BACKEND_ALIASES, **loader.override_backends)`，因此 `kv` 会命中 override 映射。
4. `symbol_by_name` 把 `'kv'` 对应字符串解析为 `celery.backends.redis.RedisBackend`。
5. `by_url` 最终返回的是“类 + 拆分后的 URL”二元组，而不是已实例化 backend。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.backends.by_url",
      "celery.backends.redis.RedisBackend"
    ],
    "indirect_deps": [
      "celery.app.backends.by_name",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.app.backends.BACKEND_ALIASES"
    ]
  }
}
```

返回语义说明（非 schema 字段）：返回 `(resolved_backend_cls, rewritten_url)`，即 `(celery.backends.redis.RedisBackend, 'redis://localhost/0')`。  

**对抗的失效类型**：Type E（字符串 scheme 动态拆分与 alias 覆盖路径断裂）。  
**为什么和现有 eval/已通过 few-shot 不重复**：  
1. eval `medium_001` 只覆盖 `by_name('redis')` 静态 alias 命中；本题增加 `by_url` 的 `+` 拆分与 URL payload 保留语义。  
2. 本题依赖 `override_backends` 的运行时覆盖，不是固定内置 alias 场景。  
3. 与已通过 `E02/E04` 主题不同：`E02` 是 fixup 字符串执行链，`E04` 是 env+import 时序；本题是 URL 解析分支。

