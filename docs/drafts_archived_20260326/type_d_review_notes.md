# Type D Few-shot Review Notes

复核范围：
- `docs/drafts/fewshot_type_d_round1.md`：D-01、D-02
- `docs/drafts/fewshot_type_d_round2.md`：D-03、D-04

对照基线：`external/celery` 当前快照（commit `b8f85213f45c937670a6a6806ce55326a0eb537f`）。

---

## D-01（TaskRegistry 同名注册冲突）

**verdict=needs_fix**

1. 结论“同名冲突时后注册覆盖先注册（last write wins）”与源码一致：`TaskRegistry.register` 最终执行 `self[task.name] = task`。  
2. 题目聚焦“命名冲突决议”，但当前 `indirect_deps` 放入 `add_autoretry_behaviour`，该调用与“覆盖规则”关系弱，容易把注意力带偏。  
3. `implicit_deps` 仅写 `TaskRegistry` 过于笼统，冲突真正稳定机制是 dict key 覆盖语义。  
4. 作为 few-shot 是合适的：它强调“注册表覆盖规则”，并且可与 D-02 的“同名复用”形成对照，不适合做单点 eval FQN。  

最小修复建议：
- 保留主结论不变。  
- 将 `indirect_deps` 里的 `add_autoretry_behaviour` 移除或降权。  
- 将 `implicit_deps` 改为更机制化表达（例如补充 `dict` key overwrite 语义，或在推理中显式声明“由 `self[...]` 赋值触发覆盖”）。

---

## D-02（@app.task 自动命名冲突）

**verdict=accept**

1. 决议“同名时不覆盖而是复用已有任务对象（first wins in `_task_from_fun` path）”与源码一致：`if name not in self._tasks` 才创建，否则直接 `task = self._tasks[name]`。  
2. 命名链路准确：`name or self.gen_task_name(...)`，再委托 `celery.utils.imports.gen_task_name`。  
3. 环境前置条件已把 `lazy=False` 固定，避免 pending/finalize 支路干扰，问题边界清晰。  
4. 适合作 few-shot：与 D-01 同属 Type D 冲突题，但决议相反，教学价值明显；不应简化成 eval 的单一 FQN 题。  

最小修复建议：
- 可选优化：`implicit_deps` 从 `TaskRegistry` 改为更贴近实现状态容器的 `Celery._tasks`，提升稳定性与可解释性。

---

## D-03（worker/control 注册冲突）

**verdict=needs_fix**

1. 主结论“同名命令后注册覆盖先注册”与 `Panel._register` 的 dict 写入逻辑一致（`Panel.data[control_name] = fun`）。  
2. 运行时分发链路也成立：pidbox 节点使用 `handlers=control.Panel.data`，因此实际执行看 `Panel.data` 的最终映射。  
3. 但当前文本把 `Panel.meta` 也作为冲突核心，容易误导：远程命令执行主要依赖 `Panel.data`；`meta` 更偏 CLI 展示/参数元信息。  
4. 题面写“worker 运行时最终采用哪一个实现”，应更明确限定“命令分发 handlers 维度”，避免混入 `Panel.meta` 的可见性语义。  
5. 作为 few-shot 合适：这是典型 registry 命名冲突决议，不适合 eval 的静态单点答案。  

最小修复建议：
- 问题文本补一句“以 pidbox handlers 分发结果为准”。  
- `ground_truth` 保留 `Panel._register`、`Panel.data`，弱化/移除 `Panel.meta`（或把 `meta` 仅放解释段，不放依赖主链）。

---

## D-04（signal registry 去重/冲突）

**verdict=needs_fix**

1. 去重机制判断正确：当 `dispatch_uid` 存在时，lookup key 由 `(dispatch_uid, sender_id)` 构成，不看 receiver 对象 id。  
2. `_connect_signal` 命中同一 key 时不会 append 新 receiver，因此不会出现“双触发”。  
3. 当前答案对“按哪个 receiver 执行”不够明确，应明确为“保留首次注册且仍存活的 receiver”。  
4. 现有前置条件缺少一个关键点：若使用 weak receiver 且原 receiver 已被回收，清理后可能允许后续 connect 重新占位。  
5. few-shot 适配度高：它能教模型识别“冲突键由 dispatch_uid 主导”的规则，明显优于做 eval 单点。  

最小修复建议：
- 在问题答案中明确写出“first connected receiver wins（在其未被回收前）”。  
- 前置条件补充“原 receiver 仍存活（未被 weakref 回收）”。  
- 在推理中补一句 `_clear_dead_receivers` 对该规则的边界影响。

