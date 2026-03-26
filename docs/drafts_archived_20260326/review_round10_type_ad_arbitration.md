# Review Round 10 — Type A / D Repair Arbitration

本轮结论基于以下材料合并仲裁：

- `docs/drafts/review_round9_type_ad.md`
- `docs/drafts/type_a_review_notes.md`
- `docs/drafts/type_d_review_notes.md`
- `docs/drafts/type_ad_challenge_notes.md`
- 修订后的 `fewshot_type_a_round1.md`
- 修订后的 `fewshot_type_d_round1.md`
- 修订后的 `fewshot_type_d_round2.md`

目标不是复述原结论，而是回答：修完以后，哪些条目现在可以进正式 few-shot，哪些仍必须挡住。

---

## 最终 verdict

### A01（CLI worker 启动长链）
- verdict: `accept_after_fix`
- 理由：
  - 已移除不存在的旧版 `WorkerCommand.*` / `worker.py:main` 路径。
  - 现在明确区分了 `worker.start()` 的启动动作和 `Celery.Worker -> subclass_with_self` 的动态类解析。
  - 题干与 `ground_truth` 口径已对齐，可作为 Type A 长链样本使用。

### A02（原 current_app auto-finalize 链）
- verdict: `reject`
- 理由：
  - 原题眼错误，不是简单措辞问题。
  - 当前草稿已明确标注作废；在新 replacement 过审前，不应进入正式 few-shot。

### D-01（TaskRegistry 同名覆盖）
- verdict: `accept_after_fix`
- 理由：
  - 已把重点收敛到 `self[task.name] = task` 的覆盖语义。
  - 不再把 `add_autoretry_behaviour` 误当作冲突决议主链的一部分。

### D-02（@app.task 同名复用）
- verdict: `accept_after_fix`
- 理由：
  - 已把前置条件收紧为 `lazy=False, shared=False`，消掉 finalize callback 支路争议。
  - `ground_truth` 现在围绕 `_task_from_fun` 与 `_tasks` 复用逻辑，教学目标更单纯。

### D-03（control command 同名覆盖）
- verdict: `accept_after_fix`
- 理由：
  - 已把题目限定为 pidbox handlers 分发语义。
  - 已去掉 `Panel.meta` 作为执行主链的误导性表述。

### D-04（Signal dispatch_uid 冲突）
- verdict: `accept_after_fix`
- 理由：
  - 已补充“首次 receiver 仍存活”的边界条件。
  - 已把 `_clear_dead_receivers` 这一真实边界行为写进推理链。

---

## Integration Guidance

- `integrate_now`: `A01`, `D-01`, `D-02`, `D-03`, `D-04`
- `hold_back`: `A02`

---

## 注意事项

1. 本轮允许集成的是“修订后的条目”，不是原始 round 9 审过的旧文本。
2. `A02` 必须单独补 replacement，不要把“作废说明”回填进正式 few-shot 文档。
3. 正式文档更新后，要同步把进度文档改成：
   - Type D 已补齐 4 条
   - Type A 已补齐 1 条，仍缺 1 条 replacement
