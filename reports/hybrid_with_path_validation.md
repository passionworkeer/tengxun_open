# HybridRetrieverWithPath + Type C/D/E Pattern Fix Validation Report

**Generated**: standalone run
**Total cases**: 102

## 1. Type C/D/E Pattern Fix Comparison

### Classification Accuracy: OLD vs NEW patterns

**Overall**: OLD 34.3% (35/102) → NEW 84.3% (86/102) **(+50.0%)**

| Failure Type | Total | OLD Acc | NEW Acc | Improvement | OLD Missed | NEW Missed |
|---|---|---|---|---|---|---|
| Type A | 16 | 0.0% | **75.0%** | ↑75.0% | 16 | 4 |
| Type B | 15 | 0.0% | **73.3%** | ↑73.3% | 15 | 4 |
| Type C | 15 | 0.0% | **80.0%** | ↑80.0% | 15 | 3 |
| Type D | 20 | 55.0% | **95.0%** | ↑40.0% | 9 | 1 |
| Type E | 36 | 66.7% | **88.9%** | ↑22.2% | 12 | 4 |

### Type C Missed Cases (3)

- `celery_type_c_medium_002`: 在 `celery/utils/collections.py` 中，`lpmerge(L, R)` 函数的合并策略是什么？当 R 字典中某个 [pred=(empty), gt=Type C]
- `celery_type_c_medium_003`: 在 `celery/utils/collections.py` 中，`lpmerge(L, R)` 的合并策略是什么？当 R 中某个键对应的 [pred=(empty), gt=Type C]
- `celery_type_c_hard_003`: 在 `celery/canvas.py` 中，`celery.canvas._chain`（内部类，被 `@Signature.regist [pred=Type D, gt=Type C]

### Type D Missed Cases (1)

- `celery_type_d_medium_006`: celery.app.task.Task.Request 是字符串 celery.worker.request:Request，celery [pred=Type E, gt=Type D]

### Type E Missed Cases (4)

- `celery_type_e_hard_002`: When packages=None, which function finally executes the real importlib [pred=Type A, gt=Type E]
- `celery_type_e_hard_013`: 在 `celery/canvas.py` 中，当调用 `chain(signature_dicts)` 时，`chain` 构造函数内部如何 [pred=Type D, gt=Type E]
- `celery_type_e_medium_011`: 在 `celery/utils/collections.py` 中，`ConfigurationView.__getitem__` 在查遍所 [pred=Type D, gt=Type E]
- `celery_type_e_hard_018`: 在 `celery/concurrency/__init__.py` 中，`get_implementation('prefork')` 如 [pred=Type D, gt=Type E]

## 2. Retrieval Recall@K Comparison (RRF vs HybridWithPath)

**Top-K**: 5

| Failure Type | Total | RRF Recall@K | HybridWithPath Recall@K | Delta | RRF Perfect | HWP Perfect |
|---|---|---|---|---|---|---|
| Type A | 16 | 0.3857 | **0.3857** | =+0.0000 | 2 | 2 |
| Type B | 15 | 0.1635 | **0.1635** | =+0.0000 | 0 | 0 |
| Type C | 15 | 0.5111 | **0.5111** | =+0.0000 | 6 | 6 |
| Type D | 20 | 0.4235 | **0.4235** | =+0.0000 | 4 | 4 |
| Type E | 36 | 0.2485 | **0.3230** | ↑+0.0745 | 0 | 3 |

## 3. Conclusions
- **Type C**: 0.0% → **80.0%** (+80.0% improvement)
- **Type D**: 55.0% → **95.0%** (+40.0% improvement)
- **Type E**: 66.7% → **88.9%** (+22.2% improvement)

### Next Steps
1. Review remaining Type C/D/E misses in detail above
2. For Type E cases where HybridWithPath improves, verify path bonus is appropriate
3. Consider increasing path_score_bonus if PathIndexer is under-boosted
