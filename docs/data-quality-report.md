# 数据质检报告
**Owner**: self (Owner 意识拉满)
**日期**: 2026-03-25
**Celery 版本**: b8f85213f45c (2026-03-15)
**评测集 v1**: `data/eval_cases.json` (12 条)
**评测集 Draft**: `data/eval_cases_migrated_draft_round4.json` (32 条)
**Few-shot**: `data/fewshot_examples_20.json` (20 条)
**微调集**: `data/finetune_dataset_500.jsonl` (当前 0 条有效记录，guard 已收口)

---

## 一、硬卡点（影响实验有效性，P0 必须解决）

### P0-1：正式评测集仍严重不足，最新 draft 也还没到 50

| 文件 | 当前条数 | 要求 | 缺口 |
|------|---------|------|------|
| `eval_cases.json` (v1) | 12 条 | ≥ 50 条 | **-38 条** |
| `eval_cases_migrated_draft_round4.json` | 32 条 | ≥ 50 条 | **-18 条** |

**影响**：
- 10 组消融实验矩阵在 12 条样本上跑，统计意义接近零
- `eval_cases_migrated_draft_round4.json` 是当前最完整的版本，但仍然只有 32 条
- 要求中明确写"纯人工从真实源码标注 ≥ 50 条"，缺口的每一分都直接影响实验可信度

**建议动作**：先把 round 4 已过双轮严格审稿的 4 条高价值 hard 样本继续留在待集成主线上，再优先补 Type D 和剩余 hard 配额。

---

### P0-2：正式集、旧 draft、round4 draft 三套口径并存

当前至少有三套数据口径并存：
- `eval_cases.json` (v1)：用 `gold_fqns: [str]` 格式，只有 `reasoning_hint`
- `eval_cases_migrated_draft.json`：旧的新-schema 迁移 draft（28 条）
- `eval_cases_migrated_draft_round4.json`：纳入 round4 后的最新 draft（32 条）

**对齐问题**：
1. v1 里 `easy_001` 和 `easy_002` 没有 `failure_type` 字段
2. round4 draft 已经比旧 draft 更接近当前真实状态，但 formal 仍没有切换
3. **正式评测到底用哪套文件，仓库里仍然是 hold 状态**

**建议动作**：继续把 `eval_cases_migrated_draft_round4.json` 当作唯一工作草案，但在 strict review 清完多 target / 条件样本之前，不要覆盖正式 `eval_cases.json`。

---

### P0-3：round4 draft 里仍有 9 条样本至少一个依赖数组为空

以下 case 的 `indirect_deps` 或 `implicit_deps` 为空数组：

| Case ID | 空字段 | 说明 |
|---------|-------|------|
| easy_001 | indirect_deps, implicit_deps | 单跳 re-export，确实没有间接依赖，可接受 |
| easy_002 | indirect_deps, implicit_deps | 同上，可接受 |
| medium_004 | implicit_deps | 需确认是否真的没有隐式依赖 |
| hard_002 | implicit_deps | 需确认 |
| hard_003 | implicit_deps | 需确认 |
| easy_007 | indirect_deps, implicit_deps | 需读源码确认 |
| easy_008 | implicit_deps | 需读源码确认 |
| celery_hard_024 | implicit_deps | round4 新题，当前是“缺失字段 reset”收口题，空 implicit 可能成立但要保留说明 |
| celery_hard_025 | indirect_deps, implicit_deps | round4 新题，题面已刻意收口为运行时 patch 点，空链可成立但要确认判题闭包是否过窄 |

**说明**：空数组有两种可能——（1）确实没有该类型依赖；（2）数据未填全。需要逐条读源码确认。

---

## 二、Few-shot 示例库 — 当前正式池的 FQN 结论

旧版这部分的问题，不是“few-shot 里有一堆 FQN 编错了”，而是把历史问题、轻微表述问题、以及已经修过的问题混写成了同一批 live issue。

