## Few-shot Type A (长链上下文) — Round 1 Draft

> 目标：提供 2 条长链上下文 few-shot，用于教模型“分段定位 + 逐跳追踪”，避免直接猜终点 FQN。均基于 `fewshot_examples.md` 的结构与 schema。

---

### Few-shot A01: CLI worker 启动长链

**问题**  
当执行 `celery -A proj worker` 时，从 CLI 命令入口到 worker 真正启动的关键调用链是什么？请标出最终执行启动动作的可调用入口，以及 Worker 实例来自哪个动态绑定类。

**环境前置条件**  
- 命令行调用：`celery -A proj worker`，未自定义子命令。
- `proj` 可导入且含 `celery = Celery('proj')`。
- 使用默认 `CELERY_LOADER` 与默认 worker 选项（无 `--loader` 等改写）。

**推理链（示例 5 步，可压缩为 ≥4 步）**  
1. `celery/bin/celery.py:main()` 启动顶层 Click 入口；`celery` group 已通过 `celery.add_command(worker)` 注册 `worker` 子命令。  
2. 解析完 `-A proj` 后，CLI 把 app 放进 `CLIContext`，随后进入 `celery/bin/worker.py:worker(...)` 这个子命令函数。  
3. `worker(...)` 内部执行 `worker = app.Worker(...)`，这里触发 `Celery.Worker` 缓存属性。  
4. `Celery.Worker` 调用 `self.subclass_with_self('celery.apps.worker:Worker')`；`subclass_with_self` 再通过 `symbol_by_name` 解析真实类并生成绑定当前 app 的 Worker 子类。  
5. 命令函数最后显式调用 `worker.start()`，真正把 worker 跑起来；因此“启动动作”和“Worker 类解析”是同一长链里的两个不同节点。

**标准答案（ground_truth）**  
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.apps.worker.Worker.start"
    ],
    "indirect_deps": [
      "celery.bin.worker.worker",
      "celery.app.base.Celery.Worker",
      "celery.apps.worker.Worker",
      "celery.app.base.Celery.subclass_with_self"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name",
      "celery.bin.celery.main"
    ]
  }
}
```

**为何适合 few-shot（长链分段示范）**  
- 涉及 CLI 解析 → Command 对象 → app 缓存属性 → 动态 subclass 4+ 跳，终点是绑定后的 Worker 子类，不是单一静态 FQN。  
- 运行时行为依赖 argv 与 app 上下文，直接 eval 难以稳定复现；few-shot 可教模型按段确认“入口解析/命令分派/实例化/动态 subclass”顺序，降低误判为简单 re-export。

---

### Few-shot A02: 当前版本作废，待替换

**状态**  
- `reject`

**原因**  
1. 原题把“首次访问 `celery.current_app`”和“触发 auto-finalize”绑定在一起，但当前源码里这不是同一条链。  
2. 原推理链混入了不存在于 `_get_current_app()` 路径中的 `maybe_evaluate(pending)` / finalize 副作用，属于错误 few-shot。  
3. 在替换成新题之前，不应把该条并入正式 few-shot 文档。  

**后续替换方向**  
- 方向 A：改成“`current_app` 首次访问的 fallback app 创建链”。  
- 方向 B：改成“首次访问 `app.tasks` 或等价入口时的真实 auto-finalize 链”。  
- 具体 replacement 需重新过审，不沿用当前版本的 `ground_truth`。

---

> 备注：两条题干均避免与现有 eval / 已通过 few-shot 重复（不重复 `shared_task/_task_from_fun`、`Task.Strategy` 等），并突出“长链拆段”教学价值。输出仅使用 `ground_truth` 三字段，未扩 schema。 
