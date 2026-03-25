# Review Round 12 — Few-shot B05 / C04 / C05 (Strict)

判定：accept / needs_more_fix / reject。对照 external/celery 当前源码。若会误导模型，直接 reject。

---

## B05 (@app.task 在 execv 场景的转发)
- verdict: **accept**  
- reasoning:  
  - 源码 `Celery.task` 首行 `if USING_EXECV and opts.get('lazy', True): return shared_task(..., lazy=False, **opts)`，首跳目标确为 `celery.app.shared_task`，题干明确“首跳入口”而非最终注册。  
  - direct 只写 `shared_task`，indirect 有 `Celery.task`，implicit 放 finalize/_task_from_fun，分层可接受。  
  - 与现有 few-shot B02/B03/B04 主题不同（pending/finalize/Proxy），无高重复。可回填正式 few-shot 文档。

## C04 (celery.chord 的再导出 + 别名链)
- verdict: **needs_more_fix**  
- reasoning:  
  - 源码 `celery/__init__.py` 通过 `recreate_module` 懒导出 `chord` 到 `celery.canvas`；`celery.canvas` 中有 `from .canvas import chord, group, ...`? 实际定义是 `class chord(Signature)`；并非 `_chord` 命名。draft 把最终落点写成 `celery.canvas._chord`，与当前版本命名不符，可能与历史版本混淆。  
  - 即使存在别名赋值，direct 应落在真实定义类 `celery.canvas.chord`（类名 chord），而不是猜测 `_chord`。需核对源码后修正 direct FQN 和 alias 关系说明。  
  - 未说明 back-compat alias 的具体赋值语句，ground_truth 易误导模型到不存在的 `_chord`。  
- action: 修正 direct 到源码实际类名，并在 reasoning 写清 alias 语句；暂不回填。

## C05 (celery.uuid 再导出跨包)
- verdict: **accept**  
- reasoning:  
  - 源码链：`celery/__init__.py` 懒导出 uuid -> `celery.utils.uuid` -> `kombu.utils.uuid.uuid`（在 `celery/utils/__init__.py` 直接 from kombu import uuid）。direct 选在最终提供者 `kombu.utils.uuid.uuid` 正确。  
  - 分层清晰（direct=最终函数，indirect=中间再导出，implicit 为空），无 schema 扩展。  
  - 与现有 few-shot/eval 无高重复，适合 few-shot 教“跨包再导出”。可回填。

---

## Integration Guidance
- **integrate_now**: B05, C05  
- **hold_back**: C04（修正落点/alias 描述后再入正式 few-shot）
