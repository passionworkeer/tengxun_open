# Review Round 18 - Eval Round 4 Revision 2

本轮只审以下 revision 2 文件：

- `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1_r2.md`
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2_r2.md`

审稿依据：

- `E:\desktop\tengxun\docs\drafts\review_round16_eval_round4_gate.md`
- `E:\desktop\tengxun\docs\drafts\review_round15_formal_pool_safety.md`
- `E:\desktop\tengxun\docs\dataset_schema.md`
- 对照上一轮：`E:\desktop\tengxun\docs\drafts\review_round17_eval_round4_findings.md`

默认口径不变：只看仓库事实，不替作者补做大段产出，不因为“方向对了”就放松 `Type A / Type D / hard` 门槛。

---

## Overall Assessment

### R2 是否明显优于原稿
- verdict: `yes`
- reasons:
  - 原稿最硬的系统性问题之一是 ID 重号；r2 已改成 `celery_hard_121/122/024/025`，当前未见与仓库中其他 eval 草案直接冲突。
  - 原稿里最危险的两条题都做了实质性修订：
    - bootstep 题从“局部 helper tracing”重写成“实例化先于 include gate 的生命周期断点题”
    - disable-prefetch 题从“CLI/运行时口径混杂”收紧到“运行时真正改写 `can_consume` 的方法是谁”
  - 两份 r2 都更接近 round 4 gate 要求的“单问单判 + 最小闭包 + 明确前提 + 真正 high-value hard”。

### 可继续进入 formal 起草队列的题
- current_recommendation:
  - `celery_hard_121`
  - `celery_hard_122`
  - `celery_hard_024`
  - `celery_hard_025`
- note:
  - 其中 `celery_hard_122` 仍建议带修推进，不建议原样冻结。

---

## File Review

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1_r2.md / park decision for former Candidate 01`
- verdict: `accept`
- reasons:
  - 这次没有再强行把原 `worker_acks_late_failure_branch` 留在 round 4 `Type A / hard` 池里，这是正确收缩。
  - 该素材在上一轮的问题并不是字段小修能救，而是题材本身更像局部分支 tracing；r2 选择 `park`，优于继续硬保留。
- required_fix:
  - 无。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1_r2.md / celery_hard_121`
- verdict: `accept`
- reasons:
  - 相比原稿，r2 明显补强了链路闭合：`Celery.autodiscover_tasks -> Celery._autodiscover_tasks -> BaseLoader.import_default_modules -> BaseLoader.autodiscover_tasks -> loaders.base.autodiscover_tasks -> find_related_module`，不再停在含糊的 loader 层。
  - 题目单一，值语义已被成功收缩为 FQN 题：现在不是问“哪些错误会被吞/重抛”，而是问“真正做判定的函数是谁”。
  - `Type A / hard` 标签成立。这里确实有延迟注册、运行时触发、跨文件收敛和错误判定断点，任一层截断都会把触发点误当判定点。
  - `direct / indirect / implicit` 基本自洽，没有再把 side effects 混进主答案。
- required_fix:
  - 无阻断修复。若作者还要再收紧，可考虑把 `reasoning_hint` 里“只要走到 import_default_modules”这句话保留，避免后续 reviewer 又把触发者写死成 worker 路径。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1_r2.md / celery_hard_122`
- verdict: `accept_with_fix`
- reasons:
  - 这是 r2 最重要的改写之一，方向明显优于原稿。原题停在 `StartStopStep.include` 局部 helper tracing；现在改成“实例化先于 include gate”的生命周期断点题，终于具备 round 4 想要的阶段性风险。
  - 题目本身单一，且明确把误判点钉在“include gate 并不是实例化 gate”。
  - `direct_deps = celery.bootsteps.Blueprint.apply` 是合理的，因为真正执行 `step = S(parent, **kwargs)` 的就是它。
  - 但最小闭包仍略松：`celery.bootsteps.Blueprint._finalize_steps` 对回答“谁执行实例化”不是必需节点，更像 boot order 准备噪声。
  - `source_file = celery/worker/worker.py` 是可以接受的入口文件，但 `ground_truth` 里的 decisive node 实际在 `bootsteps.py`；这不构成错误，只要求后续 formal 起草时继续把入口与目标分清。
