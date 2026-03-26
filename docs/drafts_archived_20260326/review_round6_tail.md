# Review Round 6 (Tail Items)

仅审 round3 尾项修订：`eval_remaining_round3.md` 与 `fewshot_round3.md`。结论：`accept / needs_more_fix / reject`。关注 ID/难度槽位、eval/few-shot 泄漏、schema 风险。

---

## Eval Remaining Round 3

### celery_medium_017（原 hard_017）
- verdict: accept  
- reasons: 已降级为 medium，ID 改为 `celery_medium_017`，去掉 `DjangoFixup.install` 副作用，目标唯一（字符串入口解析到函数）；implicit_level=3 与单层字符串解析匹配，无新 schema 风险。  
- note: 集成时使用新 ID，不要再占 hard 槽位。

### celery_medium_020（原 hard_020）
- verdict: accept  
- reasons: 已正式降为 medium，ID 更名，direct/indirect 分层清晰，implicit_depth=3 合理；不再与 hard 配额冲突。  
- note: 集成时按 medium 计入难度配比。

---

## Few-shot Round 3

### B03（导入即注册回调）
- verdict: accept  
- reasons: 完全移除 `_task_from_fun` 终点，聚焦导入阶段的 `connect_on_app_finalize` 注册；与 eval 已收样本路径不同，schema 字段合法，无泄漏风险。

### B04（shared_task Proxy 触发 auto-finalize）
- verdict: accept  
- reasons: 终点改为 `Celery.tasks` 触发点，不再泄漏 `_task_from_fun`；问题聚焦触发机制，与 eval Type B 终点题区分，字段合规。

### E03（by_url + override_backends）
- verdict: needs_more_fix  
- reasons: direct_deps 里同时放了 `by_url` 和最终类，易引入口径漂移；更重要的是答案未在 schema 内表达“返回二元组”要求，仍可能被当作“最终类”单值。需在答案中保持 schema 只含 FQN，且在 reasoning/说明强调 tuple 语义即可；或改为 direct=类，indirect=by_url/by_name，避免把入口函数与目标混写。  
- required_fix:  
  - 选择其一：  
    - A) direct 仅保留最终类 `celery.backends.redis.RedisBackend`，indirect 放 `by_url`/`by_name`，在说明里写明返回 `(cls, url)`；  
    - B) 若保留 `by_url` 作为 direct，需解释“direct=入口函数、最终目标=tuple”并确认评分/解析不会混淆。当前稿未给出这一防混淆说明。

---

## 可视为稳定收口的新增内容
- Eval：`celery_medium_017`, `celery_medium_020`（均为降级并更名后的版本）
- Few-shot：`B03`, `B04`

## 仍需最后修订
- Few-shot：`E03`（澄清 direct/目标与 tuple 返回语义，去除潜在 schema 歧义）