基于当前正式文件 `data/fewshot_examples_20.json` 和源码快照，至少可以明确三件事：

### 2.1 旧版最显眼的两个问题已经不应继续按 live issue 处理

**E02**
- 当前正式文件里，`indirect_deps` 已经写成 `kombu.utils.imports.symbol_by_name`
- 这和 `celery/fixups/django.py` 里的真实 import 路径一致
- 因此，E02 不应再被统计为当前正式 few-shot 池的 FQN 错误

**D04**
- `external/celery/celery/utils/dispatch/signal.py` 虽然有 `# pragma: no cover`
- 但当前源码快照下，`external/celery/t/unit/utils/test_dispatcher.py` 里可以找到 `dispatch_uid` 去重相关测试
- 所以，D04 不应再写成“无测试覆盖、无法验证”

### 2.2 D02 这类问题更适合归到“说明粒度”而不是“FQN 错误”

- 当前正式 few-shot 里的 D02 已经明确写出：
  - `Celery.task`
  - `_task_from_fun`
  - `gen_task_name`
  - `self._tasks` 的 first-wins 语义
- 它未必已经是最优写法，但不能再直接沿用旧版“thin wrapper 过薄，因此当前有 bug”的说法

### 2.3 当前 few-shot 的主要风险已经不是 FQN 伪造

当前 formal few-shot 池更现实的问题是：

- 它和正式 `eval` 的结构覆盖仍有错位
- 它不能自动证明 few-shot 没有泄漏风险
- 它也不能替代 formal `eval` 的样本规模与 gate

也就是说，**few-shot 的核心风险已经从“路径是不是假的”转移到“教学信号是否和正式评测结构匹配”**。

---

## 三、评测集 v1 — 源码逐条验证结论

### ✅ 验证正确（11/12）

| Case | FQN | 源码核查 |
|------|-----|---------|
| easy_001 | `celery.app.base.Celery` | ✅ `recreate_module` → `celery.app` → `from .base import Celery` |
| easy_002 | `celery.app.shared_task` | ✅ `by_module` 懒加载映射 |
| easy_003 | `celery.loaders.default.Loader` | ✅ `LOADER_ALIASES['default']` |
| easy_004 | `celery.concurrency.prefork.TaskPool` | ✅ `ALIASES['processes']` |
| medium_001 | `celery.backends.redis.RedisBackend` | ✅ `BACKEND_ALIASES['redis']` |
| medium_002 | `celery.loaders.app.AppLoader` | ✅ `LOADER_ALIASES['app']` |
| medium_004 | `celery.utils.imports.gen_task_name` | ✅ `Celery.gen_task_name` wrapper → `gen_task_name(self, name, module)` |
| hard_001 | `celery.app.base.Celery._task_from_fun` | ✅ `shared_task` 内 lambda |
| hard_002 | `celery.app.base.Celery._task_from_fun` | ✅ `_task_from_fun` 非 execv 主路径 |
| hard_003 | `celery._state._announce_app_finalized` | ✅ `_state.py:49` 函数定义 |
| hard_004 | `celery.worker.request.Request` | ✅ `strategy.py:126` + `Task.Request = 'celery.worker.request:Request'` |

### ⚠️ 环境条件陷阱（1/12）

**medium_003**：`celery.concurrency.thread.TaskPool`

```python
# celery/concurrency/__init__.py:19-24
try:
    import concurrent.futures
except ImportError:
    pass
else:
    ALIASES['threads'] = 'celery.concurrency.thread:TaskPool'
```

**问题**：`concurrent.futures` 是 Python 3.2+ 标准库，但某些裁剪环境或 Docker 镜像可能不包含。如果评测时 `concurrent.futures` 导入失败，`ALIASES['threads']` 不存在，`get_implementation('threads')` 会抛异常。

**当前题目**：没有 `environment_preconditions` 字段，模型会直接给出答案，但运行时可能报错。

