# Eval High-Value Candidates Round 4

目标：继续沿现有 plan 扩 eval，但不再堆简单 alias 题，优先补 `Type A / Type D / hard`。

本稿只给候选题，不直接入正式评测集。每题都需要后续按 `dataset_schema.md` 补齐正式字段并走双 reviewer。

---

## Candidate 01

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/worker/request.py`
- draft_question：
  - `acks_late=True` 时，普通异常、`TimeLimitExceeded`、`WorkerLostError`、`Reject`、`Ignore`、`Retry` 分别会走 `ack`、`reject(requeue=True)`、`reject(requeue=False)`、`mark_as_failure` 中的哪条路径？
- why_high_value：
  - 这是 worker 行为矩阵题，真实工程风险高，能区分“背概念”和“读实现”。
- source_anchors：
  - `external/celery/celery/worker/request.py:529`
  - `external/celery/celery/worker/request.py:579`
  - `external/celery/t/unit/worker/test_request.py:960`
- risk：
  - 题面必须写清 `acks_late` 与相关配置前提，避免把默认值说错。

## Candidate 02

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/app/base.py`
- draft_question：
  - `app.autodiscover_tasks(..., force=False)` 到底在什么时候真正执行，哪些 import 错误会被吞掉，哪些会重新抛出？
- why_high_value：
  - 跨 `app/base`、`loader/base`、`signal` 三层，是 Celery 自动发现任务最常见的误判点。
- source_anchors：
  - `external/celery/celery/app/base.py:779`
  - `external/celery/celery/app/base.py:819`
  - `external/celery/celery/loaders/base.py:97`
  - `external/celery/celery/loaders/base.py:251`
  - `external/celery/celery/utils/dispatch/signal.py:258`
  - `external/celery/t/unit/app/test_loaders.py:267`
- risk：
  - 触发者不只 worker，CLI 路径也可能调用 `import_default_modules()`，题面不要把触发时机写死。

## Candidate 03

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/bootsteps.py`
- draft_question：
  - 如果一个 bootstep 的 `include_if()` 返回 `False`，它的 `__init__`、依赖展开、`create()`、`parent.steps` 挂载分别还会不会发生？
- why_high_value：
  - 这是扩展作者最容易理解错的生命周期顺序题，必须真正看实现。
- source_anchors：
  - `external/celery/celery/bootsteps.py:186`
  - `external/celery/celery/bootsteps.py:199`
  - `external/celery/celery/bootsteps.py:224`
  - `external/celery/celery/bootsteps.py:333`
  - `external/celery/t/unit/worker/test_bootsteps.py:328`
- risk：
  - 题面要把“实例化”和“纳入运行步骤”分开问，否则会变成双问题。

## Candidate 04

- failure_type：`Type D`
- difficulty：`hard`
- entry_file：`celery/beat.py`
- draft_question：
  - 为什么 beat 会在真正发送任务之前先 `reserve()` 更新 `last_run_at/total_run_count`，这样做对“发送失败后下一轮调度”有什么后果？
- why_high_value：
  - 这是典型的设计取舍题，能检验模型是否能从代码里读出“避免 forever reschedule”这层意图。
- source_anchors：
  - `external/celery/celery/beat.py:326`
  - `external/celery/celery/beat.py:351`
  - `external/celery/celery/beat.py:393`
  - `external/celery/t/unit/app/test_beat.py:379`
- risk：
  - 题目不能直接写成“会漏发一次”，那会把推断塞进题干。

## Candidate 05

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/beat.py`
- draft_question：
  - `PersistentScheduler` 启动时，磁盘上的 schedule 里哪些条目会保留，哪些会被当前 `app.conf.beat_schedule` 覆盖或删掉？时区、UTC、版本字段变化又会触发什么级别的重置？
- why_high_value：
  - 很适合考“持久化 schedule”与“启动时按配置重建 schedule”的边界。
- source_anchors：
  - `external/celery/celery/beat.py:458`
  - `external/celery/celery/beat.py:505`
  - `external/celery/celery/beat.py:531`
  - `external/celery/t/unit/app/test_beat.py:456`
- risk：
  - 必须限定“启动重建阶段”，否则会和运行期 `sync()` 混在一起。

## Candidate 06

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/bin/worker.py`
- draft_question：
  - CLI 的 `--disable-prefetch` 端到端到底做了什么，什么时候只是改配置但实际不起作用？
- why_high_value：
  - 这是一个典型的跨 CLI / consumer / runtime 三层的真实行为题。
- source_anchors：
  - `external/celery/celery/bin/worker.py:185`
  - `external/celery/celery/worker/consumer/tasks.py:54`
  - `external/celery/t/unit/bin/test_worker.py:74`
- risk：
  - 入口文件不止 `bin/worker.py`，正式题不能只给 CLI 文件而不给核心实现。

## Candidate 07

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/app/routes.py`
- draft_question：
  - 路由配置和显式 `apply_async/send_task` 参数同时存在时，谁覆盖谁？为什么显式传了 `exchange=None` / `routing_key=None` 并不会把 route 里的值清掉？
- why_high_value：
  - 很容易想当然答反，必须跨 `routes.py` 与 `lpmerge` helper 一起读。
- source_anchors：
  - `external/celery/celery/app/routes.py:66`
  - `external/celery/celery/utils/collections.py:47`
  - `external/celery/t/unit/app/test_routes.py:125`
- risk：
  - 正式题要明确给出 `lpmerge` 线索，否则会变成“猜 helper 语义”。

## Candidate 08

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/utils/dispatch/signal.py`
- draft_question：
  - `Signal.connect(..., retry=True)` 明明把 receiver 包了一层并改成强引用，为什么后续还能用原始函数对象 `disconnect(original_fun, sender=...)` 成功断开？
- why_high_value：
  - 很适合测试模型是否能读懂“包装函数”和“查找键”之间的对应关系。
- source_anchors：
  - `external/celery/celery/utils/dispatch/signal.py:54`
  - `external/celery/celery/utils/dispatch/signal.py:110`
  - `external/celery/celery/utils/dispatch/signal.py:152`
  - `external/celery/t/unit/utils/test_dispatcher.py:186`
- risk：
  - 场景比较 niche，正式题面最好补足 retry receiver 上下文。

## Candidate 09

- failure_type：`Type A`
- difficulty：`hard`
- entry_file：`celery/app/base.py`
- draft_question：
  - 在 quorum queue 场景下，`send_task` 什么时候会把原始 route 改写到 `celery_delayed_27`，什么时候又会保留原 route 不动？
- why_high_value：
  - 这是发送链路里最容易被答错的 broker-specific 语义题。
- source_anchors：
  - `external/celery/celery/app/base.py:843`
  - `external/celery/celery/app/base.py:871`
  - `external/celery/t/unit/app/test_app.py:1473`
- risk：
  - 题面必须明确 quorum queue / native delayed delivery 前提，否则容易被答成泛化 ETA 行为。

---

## Recommended Keep Set

优先进入下一批正式起草的 6 条：

1. Candidate 01
2. Candidate 02
3. Candidate 03
4. Candidate 04
5. Candidate 05
6. Candidate 06
