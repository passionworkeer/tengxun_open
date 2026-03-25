# Type A / D Challenge Notes

本文件是独立反方审稿，只做 challenge，不做集成建议润色。原则是优先找“现在不该并入正式 few-shot”的理由，尤其关注会误导后续 AI 的题干和推理链。

---

## A02：`current_app` 首次访问 auto-finalize 链

- 建议：`reject`
- 源码依据：
  - `external/celery/celery/_state.py:92-100` 的 `_get_current_app()` 只做两件事：若 `default_app is None` 则 `set_default_app(Celery('default', fixups=[], set_as_current=False, loader=...))`，然后返回 `_tls.current_app or default_app`。
  - `external/celery/celery/_state.py:139` 只是 `current_app = Proxy(get_current_app)`；默认 app 回填路径停在 getter，不会自然跳到 finalize。
  - `external/celery/celery/app/base.py:654-669` 才是 `finalize(auto=True)` 真实发生的位置，其中 `_announce_app_finalized(self)` 和 `maybe_evaluate(pending.popleft())` 都属于 finalize 阶段，而不是 `current_app` getter。
  - `external/celery/celery/local.py:97-106` 显示 Proxy 取值靠 `_get_current_object()`；把“访问 `current_app`”直接表述成触发 `Proxy.__call__` 也不严谨。
- 不稳点：
  - 题干不稳：它把“首次访问 `celery.current_app`”和“触发 auto-finalize”绑在一起，但源码里这是两条不同链。
  - 推理链不稳：草稿把 `maybe_evaluate(pending)` 说成发生在 `_get_current_app` 路径里，这在 `_state.py` 中不存在，属于伪跳转。
  - 推理链不稳：草稿还说 fallback app 创建时会挂 fixups；但 `_get_current_app()` 明确传 `fixups=[]`，与文案相反。
  - `ground_truth` 不稳：把 `celery.app.base.Celery.finalize`、`celery.local.PromiseProxy` 放进当前问题答案，会把“取 current_app”误教成“自动 drain pending”。
- 反方结论：
  - 这条不是“小修辞问题”，而是题眼错了。现在并进去会把错误心智固化到 few-shot。
  - 如果要保留主题，必须改题为“`current_app` 首次访问的 fallback app 创建链”；如果要保留 auto-finalize，则应换入口为 `app.tasks` 或 shared task Proxy 首次解引用。

---

## D-02：`@app.task(lazy=False)` 同名冲突

- 建议：`minimal fix`
- 源码依据：
  - `external/celery/celery/app/base.py:559-565` 显示 `Celery.task` 在默认 `shared=True` 下，先注册 `connect_on_app_finalize(cons)`，随后在 `if not lazy or self.finalized:` 分支直接执行 `self._task_from_fun(fun, **opts)`。
  - `external/celery/celery/app/base.py:601-629` 显示 `_task_from_fun` 的核心决议确实是：`if name not in self._tasks` 创建，否则 `task = self._tasks[name]` 直接复用。
- 不稳点：
  - 题干不稳：它把 `lazy=False` 说成“避免 pending 路径干扰”，这没错，但还不够；默认 `shared=True` 时仍然存在 finalize callback 支路，不能讲成“只有一次直接注册”。
  - 推理链不稳：第 1 步把 `Celery.task -> _task_from_fun` 写成唯一关键链，漏掉了 `connect_on_app_finalize(cons)` 这个同样会命中 `_task_from_fun` 的分支。
  - `ground_truth` 不稳：`implicit_deps` 填 `celery.app.registry.TaskRegistry` 太泛，当前冲突决议真正依赖的是 `self._tasks` 容器与 `_task_from_fun` 的复用逻辑，而不是 `TaskRegistry.register`。
- 反方结论：
  - 主结论“同名时复用已有 task”本身是对的，但当前写法会把模型教成“`lazy=False` 就只剩一条同步链”，这不够稳。
  - 最小修法有两种，至少选一种：
    - 在前置条件里显式加 `shared=False`，把问题真正收敛成单一路径。
    - 保留默认 `shared=True`，但在推理链中明确写出 finalize callback 也会再次走 `_task_from_fun`，只是最终仍返回已有对象。

---

## A01：CLI worker 启动长链

