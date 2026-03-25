# Few-shot Type D Round 2 Draft

说明：本批次仅包含 2 条 Type D 草稿（D-03、D-04），不扩范围。  
答案字段保持正式口径：只使用 `ground_truth.direct_deps / indirect_deps / implicit_deps`。

---

## Few-shot D-03（`celery/worker/control.py`：control 注册冲突）

**问题**：当自定义 remote control 命令与已有命令同名（例如都注册为 `conf`）时，以 worker pidbox 的 handlers 分发结果为准，运行时最终采用哪一个实现？

**环境前置条件**：
1. 在同一个 Python 进程里，两个命令都通过 `@control_command` 或 `@inspect_command` 注册到同一个 `Panel`。
2. 后注册命令发生在前注册命令之后（导入顺序已确定）。
3. 两者使用相同 `name`（或函数名推导得到同一 `control_name`）。

**推理过程（>=4步）**：
1. `@control_command` / `@inspect_command` 都会转发到 `Panel.register(...)`，再进入 `Panel._register(...)`。
2. `Panel._register` 在内部 `_inner` 中执行 `cls.data[control_name] = fun`，把命令实现写入全局 handlers 映射。
3. `Panel.data` 是全局 dict；相同 key 的再次赋值会覆盖旧值，所以同名冲突时“后注册覆盖先注册”。
4. worker pidbox 初始化时将 `handlers=control.Panel.data` 传给 mailbox 节点，运行时命令分发直接使用该 handlers 映射。
5. 因此冲突场景下，最终生效的是最后一次写入 `Panel.data[control_name]` 的函数实现。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.worker.control.Panel._register",
      "celery.worker.control.Panel.data"
    ],
    "indirect_deps": [
      "celery.worker.control.control_command",
      "celery.worker.control.inspect_command",
      "celery.worker.pidbox.Pidbox.__init__"
    ],
    "implicit_deps": []
  }
}
```

**为什么适合作 few-shot**：
- 这是典型 Type D（命名冲突）机制题，核心是“注册键冲突如何决议”，不是单一 FQN 映射题。
- 能教模型识别“字典注册表 + 导入顺序 + 最后写入生效”的稳定模式，适合作为迁移模板。
- 与现有 eval/hard 样本（装饰器注册、symbol_by_name、loader alias）不重复。

---

## Few-shot D-04（`celery/utils/dispatch/signal.py`：signal registry 去重/冲突）

**问题**：在同一个 `Signal` 上，对同一 `sender` 重复 `connect` 两个 receiver 且使用同一个 `dispatch_uid` 时，最终会触发几次，按哪个 receiver 执行？

**环境前置条件**：
1. 两次 `connect` 作用于同一个 `Signal` 实例。
2. `sender` 相同，且显式传入相同 `dispatch_uid`。
3. 第二次 `connect` 前未执行 `disconnect`。
4. 第一次连接的 receiver 在发送前仍存活（未被 weakref 回收）。
5. receiver 都可接收 `**kwargs`（满足 signal receiver 约束）。

**推理过程（>=4步）**：
1. `Signal.connect(...)` 最终进入 `Signal._connect_signal(...)`。
2. `_connect_signal` 用 `_make_lookup_key(receiver, sender, dispatch_uid)` 生成去重键；当 `dispatch_uid` 存在时，key 由 `(dispatch_uid, sender_id)` 组成，不看 receiver 对象身份。
3. `_connect_signal` 在 `self.receivers` 中遍历已有 key；若命中相同 key，直接 `break`，不会 append 新 receiver。
4. 进入发送路径前，Signal 还会清理 dead weak receiver；在题设“首次 receiver 仍存活”的前提下，这个 key 仍由第一次连接留下的 receiver 占据。
5. `Signal.send(...)` 调用 `_live_receivers(...)` 后按列表逐个执行，因此该冲突键只会有一个 live receiver 被调用一次，执行的是第一次成功保留下来的 receiver。
6. 若想替换为新 receiver，需要先按相同 key 做 `disconnect(...)`，或等待旧 weak receiver 被清理后再重新 connect。

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.utils.dispatch.signal.Signal._connect_signal",
      "celery.utils.dispatch.signal._make_lookup_key"
    ],
    "indirect_deps": [
      "celery.utils.dispatch.signal.Signal.connect",
      "celery.utils.dispatch.signal.Signal._clear_dead_receivers",
      "celery.utils.dispatch.signal.Signal.send",
      "celery.utils.dispatch.signal.Signal._live_receivers",
      "celery.utils.dispatch.signal.Signal.disconnect"
    ],
    "implicit_deps": [
      "celery.utils.dispatch.signal.Signal.receivers"
    ]
  }
}
```

**为什么适合作 few-shot**：
- 该题是“命名/标识冲突决议规则”示范，核心在 key 设计与去重逻辑，属于 Type D 高频误判点。
- 适合教模型区分“函数同名/不同对象”与“dispatch_uid 冲突”两种语义，不依赖大段上下文。
- 与已存在样本（如 strategy 的 `task.Request` 解析）主题不同，不构成重复。
