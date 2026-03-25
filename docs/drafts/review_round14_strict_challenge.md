# Review Round 14 - Strict Challenge Summary

本轮目标不是再起草新条目，而是让严格 reviewer 专门挑战 `A02 / B05 / C04 / C05` 是否真的可以进正式 few-shot。

---

## A02 - `current_app.tasks` 首访链路

- strict objection：
  - 不能把 “访问 `current_app`” 直接说成 “触发 finalize”。
  - ground truth 不应把内部写状态步骤塞成主链依赖。
- final resolution：
  - 保留 `celery.app.base.Celery.tasks` 作为稳定 finalize 触发点。
  - 保留 `celery._state._get_current_app` 作为 default app 解析入口。
  - 不把 `set_default_app(...)` 回填进正式 ground truth，只在推理过程里说明。
- final verdict：`integrate_with_tightening`

## B05 - `@app.task` 在 execv 场景的首跳转发

- strict objection：
  - 若没有说明环境变量必须在导入 `celery.app.base` 之前设置，`USING_EXECV` 可能不会反映该条件。
  - `_task_from_fun` 是后续链路，不应混入本题 ground truth。
- final resolution：
  - 在环境前置条件中显式写明 env 的导入时序。
  - 正式 ground truth 聚焦 `celery.app.shared_task` 这一首跳入口，并把 `USING_EXECV` 收到隐式条件。
- final verdict：`integrate_with_tightening`

## C04 - `celery.chord` 再导出 + 别名链

- strict objection：
  - 重点挑战“是否应该停在公开别名 `celery.canvas.chord`，而不是继续追 `_chord`”。
- final resolution：
  - 源码明确 `class _chord(Signature)`，随后 `chord = _chord`。
  - 因而 `_chord` 是真实定义，`chord` 是 back-compat 公开别名。
- final verdict：`integrate_now`

## C05 - `celery.uuid` 跨包再导出

- strict objection：
  - 重点挑战“是否应该停在 `celery.utils.uuid`，而不是继续追到最终提供者”。
- final resolution：
  - `celery.utils.__init__` 只是 `from kombu.utils.uuid import uuid`。
  - 因而最终真实符号应落到 `kombu.utils.uuid.uuid`。
- final verdict：`integrate_now`

---

## Summary

- `A02`：可集成，但需收紧依赖分层。
- `B05`：可集成，但需补全 import 前 env 前置条件，并去掉后续链路噪音。
- `C04`：可直接集成。
- `C05`：可直接集成。
