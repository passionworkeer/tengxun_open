# Few-shot Type D Round 1

本批次仅包含你指定的 2 条：`D-01`（`celery/app/registry.py`）与 `D-02`（`celery/app/base.py` 的 task 命名/冲突逻辑）。  
不扩范围，不扩 schema。

---

## D-01：TaskRegistry 同名注册冲突（registry.py）

**问题**  
在同一个 `TaskRegistry` 实例里，先后 `register` 两个 `task.name` 相同、但 `run` 实现不同的 Task，最终 `registry[name]` 指向哪一个？

**环境前置条件**  
1. 两次注册发生在同一个 `TaskRegistry` 对象上。  
2. 两个 Task 都有合法 `name`（不会触发 `InvalidTaskError`）。  
3. 第二次注册确实发生（不是并发未完成状态）。  

**推理过程（>=4步）**  
1. `TaskRegistry.register` 先校验 `task.name` 非空，否则抛 `InvalidTaskError`。  
2. 如果传入的是类，`register` 会先实例化，再继续处理。  
3. `register` 最终执行 `self[task.name] = task`。  
4. 由于底层是字典语义，同 key 赋值会覆盖旧值，因此后注册的 task 覆盖先注册的 task。  
5. 所以冲突决议是“last write wins”，最终 `registry[name]` 指向第二次注册对象。  

**标准答案**  
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.registry.TaskRegistry.register"
    ],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
```

**为什么适合作 few-shot**  
这是典型 Type D（命名空间冲突）里最容易被模型答错的一类：很多模型会误判为“首个注册保留”。它更适合作 few-shot 教模型识别“同名 key 覆盖”规则，而不是做 eval 的单点 FQN 记忆题。

---

## D-02：`@app.task` 自动命名后的同名冲突（base.py）

**问题**  
同一个 app 中，两个函数都用 `@app.task(lazy=False, shared=False)` 且未显式传 `name`，并且推导出的 `task.name` 相同。第二次装饰时会覆盖第一次，还是复用第一次任务对象？

**环境前置条件**  
1. 两个函数在同一个 app 下注册。  
2. 两次注册都走 `lazy=False, shared=False`，避免 pending 与 finalize callback 支路干扰，直接考察同步注册路径。  
3. 两个函数推导出的任务名相同（例如模块名+函数名相同，或等效命名场景）。  

**推理过程（>=4步）**  
1. `Celery.task` 在 `lazy=False, shared=False` 条件下，不经过 pending 队列，也不注册 `connect_on_app_finalize(cons)` 支路。  
2. 该分支直接调用 `self._task_from_fun(fun, **opts)`。  
3. `_task_from_fun` 会先确定任务名：`name = name or self.gen_task_name(fun.__name__, fun.__module__)`。  
4. `gen_task_name` 最终委托 `celery.utils.imports.gen_task_name` 生成规范任务名。  
5. 冲突判断在 `_task_from_fun` 内：若 `name not in self._tasks` 才创建新任务并写入；否则直接 `task = self._tasks[name]`。  
6. 因此在“同名冲突”场景下，第二次不会覆盖，返回的是第一次已存在任务对象（first wins in this path）。  

**标准答案**  
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery._task_from_fun"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.gen_task_name",
      "celery.utils.imports.gen_task_name"
    ],
    "implicit_deps": [
      "celery.app.base.Celery._tasks"
    ]
  }
}
```

**为什么适合作 few-shot**  
这条能和 D-01 形成对照：`TaskRegistry.register` 是“后写覆盖”，但 `@app.task -> _task_from_fun` 的同名分支是“已有即复用”。这种“同属命名冲突、却因入口不同而决议相反”的模式非常适合 few-shot，能显著降低 Type D 误判。