**建议**：migrated_draft 里加：
```json
"environment_preconditions": ["Python >= 3.2 with concurrent.futures available"]
```

---

## 四、数据 schema 对齐问题

### 4.1 v1 和 migrated_draft 的 failure_type 不一致

| Case | v1 failure_type | migrated_draft failure_type | 一致性 |
|------|----------------|--------------------------|--------|
| easy_001 | 无字段 | `Type C` | ⚠️ 需对齐 |
| easy_002 | 无字段 | `Type B` | ⚠️ 需对齐 |
| ... | ... | ... | ... |

v1 完全没有 `failure_type`，migrated_draft 全部补了。但 easy_001 标 Type C、easy_002 标 Type B，这个归因需要确认（是否经过 Bad Case 验证，还是拍脑袋填的）。

### 4.2 round4 draft 已补进 Type A，但分布仍不均衡

`eval_cases_migrated_draft_round4.json` 当前 breakdown:
- Type C: 5
- Type E: 13
- Type B: 8
- Type D: 2
- **Type A: 4**

这比旧 28 条 draft 已经好很多，至少 Type A 不再是 0。但问题并没有完全解决：

- Type A 虽然补进来了，但目前主要来自 round4 新增 4 条，尚未正式升格
- Type D 仍然只有 2 条，和 few-shot 池里的 D01-D04 明显不对齐
- Type E 仍然明显偏多，说明评测集分布还没有平衡下来

### 4.3 round4 draft 的 difficulty 分布已经可见，但还没用 baseline 反证

当前分布：

- easy: 8
- medium: 10
- hard: 14

这个分布从配额上比旧 draft 更接近目标，但仍需用 baseline 跑出来的实际分数去反证 `easy / medium / hard` 标注是否站得住。

---

## 五、Few-shot 到评测集的对齐缺失

### 5.1 Few-shot 覆盖类型 vs 评测集覆盖类型的对应关系

| Type | Few-shot 有 | migrated_draft 有 | 对齐 |
|------|------------|-----------------|------|
| Type A | A01, A02 (2条) | 4 条 | ⚠️ 已补进，但尚未 formal |
| Type B | B01-B05 (5条) | 8 条 | ✅ 有覆盖 |
| Type C | C01-C05 (5条) | 5 条 | ✅ 有覆盖 |
| Type D | D01-D04 (4条) | 2 条 | ⚠️ 不完整 |
| Type E | E01-E04 (4条) | 13 条 | ✅ 有覆盖 |

**核心问题**：Type A 已经不再是空白，但 few-shot 和评测集的结构性错位还在。现在最突出的不是“Type A 为 0”，而是：

1. round4 新增的 Type A / hard 样本还停留在 draft，没进入正式池；
2. Type D 仍然偏少，few-shot 对 D 类的引导没有足够评测数据承接；
3. PE 的 few-shot 设计已经比评测集走得更远，导致“prompt 做好了，但验证集不够强”的错位仍然存在。

---

## 六、Owner 揪头发 — 还有哪些没说出来的坑

> 💼 [P8 自检] 颗粒度够了吗？冰山下面还有冰山吗？

**坑 1：微调数据集从哪里来？**
- `data/finetune_dataset_500.jsonl` 现在仍是空占位，`valid_records=0`
- 但现在不是“完全没入口”了：`data_guard.py` 已经能卡 `min_records=500` 和 `min_hard_ratio=0.3`
- 真正没做完的是：语义级 anti-hallucination 校验、500 条高质量数据生成、真实 trainer backend
- 这个 gap 仍然是 M4 的硬卡点，只是现在 blocker 已经被明确暴露，不再是假绿灯

**坑 2：migrated_draft 的 difficulty 分布是人为设定还是实验测量？**
- easy/medium/hard 的划分标准是什么？
- 有没有通过基线模型跑过分數分布来验证？
- 还是拍脑袋分的？

