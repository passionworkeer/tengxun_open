## Few-shot Type A (长链上下文) — Round 1 Draft

> 目标：提供 2 条长链上下文 few-shot，用于教模型“分段定位 + 逐跳追踪”，避免直接猜终点 FQN。均基于 `fewshot_examples.md` 的结构与 schema。

---

### Few-shot A01: CLI worker 启动长链

**问题**  
当执行 `celery -A proj worker` 时，从命令入口到 Worker 实例化的关键调用链是什么？请标出最终负责启动 worker 的可调用对象。

**环境前置条件**  
- 命令行调用：`celery -A proj worker`，未自定义子命令。
- `proj` 可导入且含 `celery = Celery('proj')`。
- 使用默认 `CELERY_LOADER` 与默认 worker 选项（无 `--loader` 等改写）。

**推理链（示例 5 步，可压缩为 ≥4 步）**  
1. `celery/bin/celery.py:main()` 解析 argv，将 `worker` 子命令分派给 `celery/bin/worker.py:main`.  
2. `celery/bin/worker.py:main` 构造 `WorkerCommand(app=self.app)`，进入 `run_from_argv`。  
3. `WorkerCommand.run_from_argv` 内部调用 `self.execute_from_commandline` → `WorkerCommand.run`。  
4. `run` 构造 `worker = self.app.Worker(**kwargs)`（`self.app` 已在 CLI 创建），这里触发 `Celery.Worker` 缓存属性。  
5. `Celery.Worker` 缓存属性调用 `self.subclass_with_self('celery.apps.worker:Worker')`，最终返回绑定 app 的 Worker 子类并实例化，启动 worker。

**标准答案（ground_truth）**  
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.apps.worker.Worker"
    ],
    "indirect_deps": [
      "celery.bin.worker.WorkerCommand.run",
      "celery.app.base.Celery.Worker",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name"
    ]
  }
}
```

**为何适合 few-shot（长链分段示范）**  
- 涉及 CLI 解析 → Command 对象 → app 缓存属性 → 动态 subclass 4+ 跳，终点是绑定后的 Worker 子类，不是单一静态 FQN。  
- 运行时行为依赖 argv 与 app 上下文，直接 eval 难以稳定复现；few-shot 可教模型按段确认“入口解析/命令分派/实例化/动态 subclass”顺序，降低误判为简单 re-export。

---

### Few-shot A02: `current_app` 首次访问的 auto-finalize 链

**问题**  
第一次访问 `celery.current_app` 时，Proxy 是如何把默认 app 回填并触发 auto-finalize 的？请给出完成回填与 finalize 的关键调用链。

**环境前置条件**  
- 尚未手动创建全局 app（未调用 `Celery()` 显式绑定）。  
- 使用默认 loader，未设置 `CELERY_LOADER`。  
- 无自定义 `app.autodiscover_tasks` 预先执行。

**推理链（示例 5 步，可压缩为 ≥4 步）**  
1. 代码访问 `celery.current_app`，实为 `celery/_state.py` 中的 `current_app = Proxy(get_current_app)`，触发 Proxy `__call__`。  
2. `get_current_app` 检查线程局部，若无则调用 `_get_current_app() or (set_default_app())`。  
3. `_get_current_app` 若发现 `default_app` 为空，则创建默认 `Celery('default')`，随后 `maybe_evaluate(pending)` 将 `_pending` 里的 PromiseProxy 任务 drain。  
4. 创建默认 app 时，`Celery.__init__` 会挂钩 `self._fixups`，并在 `finalize(auto=True)` 时触发 `connect_on_app_finalize` 登记的回调（如 shared_task pending）。  
5. 最终 `current_app` Proxy 返回实际的 `Celery` 实例；默认 app 被写回 `_state.default_app`，后续访问走缓存，不再触发构造。

**标准答案（ground_truth）**  
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery._state.get_current_app"
    ],
    "indirect_deps": [
      "celery._state._get_current_app",
      "celery.app.base.Celery.finalize",
      "celery.local.PromiseProxy"
    ],
    "implicit_deps": [
      "celery._state.set_default_app",
      "celery._state.default_app"
    ]
  }
}
```

**为何适合 few-shot（长链分段示范）**  
- 涉及 Proxy → 线程局部 → 默认 app 构造 → finalize → pending drain，多阶段状态切换，属于典型长链上下文。  
- 如果放入 eval 容易因默认 app / pending state 造成不可复现的歧义；few-shot 可示范“先定位 Proxy/Getter，再看默认分支，再看 finalize 副作用”这一分段检索方法。

---

> 备注：两条题干均避免与现有 eval / 已通过 few-shot 重复（不重复 `shared_task/_task_from_fun`、`Task.Strategy` 等），并突出“长链拆段”教学价值。输出仅使用 `ground_truth` 三字段，未扩 schema。 
