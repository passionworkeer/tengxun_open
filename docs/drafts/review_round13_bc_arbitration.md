# Review Round 13 — BC Tail Arbitration (B05, C04)

仅仲裁 B05 / C04；其他条目不处理。Verdict 取值：`integrate_now` | `needs_fix`。

---

## B05 — `@app.task` 在 execv 场景的分支
- **verdict: integrate_now**
- **basis (source)**  
  - `celery/app/base.py` lines ~542-548: 当 `USING_EXECV and opts.get('lazy', True)` 为真时，`Celery.task` 直接 `return shared_task(*args, lazy=False, **opts)`，首跳目标确为 `celery.app.shared_task`，未走本 app 的 `_task_from_fun`。  
  - 后续绑定仍在 `shared_task` 的 finalize/pending 路径完成，与题干的“先转发入口”描述一致。
- **note**  
  - 题干环境已强调 `FORKED_BY_MULTIPROCESSING` 置位；ground_truth 以 `shared_task` 为 direct 符合源码。implicit 中提到 `_task_from_fun` 仅是后续实际绑定点，不影响首跳判定，保留可接受。

---

## C04 — `celery.chord` 再导出 / 兼容别名
- **verdict: integrate_now**
- **basis (source)**  
  - `celery/__init__.py` exports `chord` from `celery.canvas` (`recreate_module` path)。  
  - `celery/canvas.py` lines ~1953, 2373：定义 `class _chord(Signature)`，随后 `chord = _chord`。顶层 `celery.chord` 最终指向的是该类对象，其定义 FQN 为 `celery.canvas._chord`，别名 `celery.canvas.chord` 仅指向同一对象。  
  - 因此 ground_truth 指向 `_chord` 符合“真实定义”要求，间接列出 `celery.canvas.chord` 作为别名也已覆盖。
- **note**  
  - 如需显式强调别名，可在后续文本说明“chord 为 _chord 的公开别名”，但当前答案已区分 direct/indirect，无阻塞集成。

---

## Summary
- integrate_now: B05, C04  
- needs_fix: none
