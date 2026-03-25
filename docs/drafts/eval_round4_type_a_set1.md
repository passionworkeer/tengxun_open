# Eval Round 4 Type A Set 1 (EVAL-021)

> 已按 `docs/dataset_schema.md` 使用新 schema 字段。  
> 已按 `docs/drafts/review_round15_formal_pool_safety.md` gate 收紧为“单问单判 + 可用 FQN 稳定表达”。

## 总表（Candidate 01-03）

| id | difficulty | category | failure_type | implicit_level | source_file | question 摘要 |
|---|---|---|---|---:|---|---|
| celery_hard_021 | hard | worker_acks_late_failure_branch | Type A | 5 | celery/worker/request.py | `acks_late + WorkerLostError + reject_on_worker_lost` 分支最终由谁执行 reject/requeue |
| celery_hard_022 | hard | autodiscovery_import_error_gate | Type A | 5 | celery/app/base.py | `autodiscover_tasks(force=False)` 延迟链中，谁判定 `ModuleNotFoundError` 是吞掉还是重抛 |
| celery_hard_023 | hard | bootstep_include_gate | Type A | 4 | celery/bootsteps.py | `include_if=False` 时，谁决定不把 step 挂进 `parent.steps` |

## 逐条 JSON 草案

### celery_hard_021

```json
{
  "id": "celery_hard_021",
  "difficulty": "hard",
  "category": "worker_acks_late_failure_branch",
  "failure_type": "Type A",
  "implicit_level": 5,
  "question": "在 `celery.worker.request.Request.on_failure` 中，若 `task.acks_late=True` 且异常为 `WorkerLostError`，并且 `task.reject_on_worker_lost=True`，最终负责执行“拒收并 requeue”的方法是哪个？",
  "source_file": "celery/worker/request.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.worker.request.Request.reject"
    ],
    "indirect_deps": [
      "celery.worker.request.Request.on_failure"
    ],
    "implicit_deps": [
      "celery.worker.request.WorkerLostError"
    ]
  },
  "reasoning_hint": "`on_failure` 在 `acks_late` 分支下先判断 `is_worker_lost` 与 `reject_on_worker_lost`，命中后走 `self.reject(requeue=True)`；本题只判定最终 reject 执行入口，不扩展到 `mark_as_failure` 等副作用矩阵。",
  "source_note": "See celery/worker/request.py:579-632, 672-676; test anchor: t/unit/worker/test_request.py:865-880."
}
```

### celery_hard_022

```json
{
  "id": "celery_hard_022",
  "difficulty": "hard",
  "category": "autodiscovery_import_error_gate",
  "failure_type": "Type A",
  "implicit_level": 5,
  "question": "在 `app.autodiscover_tasks(packages, force=False)` 的延迟执行链里，真正执行扫描后，负责判定 `ModuleNotFoundError` 是“候选 tasks 模块缺失可忽略”还是“嵌套导入错误需重抛”的函数是哪个？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.loaders.base.find_related_module"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.autodiscover_tasks",
      "celery.loaders.base.BaseLoader.import_default_modules",
      "celery.loaders.base.autodiscover_tasks"
    ],
    "implicit_deps": [
      "celery.signals.import_modules",
      "vine.starpromise"
    ]
  },
  "reasoning_hint": "`force=False` 只在 `signals.import_modules` 上注册 `starpromise`；后续触发扫描后，真正做 `ModuleNotFoundError` 名称比对（`module_name == e.name`）并决定吞/抛的是 `find_related_module`。",
  "source_note": "See celery/app/base.py:779-824; celery/loaders/base.py:97-105, 239-278; tests: t/unit/app/test_loaders.py:267-305."
}
```

### celery_hard_023

```json
{
  "id": "celery_hard_023",
  "difficulty": "hard",
  "category": "bootstep_include_gate",
  "failure_type": "Type A",
  "implicit_level": 4,
  "question": "在 `Blueprint.apply` 过程中，当某个 `StartStopStep.include_if()` 返回 `False` 时，最终由哪个方法决定不把该 step 挂载到 `parent.steps`？",
  "source_file": "celery/bootsteps.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.bootsteps.StartStopStep.include"
    ],
    "indirect_deps": [
      "celery.bootsteps.Step._should_include",
      "celery.bootsteps.Step.include_if"
    ],
    "implicit_deps": [
      "celery.bootsteps.Blueprint.apply"
    ]
  },
  "reasoning_hint": "`Blueprint.apply` 会先实例化 step，再调用 `step.include(parent)`；`StartStopStep.include` 通过 `_should_include` 消费 `include_if` 结果，只有为真时才 `parent.steps.append(self)`。",
  "source_note": "See celery/bootsteps.py:186-205, 322-339, 378-383; tests: t/unit/worker/test_bootsteps.py:93-103, 172-180, 197-201."
}
```

