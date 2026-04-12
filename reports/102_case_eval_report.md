# 102-case 检索基准评测报告

**生成时间**: 2026-04-12 22:55:04
**检索器**: hybrid_with_path
**Top-K**: 5
**数据集**: `data/eval_cases.json` (120 cases)
**Celery repo**: E:\desktop\tengxun\tengxun_open\external\celery

## 口径一致性说明

本评测采用 **retrieval-only** 口径:
- 预测层: 所有检索到的 FQN 归入 `direct_deps`
  (检索系统无法区分 direct/indirect/implicit)
- 评测对象: HybridRetrieverWithPath 检索质量，而非 LLM 理解质量
- 对比基准: 旧 54-case 使用同样口径，结果可直接对比

与旧 54-case 结果对比说明:
- 旧评测: 54 cases (无 failure_type 标注)
- 新评测: 102 cases (含 Type A/B/C/D/E)
- 口径: 完全一致 (retrieval-only, FQN 归 direct)

## 总体结果

| 指标 | 值 |
|---|---|
| Cases | 120 |
| **Avg Union F1** | **0.2098** |
| Avg Macro F1 | 0.0905 |
| Avg Direct F1 | 0.1690 |
| Avg Recall@3 | 0.2626 |
| **Avg Recall@5** | **0.3212** |
| Avg Recall@10 | 0.4171 |
| Avg Precision | 0.1800 |
| Perfect (F1=1.0) | 0 |
| Zero (F1=0.0) | 38 |

## 按 Difficulty 分类

| Difficulty | Count | Union F1 | Macro F1 | Recall@3 | Recall@5 | Recall@10 | Perfect | Zero |
|---|---|---|---|---|---|---|---|---|
| Easy | 15 | **0.1959** | 0.1603 | 0.4578 | 0.4578 | 0.6578 | 0 | 6 |
| Medium | 23 | **0.2825** | 0.1725 | 0.3649 | 0.5424 | 0.6077 | 0 | 3 |
| Hard | 82 | **0.1919** | 0.0547 | 0.1982 | 0.2341 | 0.3196 | 0 | 29 |

## 按 Failure Type 分类

| Failure Type | Count | Union F1 | Macro F1 | Recall@5 | Perfect | Zero |
|---|---|---|---|---|---|---|
| Type A | 19 | **0.2737** | 0.0843 | 0.3371 | 0 | 3 |
| Type B | 19 | **0.1259** | 0.0313 | 0.1492 | 0 | 9 |
| Type C | 18 | **0.1817** | 0.1486 | 0.4370 | 0 | 8 |
| Type D | 24 | **0.2487** | 0.1018 | 0.3841 | 0 | 6 |
| Type E | 40 | **0.2085** | 0.0885 | 0.3053 | 0 | 12 |

## Top 10 最佳 Cases

| Case ID | Difficulty | Type | Gold | Predicted | F1 |
|---|---|---|---|---|---|
| celery_type_d_medium_005 | medium | Type D | celery.canvas.Signature.TYPES, celery.canvas.Signature.from_dict | celery.canvas.Signature.from_dict, celery.canvas.Signature.register_type | **0.7273** |
| celery_type_d_hard_005 | hard | Type D | celery.canvas._chain, celery.canvas.Signature.TYPES | celery.canvas._chain, celery.canvas.Signature.from_dict | **0.6667** |
| celery_type_a_hard_006 | hard | Type A | celery.worker.request.Request.on_failure, celery.worker.request.Request.on_timeout | celery.worker.request.Request.on_failure, t.unit.worker.test_request.test_Request | **0.6000** |
| celery_type_d_hard_007 | hard | Type D | celery.canvas._chord, celery.canvas.Signature.TYPES | celery.canvas._chord, celery.canvas.Signature.from_dict | **0.6000** |
| celery_type_a_hard_003 | hard | Type A | celery.beat.PersistentScheduler._create_schedule, celery.beat.PersistentScheduler.setup_schedule | celery.beat.PersistentScheduler._create_schedule, celery.beat.PersistentScheduler.setup_schedule | **0.5714** |
| celery_type_a_hard_015 | hard | Type A | celery.loaders.base.find_related_module, celery.app.base.Celery.autodiscover_tasks | celery.app.base.Celery._autodiscover_tasks_from_fixups, celery.app.base.Celery | **0.5455** |
| celery_type_e_easy_002 | easy | Type E | celery.utils.imports.load_extension_class_names, celery.utils.imports.load_extension_classes | celery.utils.imports.load_extension_classes, celery.utils.imports.load_extension_class_names | **0.5000** |
| celery_type_e_hard_007 | hard | Type E | celery.concurrency.prefork.TaskPool, celery.utils.imports.instantiate | celery.concurrency.prefork, celery.concurrency.prefork.TaskPool | **0.5000** |
| celery_type_e_hard_008 | hard | Type E | celery.utils.imports.symbol_by_name, celery.utils.imports.load_extension_classes | celery.utils.imports.NotAPackage, celery.utils.imports.load_extension_classes | **0.5000** |
| celery_type_e_medium_009 | medium | Type E | celery.concurrency.prefork.TaskPool, celery.utils.imports.instantiate | celery.concurrency.prefork, celery.concurrency.prefork.TaskPool | **0.5000** |

## Bottom 10 最差 Cases (F1=0.0)

| Case ID | Difficulty | Type | Gold |
|---|---|---|---|
| celery_type_a_hard_002 | hard | Type A | celery.bootsteps.Blueprint.apply, celery.worker.worker.WorkController.__init__ |
| celery_type_a_hard_007 | hard | Type A | celery.signals.import_modules, celery.app.base.Celery._autodiscover_tasks |
| celery_type_b_easy_002 | easy | Type B | celery._state.get_current_task, celery._state._task_stack.top |
| celery_type_b_hard_001 | hard | Type B | celery.app.base.Celery._task_from_fun |
| celery_type_b_hard_002 | hard | Type B | celery.app.base.Celery._task_from_fun |
| celery_type_b_hard_003 | hard | Type B | celery._state._announce_app_finalized |
| celery_type_b_hard_006 | hard | Type B | celery.app.base.Celery._autodiscover_tasks, celery.loaders.base.BaseLoader.init_worker |
| celery_type_b_hard_008 | hard | Type B | celery.app.base.Celery._task_from_fun, celery.app.base.Celery.task |
| celery_type_c_easy_002 | easy | Type C | celery.app.shared_task |
| celery_type_c_easy_005 | easy | Type C | celery.utils.imports.gen_task_name |

... 还有 28 个 F1=0.0 case

## 关键发现
- Hard 场景 F1: 0.1919 (Easy: 0.1959)
- Hard 场景零命中: 29 cases
- Type E Recall@K 提升: +0.0218 (HWP vs RRF)
- Type E Avg F1: 0.2085

## 下一步建议
1. Hard 场景检索严重不足，需要更多训练数据覆盖
2. PathIndexer 覆盖率有限，需扩展到 symbol_by_name 更多变体
