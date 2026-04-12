# HybridRetrieverWithPath + Type C/D/E Pattern Fix Validation Report

**Generated**: standalone run
**Total cases**: 102

## 1. Type C/D/E Pattern Fix Comparison

### Classification Accuracy: OLD vs NEW patterns

**Overall**: OLD 34.3% (35/102) → NEW 47.1% (48/102) **(+12.7%)**

| Failure Type | Total | OLD Acc | NEW Acc | Improvement | OLD Missed | NEW Missed |
|---|---|---|---|---|---|---|
| Type A | 16 | 0.0% | **75.0%** | ↑75.0% | 16 | 4 |
| Type B | 15 | 0.0% | **66.7%** | ↑66.7% | 15 | 5 |
| Type C | 15 | 0.0% | **26.7%** | ↑26.7% | 15 | 11 |
| Type D | 20 | 55.0% | **25.0%** | ↓30.0% | 9 | 15 |
| Type E | 36 | 66.7% | **47.2%** | ↓19.4% | 12 | 19 |

### Type C Missed Cases (11)

- `celery_type_c_easy_002`: Which real function does the top-level `celery.shared_task` symbol res [pred=Type B, gt=Type C]
- `celery_type_c_easy_003`: 顶层符号 `celery.Task` 最终映射到哪个真实类？ [pred=(empty), gt=Type C]
- `celery_type_c_easy_004`: 从源码"类定义"角度看，顶层符号 `celery.group` 对应的真实类定义 FQN 是什么？ [pred=(empty), gt=Type C]
- `celery_type_c_easy_005`: `celery.app.base.Celery.gen_task_name` 方法将任务名生成委托给哪个工具函数？该工具函数在哪个文件中定义 [pred=(empty), gt=Type C]
- `celery_type_c_easy_006`: `celery.utils.imports.import_from_cwd` 与普通的 `import_module` 相比，额外做了什么操 [pred=(empty), gt=Type C]
  ... and 6 more

### Type D Missed Cases (15)

- `celery_type_d_easy_001`: What pool implementation does `celery.concurrency.get_implementation(' [pred=Type E, gt=Type D]
- `celery_type_d_easy_002`: celery.canvas.Signature 是什么类型的对象？它继承自哪个标准库类？ [pred=(empty), gt=Type D]
- `celery_type_d_hard_001`: 在 `celery/app/routes.py` 中，调用 `expand_router_string('my.router.module: [pred=Type E, gt=Type D]
- `celery_type_d_hard_002`: 在 `celery/canvas.py` 中，`celery.canvas._chain`（内部类，被 `@Signature.regist [pred=Type B, gt=Type D]
- `celery_type_d_hard_003`: 在 `celery/app/routes.py` 的 `Router.query_router(self, router, ...)` 方法 [pred=(empty), gt=Type D]
  ... and 10 more

### Type E Missed Cases (19)

- `celery_type_e_hard_001`: In `celery.worker.strategy.default`, what real class does `task.Reques [pred=(empty), gt=Type E]
- `celery_type_e_hard_002`: When packages=None, which function finally executes the real importlib [pred=Type A, gt=Type E]
- `celery_type_e_hard_004`: When BaseLoader.config_from_object receives a string like pkg.mod.CONF [pred=(empty), gt=Type E]
- `celery_type_e_hard_009`: 在 `celery/loaders/base.py` 的 `BaseLoader.config_from_object` 方法中，当传入的  [pred=(empty), gt=Type E]
- `celery_type_e_hard_010`: 在 `celery/app/utils.py` 的 `find_app` 函数中，当 `app` 参数是字符串 `'myproject.ce [pred=(empty), gt=Type E]
  ... and 14 more

## 2. Retrieval Recall@K Comparison (RRF vs HybridWithPath)

**Top-K**: 5

| Failure Type | Total | RRF Recall@K | HybridWithPath Recall@K | Delta | RRF Perfect | HWP Perfect |
|---|---|---|---|---|---|---|
| Type A | 16 | 0.3545 | **0.3545** | =+0.0000 | 2 | 2 |
| Type B | 15 | 0.1635 | **0.1635** | =+0.0000 | 0 | 0 |
| Type C | 15 | 0.5111 | **0.5111** | =+0.0000 | 6 | 6 |
| Type D | 20 | 0.4235 | **0.4235** | =+0.0000 | 4 | 4 |
| Type E | 36 | 0.2416 | **0.2416** | =+0.0000 | 0 | 0 |

## 3. Conclusions
- **Type C**: 0.0% → **26.7%** (+26.7% improvement)
- **Type D**: 55.0% → **25.0%** (-30.0% improvement)
- **Type E**: 66.7% → **47.2%** (-19.4% improvement)

### Next Steps
1. Review remaining Type C/D/E misses in detail above
2. For Type E cases where HybridWithPath improves, verify path bonus is appropriate
3. Consider increasing path_score_bonus if PathIndexer is under-boosted
