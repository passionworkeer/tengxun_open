# Review Round 11 — Few-shot Type A Round2

严格审稿，仅判 A01/A02，结论：accept / needs_more_fix / reject。对照当前 external/celery 源码。

---

## A01（Click CLI worker 启动链）
- verdict: **accept**  
- objections checked:  
  - 入口改为 Click 路由，直接命中 `celery.bin.worker.worker -> app.Worker -> subclass_with_self -> WorkController.start`，终点选在实际启动方法 `WorkController.start`，避免了“把类当终点”的旧口径；direct/indirect 分层清晰。  
  - 前置条件写明使用新 CLI，不与老 `WorkerCommand` 流程混淆；未发现与现有 eval/已通过 few-shot 的重复。  
- integration: 可以直接回填正式 `docs/fewshot_examples.md`。

## A02（current_app.tasks 触发 finalize 链）
- verdict: **needs_more_fix**  
- objections:  
  - direct 选了 `Celery.tasks` 和 `Celery.finalize`，但 implicit/indirect 同时塞入 `_get_current_app` / `set_default_app` / `_announce_app_finalized` / `maybe_evaluate`，分层仍有摇摆：`_announce_app_finalized` 是 finalize 内部动作，放 indirect 会让 direct/indirect 边界不稳。  
  - 题干强调“未显式创建全局 app”，但答案没区分 default app 创建和 finalize 的前置条件（e.g. pending 是否存在、fixups 是否被禁用）；若 fixups/pending 为空，`maybe_evaluate` 不一定执行，当前 implicit 列表把它写成必经路径。  
  - 仍需更明确区分：取 `current_app` 只构造 default app，不触发 finalize；访问 `.tasks` 才触发 finalize，这一点应在 ground_truth 分层中体现（建议 direct 仅 `Celery.tasks`, indirect `Celery.finalize`; implicit 留 Proxy/default_app，去掉 `_announce_app_finalized` 或将其降到 reasoning 说明而非依赖列表）。  
- integration: 暂不回填，需收紧 direct/indirect/implicit 边界并说明 finalize 是否必然执行哪些子步骤。

---

## Integration Guidance
- **integrate_now**: A01  
- **hold_back**: A02（先收紧分层/前提后再入正式 few-shot）