- required_fix:
  - 从 `indirect_deps` 中删除 `celery.bootsteps.Blueprint._finalize_steps`，收紧最小闭包。
  - 保留 `WorkController.__init__` 作为入口链节点、`StartStopStep.include` 与 `Step._should_include` 作为对照链节点即可。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2_r2.md / park decision for Candidate 04`
- verdict: `accept`
- reasons:
  - r2 没再试图把 beat reserve/send 素材包装成 `Type D / hard`，这是对上一轮 strict finding 的直接吸收。
  - 该题材此前最大问题就是分类失真和 high-value 不足；现在选择移出 formal 候选池，比继续微修字段更正确。
- required_fix:
  - 无。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2_r2.md / celery_hard_024`
- verdict: `accept`
- reasons:
  - r2 已把上一轮最关键的歧义点写清：题目限定的是“缺失 `utc_enabled` 元数据字段”的启动阶段 reset，而不是 `stored_tz != tz` / `stored_utc != utc` 这两条值变化 reset。
  - 这次 `reasoning_hint` 明确排除了相邻 `clear()` 分支，达到了 strict reviewer 要求的“说明为什么不是另一个最像答案”的标准。
  - 问题单一、最小闭包简洁、无值语义越界，且仍保留了启动阶段断点这一 round 4 高价值特征。
  - 与原稿相比，已经从“accept_with_fix”提升到可直接进入 formal 起草。
- required_fix:
  - 无。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2_r2.md / celery_hard_025`
- verdict: `accept`
- reasons:
  - 这是另一条明显优于原稿的修订。原稿最大问题是题面问运行时改写点，入口和依赖却仍偏向 CLI；r2 现在把 `source_file`、题目口径和 `direct_deps` 全部收到了 `celery/worker/consumer/tasks.py`。
  - `direct_deps = celery.worker.consumer.tasks.Tasks.start` 正确，且足够。题目问的就是“运行时真正改写 `channel_qos.can_consume` 的方法是谁”，不再需要把 CLI callback 或 `reserved_requests` 等实现细节混入闭包。
  - 运行时前提写得比原稿干净：`worker_disable_prefetch=True`、broker 为 Redis，且发生在 consumer bootstep 启动阶段。这已经足以支撑 `Type A / hard`。
  - 特别检查通过：bootstep 生命周期没有再被误写成 CLI 配置题，最小闭包也已经显著收紧。
- required_fix:
  - 无。

---

## Special Check

### Bootstep 重写题
- target: `celery_hard_122`
- verdict: `improved_but_still_trim`
- reasons:
  - 相比上一版，这题已经从“不建议继续打磨”提升到“可继续推进”。
  - 剩余问题不是方向错，而是闭包里仍有一个可删噪声节点 `Blueprint._finalize_steps`。

### Disable-prefetch 修订题
- target: `celery_hard_025`
- verdict: `passed_special_check`
- reasons:
  - 这次修订抓住了上一轮的核心 objection：不再混用 CLI 入口题与运行时 patch 题。
  - 题干、入口文件、direct_deps 三者终于同口径，当前版本可以继续 formal 起草。

---

## Final Recommendation

### 可继续推进
- `celery_hard_121`
- `celery_hard_122`
- `celery_hard_024`
- `celery_hard_025`

### 推进优先级
- first:
  - `celery_hard_121`
  - `celery_hard_024`
  - `celery_hard_025`
- second:
  - `celery_hard_122`
  - 先删掉一处噪声 indirect，再进入 formal 起草即可

### 本轮不继续推进的题材决策
- former Candidate 01: `park` decision accepted
- Candidate 04: `park` decision accepted