**坑 3：migrated_draft 里部分 case 的 `reasoning_hint` 和 v1 完全一样**
- 说明 migrated draft 是从 v1 改写格式而来，不是重新从源码挖掘
- "人工标注"这四个字是否存疑？

**坑 4：Few-shot 里的 B02 — `celery.local.maybe_evaluate` 的调用上下文**
```python
# base.py:667-669
pending = self._pending
while pending:
    maybe_evaluate(pending.popleft())
```
这个链路是对的，但 B02 的 `implicit_deps` 里还包含了 `celery._state._announce_app_finalized` — 需要确认这个函数确实在 finalize 时被调用（已在 `_state.py:49` 确认）。

---

## 七、优先级 Action List

| 优先级 | 问题 | Owner 动作 | 验收标准 |
|-------|------|-----------|---------|
| 🔴 P0 | 最新 round4 draft 仍缺 18 条 | 继续补高价值 Type D / hard，并保住已过审的 4 条 round4 候选 | `eval_cases_migrated_draft_round4.json` ≥ 50 条 |
| 🔴 P0 | 正式数据源仍未冻结 | 继续以 round4 draft 作为唯一工作草案，但不提前覆盖 formal | formal 升格前完成 strict review 清理 |
| 🔴 P0 | Type D 仍偏少 | 继续补 Type D 到 4-5 条，和 few-shot D 池形成基本对应 | Type D 在评测集不再明显偏科 |
| 🟡 P1 | medium_003 环境条件缺失 | 加 `environment_preconditions` | 运行时不会因 missing concurrent.futures 报错 |
| 🟡 P1 | FQN 报告口径混淆 | 把“FQN 可溯源性”与“实验可用性”拆成两层文档结论 | 不再出现旧版 76% / 97% / 87% 这类混口径统计 |
| 🟡 P1 | Few-shot 历史问题已修但文档未刷新 | 在所有状态文档里同步 E02 已修、D04 有测试、D02 不再算 live FQN 问题 | few-shot 相关结论页不再互相矛盾 |
| 🟡 P1 | round4 draft 9 条空依赖 | 逐条读源码确认是真的没有还是未填 | 确认每条空依赖都有理由 |
| 🟡 P1 | 微调数据集 pipeline | 设计评测集→微调集的 AST 转化流程，并补真实 trainer backend | `finetune_dataset_500.jsonl` 不再是 0 valid |
| 🟢 P2 | round4 的 4 条新样本仍未 formal | 把 `celery_hard_121 / 122 / 024 / 025` 持续留在待集成主线 | formal 升格时不再重复返工 |
| 🟢 P2 | difficulty 划分标准未验证 | 基线跑分验证 easy/medium/hard 分布 | easy 平均分 > medium > hard，有数据支撑 |

---

## 八、数据质量总评

```
评测集 v1:              12 条    ████████░░░░ 24%  (缺36条)
评测集 round4 draft:    32 条    ████████████████░░░░ 64%  (缺18条)
Few-shot 示例:          20 条    ████████████████████ 100% ✅
Celery 源码版本:        b8f85213  ✅ 已锁定
FQN 可溯源性报告:       已重写，旧 87% / 27/31 口径作废
环境条件陷阱:           1 条未标注 (medium_003)
覆盖率 Type A:          4 条 in round4 draft ⚠️（仍未 formal）
微调数据集:             0 valid，guard 已收口，trainer 仍是 scaffold 🔴
```

**结论**：当前 few-shot 的主要问题已经不是“大量 FQN 编错”，而是文档口径混淆和 formal eval 侧承接不足。评测集从 28 提升到了 32 条 draft，但 formal 仍未冻结；Type A 已补进，Type D 仍偏少；微调线不再是假绿灯，但离可训练还差真实 500 条数据和 trainer backend。**下一步仍然是先把评测集从 32 补到 50，并保持 strict review，不要为凑数提前升 formal。**
