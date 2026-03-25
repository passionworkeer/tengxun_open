# Review Round 5 (Round 2 Fixes Only)

只审本轮修订稿，不重复 Round1/3/4 已结论的未改条目。结论用 `accept / needs_more_fix / reject`。聚焦：是否真正消除上轮 objection、是否仍与 eval 泄漏或重复、是否引入新 schema 风险。

---

## Eval Easy / Medium（Round2 修订项）

### easy_005
- verdict: accept  
- reasons: direct 已改为 `get_current_app`，Proxy 下沉 implicit，口径与问题一致；implicit_level 提升到 3 覆盖 fallback。  
- residual risk: 无。

### easy_006
- verdict: accept  
- reasons: direct 命中 getter，indirect 落到 `_task_stack.top`，Type B 与 implicit 拆分自洽；消除了“Proxy 作为终点”的摇摆。  
- residual risk: 无。

### easy_008
- verdict: accept  
- reasons: 题面明确“类定义 FQN”，implicit_level 下调为 1，避免 callable 歧义；链路与 schema 对齐。  
- residual risk: 无。

### medium_006
- verdict: accept  
- reasons: direct 同时列触发点 `_get_backend` 和目标类，implicit_level 下调，差异点（by_url 拆分）在 note 中说明，去重风险可接受。  
- residual risk: 无。

### medium_007（重写为 fallback loader 题）
- verdict: accept  
- reasons: 彻底换题，目标唯一（default.Loader），链路包含 fallback current_app + alias 解析，可复核且不与已有样本重叠；Type E、implicit_level=3 合理。  
- residual risk: 命名仍沿用 `medium_007` 但语义已变，集成时留意说明。

---

## Eval Hard（Round2 修订项）

### celery_hard_013
- verdict: accept  
- reasons: 题面/字段改为 `tasks -> finalize` 组合，闭合了“触发 vs 执行”歧义；implicit_level 下调。链路现可复核且唯一。  

### celery_hard_015
- verdict: accept  
- reasons: direct 命中 `_autodiscover_tasks`，trigger 链放入 indirect+implicit，补齐 `Signal.send` 闭环，已解决前次跳步问题。  

### celery_hard_018
- verdict: accept  
- reasons: 前置条件写明，implicit 补上 env/settings；direct/indirect 表达“解析到 DjangoTask 基类”口径清晰，剩余风险可控（条件样本）。  

### celery_hard_020（降级为 medium）
- verdict: needs_more_fix  
- reasons: 虽已降级并补充触发点，但 ID/文件仍标 `hard_020`，易与难度统计冲突；推荐重命名 ID（如 `medium_009`）并迁出 hard 槽位后再集成。  

---

## Few-shot（Round2 修订项）

### Few-shot B02
- verdict: accept  
- reasons: 题干聚焦 pending 兑现路径，direct 引入 `maybe_evaluate`，已与 eval 主链拉开差异；无新增 schema 风险。  

### Few-shot B03
- verdict: needs_more_fix  
- reasons: 仍与 eval `celery_hard_014` 共用同一 built-in 任务与 `_task_from_fun` 终点，泄漏风险未消除；虽补了回调闭环，但去重问题仍在。需改成非 backend_cleanup 的内置示例或调整终点。  

### Few-shot B04
- verdict: needs_more_fix  
- reasons: 终点仍依赖 `_task_from_fun`，与多条 eval Type B 主链重叠；虽突出命名/查表，但 direct/implicit 仍指向注册终点，泄漏风险未解。需进一步弱化/移除 `_task_from_fun` 终点或换题。  

### Few-shot C02（新题：bugreport）
- verdict: accept  
- reasons: 三跳再导出 + current_app 隐式，未与现有 eval 重复，覆盖 Type C 多跳链，格式符合 schema。  

### Few-shot C03（改题：subtask -> signature）
- verdict: accept  
- reasons: 聚焦顶层别名链，去除了 current_app 主题，链路清楚且无重复。  

### Few-shot E02
- verdict: accept  
- reasons: 修正 FQN，写明前置条件与返回对象，结构自洽；未见新 schema 风险。  

### Few-shot E03
- verdict: needs_more_fix  
- reasons: 虽加入 override_backends 场景，但新增字段 `expected_return` 不在 few-shot schema 中，可能破坏解析；同时 direct 只给类，未体现 tuple 返回要求。需移除额外字段，或把 tuple 语义写入 reasoning/answer而不扩 schema。  

### Few-shot E04
- verdict: accept  
- reasons: 前置条件（导入前设 env）已写清，implicit/indirect 符合 schema；与 eval 样本不重复。  

---

## 可立即集成的新增条目
- Eval easy/medium round2：`easy_005`, `easy_006`, `easy_008`, `medium_006`, `medium_007`  
- Eval hard round2：`celery_hard_013`, `celery_hard_015`, `celery_hard_018`  
- Few-shot round2：`B02`, `C02`, `C03`, `E02`, `E04`

## 需进一步修订后再考虑
- Eval hard：`celery_hard_020`（需改 ID/槽位匹配 medium）  
- Few-shot：`B03`, `B04`, `E03`

## 建议直接替换/重写
- Few-shot B03/B04：避免再以 `_task_from_fun` 为终点，可换成非注册型 Type B 失败模式。  
- Few-shot E03：去掉非 schema 字段并明确 tuple 返回写法，否则保持 hold。
