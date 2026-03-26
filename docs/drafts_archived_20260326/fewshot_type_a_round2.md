## Few-shot Type A (长链上下文) - Round 2 Draft

> 本稿仅重写 `A01` / `A02`，并按当前 `external/celery` 源码口径修正。  
> 结构与 `docs/fewshot_examples.md` 一致：问题、环境前置条件、推理过程、答案（仅 `ground_truth` 三字段）。

---

### Few-shot A01: Click CLI worker 启动长链（新版）

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
      "celery.app.base.Celery.subclass_with_self",
      "celery.apps.worker.Worker"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  }
}
```

---

### Few-shot A02: `current_app.tasks` 首访触发 finalize 长链（替换版）

**问题**: 在未显式创建全局 app 的前提下，首次访问 `celery.current_app.tasks` 时，如何先走 fallback app 创建，再触发 `auto-finalize`？

**环境前置条件**:
1. 进程启动后尚未显式调用 `Celery(...)` 绑定全局 app。  
2. 首次访问的是 `celery.current_app.tasks`（不是仅访问 `celery.current_app`）。  
3. `autofinalize=True`（默认配置）。  

**推理过程**:
1. `celery.current_app` 是 `celery._state.current_app = Proxy(get_current_app)`；首次取值会进入 `get_current_app`。  
2. `get_current_app` 默认指向 `_get_current_app`；若 `default_app is None`，则创建 `Celery('default', fixups=[], set_as_current=False, loader=...)` 并写入 `set_default_app(...)`。  
3. 到这一步只完成 fallback app 解析，不会仅因访问 `current_app` 本身触发 finalize。  
4. 当继续访问 `.tasks` 时，命中 `Celery.tasks` cached_property；其内部显式执行 `self.finalize(auto=True)`。  
5. `finalize(auto=True)` 将 app 标记 finalized，并执行 `_announce_app_finalized(self)` 与 pending 评估流程（存在 pending 时会被 drain），最后返回任务注册表。  

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.tasks",
      "celery.app.base.Celery.finalize"
    ],
    "indirect_deps": [
      "celery._state.get_current_app",
      "celery._state._get_current_app",
      "celery._state.set_default_app",
      "celery._state._announce_app_finalized"
    ],
    "implicit_deps": [
      "celery.local.Proxy",
      "celery._state.default_app",
      "celery.local.maybe_evaluate"
    ]
  }
}
```
