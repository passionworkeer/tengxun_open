## Few-shot Type A (长链上下文) - Round 3 Draft

> 本轮只修 `A02`，`A01` 沿用 `fewshot_type_a_round2.md` 已通过版本，不在本稿重复改写。  
> 结构保持 few-shot 模板：问题、环境前置条件、推理过程、答案。

---

### Few-shot A02: `current_app.tasks` 首访链路（分离 default app 与 finalize）

**问题**: 在未显式创建全局 app 的前提下，首次访问 `celery.current_app.tasks` 时，哪一步只负责创建/返回 default app，哪一步才会触发 `finalize`？

**环境前置条件**:
1. 进程内尚未显式执行 `Celery(..., set_as_current=True)` 或其他等价的全局 app 绑定。
2. 使用默认 current_app 路径（未开启 `C_STRICT_APP` / `C_WARN_APP` 特殊分支）。
3. `autofinalize=True`（默认配置）。

**推理过程**:
1. `celery.current_app` 是 `Proxy(get_current_app)`；先发生的是 Proxy 解引用，而不是任务注册表访问。
2. 在默认分支中，`get_current_app` 绑定到 `_get_current_app`：若 `default_app is None`，会创建 fallback `Celery('default', fixups=[], set_as_current=False, loader=...)` 并 `set_default_app(...)`。
3. 到这一步为止，仅完成“创建/返回 default app”；单独访问 `celery.current_app` 本身不会触发 `finalize`。
4. 随后访问 `.tasks` 才命中 `Celery.tasks`（cached_property），其内部显式执行 `self.finalize(auto=True)`，这是 finalize 的稳定触发点。
5. `finalize` 内部可能涉及 `_announce_app_finalized`、`maybe_evaluate` 等子步骤，但它们受内部状态（如 pending 队列是否为空）影响，不应作为本题必经主链依赖。

**答案**:
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.tasks"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.finalize",
      "celery._state._get_current_app",
      "celery._state.set_default_app"
    ],
    "implicit_deps": [
      "celery._state.current_app",
      "celery.local.Proxy",
      "celery._state.default_app"
    ]
  }
}
```

