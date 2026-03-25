# Eval Round 4 - Type A/D Set 2 (EVAL-021)

> 已按最新 `docs/dataset_schema.md` 字段起草，并按 `docs/drafts/review_round15_formal_pool_safety.md` gate 收紧为“单问单判、最小闭包、可物理回溯”。
> 本文件仅覆盖 Candidate 04-06：beat reserve/send、PersistentScheduler startup reset、`--disable-prefetch`。

## 总表

| id | candidate | difficulty | category | failure_type | implicit_level | source_file | question 摘要 |
|---|---:|---|---|---|---:|---|---|
| celery_hard_021 | 04 | hard | beat_reserve_before_send | Type D | 4 | celery/beat.py | `tick` 的 due 分支里，发送前先推进条目状态的方法是谁 |
| celery_hard_022 | 05 | hard | persistent_scheduler_startup_reset | Type A | 4 | celery/beat.py | 启动时缺失 `utc_enabled` 元数据，触发 reset 的直接方法是谁 |
| celery_hard_023 | 06 | hard | disable_prefetch_redis_effective_gate | Type A | 5 | celery/bin/worker.py | `worker_disable_prefetch=True` 且 Redis 时，真正改写 `can_consume` 的方法是谁 |

## 逐条 JSON 草案

### celery_hard_021 (Candidate 04)

```json
{
  "id": "celery_hard_021",
  "difficulty": "hard",
  "category": "beat_reserve_before_send",
  "failure_type": "Type D",
  "implicit_level": 4,
  "question": "`Scheduler.tick` 在 `is_due=True` 分支里，发送任务前先推进该条目运行计数与时间戳的关键方法是哪一个？",
  "source_file": "celery/beat.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.beat.Scheduler.reserve"
    ],
    "indirect_deps": [
      "celery.beat.Scheduler.tick",
      "celery.beat.ScheduleEntry._next_instance"
    ],
    "implicit_deps": []
  },
  "reasoning_hint": "`tick` 的 due 分支先调用 `reserve(entry)`，再调用 `apply_entry`。`reserve` 内部通过 `next(entry)` 走到 `ScheduleEntry._next_instance`，写回新的 `last_run_at/total_run_count`。",
  "source_note": "Anchors: celery/beat.py:351-356, 389-391, 134-141. Design intent is echoed in celery/beat.py:394-397 comment (advance before execute)."
}
```

### celery_hard_022 (Candidate 05)

```json
{
  "id": "celery_hard_022",
  "difficulty": "hard",
  "category": "persistent_scheduler_startup_reset",
  "failure_type": "Type A",
  "implicit_level": 4,
  "question": "`PersistentScheduler` 启动阶段如果持久化 store 缺失 `utc_enabled` 元数据字段，负责触发 reset（`clear`）的直接方法是哪一个？",
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
  "reasoning_hint": "`setup_schedule` 在启动早期先调用 `_create_schedule`。若 metadata 缺失（如 `utc_enabled`），该方法在对应分支直接执行 `self._store.clear()`，然后才进入 `merge_inplace`。",
  "source_note": "Anchors: celery/beat.py:531-544, 569-590 (especially 587-589). Related startup-path tests: t/unit/app/test_beat.py:745-773."
}
```

### celery_hard_023 (Candidate 06)

```json
{
  "id": "celery_hard_023",
  "difficulty": "hard",
  "category": "disable_prefetch_redis_effective_gate",
  "failure_type": "Type A",
  "implicit_level": 5,
  "question": "在 `worker_disable_prefetch=True` 且 broker 为 Redis 的前提下，真正改写 `channel_qos.can_consume` 以生效“禁预取”的方法是哪一个？",
  "source_file": "celery/bin/worker.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.worker.consumer.tasks.Tasks.start"
    ],
    "indirect_deps": [
      "celery.bin.worker.worker"
    ],
    "implicit_deps": [
      "celery.worker.state.reserved_requests"
    ]
  },
  "reasoning_hint": "`--disable-prefetch` 先经 CLI 写入 `app.conf.worker_disable_prefetch`；真正生效点在 `Tasks.start`。仅当 `driver_type == 'redis'` 时才 monkey-patch `channel_qos.can_consume`，否则仅 warning 后返回。",
  "source_note": "Anchors: celery/bin/worker.py:185-190, 326-327; celery/worker/consumer/tasks.py:54-78. Tests: t/unit/bin/test_worker.py:74-84, 87-99, 117-127."
}
```

