# Eval Round 4 Type A/D Set2 - R2

> 基于 `docs/drafts/review_round17_eval_round4_findings.md` 修订。  
> 本稿不改原文件 `eval_round4_type_ad_set2.md`，仅处理 Candidate 04-06。  
> 口径：沿用 `docs/dataset_schema.md`，并执行 round15/round17 gate（单问单判、最小闭包、可回溯、全局唯一 ID）。

## 处理总表

| candidate | status | new_id | note |
|---|---|---|---|
| 04 (beat reserve/send) | park | - | reviewer 明确不建议继续以当前版本打磨；从本轮 formal 候选移出 |
| 05 (PersistentScheduler startup reset) | keep_revised | `celery_hard_024` | 保留 hard，修复 ID 冲突并显式排除相邻 `clear()` 分支歧义 |
| 06 (`--disable-prefetch`) | keep_revised | `celery_hard_025` | 采用“运行时真正改写 `can_consume` 的方法是谁”收口，入口与依赖收紧到 `tasks.py` |

## Park 项

### Candidate 04（park）

- 结论：本轮不继续打磨，不进入 formal pool。
- 原因：当前题面本质是局部 helper tracing，无法稳定满足 round4 对 `Type A / Type D / hard` 的区分度要求；继续微调字段收益低、误导风险高。

## 保留项 JSON 草案（R2）

### celery_hard_024（Candidate 05）

```json
{
  "id": "celery_hard_024",
  "difficulty": "hard",
  "category": "persistent_scheduler_startup_reset",
  "failure_type": "Type A",
  "implicit_level": 4,
  "question": "`PersistentScheduler` 启动阶段若持久化 store 缺失 `utc_enabled` 元数据字段，直接触发 reset（`self._store.clear()`）的方法是哪一个？",
  "source_file": "celery/beat.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.beat.PersistentScheduler._create_schedule"
    ],
    "indirect_deps": [
      "celery.beat.PersistentScheduler.setup_schedule"
    ],
    "implicit_deps": []
  },
  "reasoning_hint": "题目限定的是“缺失 metadata 字段”场景，命中 `_create_schedule` 内 `elif 'utc_enabled' not in self._store: self._store.clear()` 分支。需要显式排除 `setup_schedule` 中另两条值变化触发的 `clear()`：`stored_tz != tz` 与 `stored_utc != utc`，它们属于“值变更”而非“字段缺失”。",
  "source_note": "Anchors: celery/beat.py:531-544, 545-556, 569-590 (esp. 587-589). Cross-check tests: t/unit/app/test_beat.py:745-773."
}
```

Hard/Type A 自检：该题需要在同一启动链中区分“缺失字段 reset”与“配置值变更 reset”两个相邻竞争分支，存在阶段性截断风险，不是单纯同函数关键词检索。

### celery_hard_025（Candidate 06）

```json
{
  "id": "celery_hard_025",
  "difficulty": "hard",
  "category": "disable_prefetch_runtime_can_consume_patch",
  "failure_type": "Type A",
  "implicit_level": 5,
  "question": "在 `worker_disable_prefetch=True` 且 broker 为 Redis 的前提下，运行时真正改写 `channel_qos.can_consume` 的方法是哪一个？",
  "source_file": "celery/worker/consumer/tasks.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.worker.consumer.tasks.Tasks.start"
    ],
    "indirect_deps": [],
    "implicit_deps": []
  },
  "reasoning_hint": "题面已收口为运行时改写点而非 CLI 端到端链。`Tasks.start` 中先判断 `worker_disable_prefetch`，再做 Redis gate（`driver_type == 'redis'`）；仅在该分支内通过 `MethodType` 将自定义 `can_consume` 绑定到 `channel_qos`。",
  "source_note": "Anchors: celery/worker/consumer/tasks.py:29-30, 54-78. Behavior checks: t/unit/bin/test_worker.py:87-99, 117-127."
}
```

Hard/Type A 自检：该题依赖运行时前置条件（配置值 + broker 类型）与 bootstep 启动阶段行为，错误忽略任一条件都会把答案误判为 CLI 或静态配置层。