- 建议：`minimal fix`
- 源码依据：
  - `external/celery/celery/bin/celery.py:182` 通过 `celery.add_command(worker)` 注册子命令，`main()` 只是启动 Click 入口（`bin/celery.py:220`）。
  - `external/celery/celery/bin/worker.py:307-367` 的真实路径是 `worker(ctx, ...) -> worker = app.Worker(...) -> worker.start()`。
  - `external/celery/celery/app/base.py:1346-1352` 的 `Celery.Worker` 只是 `subclass_with_self('celery.apps.worker:Worker')` 的动态类构造入口。
- 不稳点：
  - 推理链不稳：草稿用了 `worker.py:main`、`WorkerCommand.run_from_argv`、`execute_from_commandline` 等当前源码中不存在的旧接口名。
  - 题干不稳：它问“最终负责启动 worker 的可调用对象”，但 `ground_truth.direct_deps` 只给了类 `celery.apps.worker.Worker`，没有落到实际启动动作 `worker.start()`。
- 反方结论：
  - 这条不是逻辑错，而是实现路径写旧了。
  - 不建议原样集成；至少先把链路改成 Click 入口和 `worker.start()` 的当前口径。

---

## D-01：TaskRegistry 同名覆盖

- 建议：`minimal fix`
- 源码依据：
  - `external/celery/celery/app/registry.py:16-27` 的 `TaskRegistry.register()` 结尾就是 `self[task.name] = task`，因此同 key 后写覆盖前写。
- 不稳点：
  - `ground_truth.indirect_deps` 放 `add_autoretry_behaviour` 与“同名覆盖规则”关系弱，容易把 few-shot 的重点从冲突决议带偏到副作用增强。
  - `ground_truth.implicit_deps` 只写 `TaskRegistry` 太空，不如直接在推理里强调 dict 赋值覆盖语义。
- 反方结论：
  - 结论本身没问题，但依赖分层还不够锐利。
  - 可以修，不需要重写。

---

## D-03：control command 同名覆盖

- 建议：`minimal fix`
- 源码依据：
  - `external/celery/celery/worker/control.py:52-65` 中 `Panel._register()` 对执行分发表的关键写入是 `cls.data[control_name] = fun`。
  - `external/celery/celery/worker/pidbox.py:28-30` 运行时把 `handlers=control.Panel.data` 传进节点，真正命令分发看的是 `Panel.data`。
- 不稳点：
  - `ground_truth` 把 `Panel.meta` 放进主链，但“运行时最终采用哪一个实现”主要由 `Panel.data` 决定，`meta` 不是执行冲突的核心。
  - 题干若不补限定，容易让读者把“元信息覆盖”和“handler 覆盖”混为一谈。
- 反方结论：
  - 主结论可保留，但应明确这是“pidbox handlers 维度”的覆盖，而不是泛指所有控制面元数据语义都一样重要。

---

## D-04：Signal `dispatch_uid` 冲突

- 建议：`minimal fix`
- 源码依据：
  - `external/celery/celery/utils/dispatch/signal.py:54-61`：有 `dispatch_uid` 时，lookup key 是 `(dispatch_uid, _make_id(sender))`。
  - `external/celery/celery/utils/dispatch/signal.py:208-213`：命中同 key 时不会 append 新 receiver。
  - `external/celery/celery/utils/dispatch/signal.py:292-301`：连接/发送前会 `_clear_dead_receivers()`，死亡 weak receiver 会被清掉。
  - `external/celery/celery/utils/dispatch/signal.py:258-288`：`send()` 实际逐个执行 `_live_receivers(sender)` 返回的 live receiver。
- 不稳点：
  - 题干不稳：它问“按哪个 receiver 执行”，但没补“第一个 receiver 仍存活”的条件；若 weak receiver 已被回收，后续行为会变。
  - 推理链不稳：当前版本强调“只会有一个 receiver 被调用一次”，但没有把 `_clear_dead_receivers()` 这个边界条件写出来。
- 反方结论：
  - 规则主体是对的，但如果不补 weakref 存活前提，这条 few-shot 容易被追问击穿。
  - 建议补一行前置条件：首次连接的 receiver 仍存活，且第二次 connect 前未发生清理导致重新占位。
