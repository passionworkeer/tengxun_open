# Review Round 15 - Formal Few-shot Pool Safety

本轮目标不是继续扩数量，而是检查“正式 20 条 few-shot”是否适合直接写进 `prompt_templates_v2.py`。

---

## Trigger

- strict reviewer 对正式池发出三类阻塞：
  - `B01` 存在错链 / 脏链
  - `E03` 题目超出当前 schema 的可表达范围
  - `D04` 把强运行时行为题硬塞进 FQN 判题结构

---

## Resolution

### B01

- 原问题：
  - `indirect_deps` 错写成 `celery.app.task.create_task_cls`
  - `implicit_deps` 混入了与本题无关的 `celery.app.builtins.add_backend_cleanup_task`
- 修复后：
  - `direct_deps` 保持 `celery.app.base.Celery._task_from_fun`
  - `indirect_deps` 收紧为：
    - `celery._state.connect_on_app_finalize`
    - `celery._state._get_active_apps`
  - `implicit_deps` 收紧为：
    - `celery.app.shared_task`

### D04

- 原问题：
  - 题目在问“最终触发几次 / 按哪个 receiver 执行”，过度依赖运行时状态和对象存活条件。
- 修复后：
  - 改写为“去重键判定发生在哪个 helper 链路”。
  - 正式答案只保留稳定的 helper 级依赖：
    - direct:
      - `celery.utils.dispatch.signal.Signal._connect_signal`
      - `celery.utils.dispatch.signal._make_lookup_key`
    - indirect:
      - `celery.utils.dispatch.signal.Signal.connect`
    - implicit:
      - `celery.utils.dispatch.signal.Signal.receivers`

### E03

- 原问题：
  - 同时在问“backend 解析到哪个类”与“URL payload 如何保留”，但当前 schema 只能稳定表达 FQN。
- 修复后：
  - 改成单问单判，只问 backend 最终解析到哪个类。
  - 保留 `by_url -> by_name -> symbol_by_name` 这条稳定链，不再把 tuple 第二项写进题目。

---

## Side Fix

- `docs/eval_case_annotation_template.md` 中同源的 `shared_task_registration` 示例已同步修正，避免未来再次把脏链抄回正式样本。

---

## Gate

后续进入 formal few-shot / eval pool 的题，必须同时满足：

1. 单问单判，不把“最终是谁”与“为什么 / 什么时候 / 还会返回什么值”绑成一题。
2. 当前 schema 能完整承载答案；不能表达的值语义、顺序语义、次数语义不得硬塞进 FQN 结构。
3. `ground_truth` 只保留判题必需的最小闭包，不混入 side effects。
4. 每个 FQN 都能在当前 Celery 提交号下物理回溯到源码。
5. 强依赖 import 时机、env、weakref / GC、运行时状态的题，必须把前置条件写成可复核约束。

---

## Verdict

- `B01 / D04 / E03` 已完成收紧修复。
- 当前 20 条正式 few-shot 可继续写入 `prompt_templates_v2.py` 与 `data/fewshot_examples_20.json`。
