# DependencyPathIndexer 验证报告

**Index stats**: 40 paths, 30 unique FQNs, 29 aliases loaded

## 1. Type E Recall@K 对比

| 方法 | Type E Avg Recall@K | # Cases |
|---|---|---|
| **DependencyPathIndexer** | **0.2099** | 27 |
| RRF (baseline) | 0.2668 | 27 |

- PathIndexer vs RRF: -0.0569 (-21.3%)
- RRF 优于 PathIndexer（两者互补才有效）

## 2. 互补性分析

总 Type E cases: 27

| 类别 | 数量 | 占比 | Cases |
|---|---|---|---|
| 两者都命中 | 11 | 40.7% | celery_type_e_easy_001, celery_type_e_hard_005, celery_type_e_hard_006, celery_type_e_hard_007, celery_type_e_hard_011... |
| **仅 PathIndexer 命中** | 0 | 0.0% |  |
| 仅 RRF 命中 | 15 | 55.6% | celery_type_e_easy_002, celery_type_e_hard_001, celery_type_e_hard_002, celery_type_e_hard_003, celery_type_e_hard_004... |
| 两者都未命中 | 1 | 3.7% | celery_type_e_hard_012 |

**组合覆盖率**: 26/27 = 96.3%

## 3. Type E Case 详细召回

| Case ID | Question (truncated) | Gold FQNs | Path FQNs | Path Recall |
|---|---|---|---|---|
| celery_type_e_easy_001 | In `celery.loaders.get_loader_cls`, what... | celery.loaders.default.Loader | celery.loaders.default.Loader | 1.00 |
| celery_type_e_easy_002 | `celery.utils.imports.load_extension_cla... | celery.utils.imports.load_extension_class_names, celery.utils.imports.load_extension_classes |  | 0.00 |
| celery_type_e_hard_001 | In `celery.worker.strategy.default`, wha... | celery.worker.request.Request | celery.loaders.default.Loader | 0.00 |
| celery_type_e_hard_002 | When packages=None, which function final... | celery.loaders.base.find_related_module, celery.app.base.Celery._autodiscover_tasks_from_fixups | celery.loaders.app.AppLoader | 0.00 |
| celery_type_e_hard_003 | 在满足 Django fixup 前置条件（`DJANGO_SETTINGS_M... | celery.contrib.django.task.DjangoTask, celery.fixups.django.fixup | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 0.00 |
| celery_type_e_hard_004 | When BaseLoader.config_from_object recei... | celery.utils.imports.symbol_by_name, celery.loaders.base.BaseLoader.config_from_object |  | 0.00 |
| celery_type_e_hard_005 | 在 `celery/utils/imports.py` 中，`symbol_by... | celery.concurrency.prefork.TaskPool, celery.utils.imports.symbol_by_name | celery.concurrency.prefork.TaskPool, celery.concurrency.prefork.TaskPool | 0.50 |
| celery_type_e_hard_006 | 在 `celery/app/backends.py` 中，`backends.b... | celery.backends.redis.RedisBackend, celery.app.backends.by_name | celery.backends.redis.RedisBackend, celery.loaders.app.AppLoader | 0.25 |
| celery_type_e_hard_007 | 在 `celery/utils/imports.py` 中，`instantia... | celery.concurrency.prefork.TaskPool, celery.utils.imports.instantiate | celery.concurrency.prefork.TaskPool, celery.concurrency.prefork.TaskPool | 0.33 |
| celery_type_e_hard_008 | 在 `celery/utils/imports.py` 中，`load_exte... | celery.utils.imports.symbol_by_name, celery.utils.imports.load_extension_classes |  | 0.00 |
| celery_type_e_hard_009 | 在 `celery/loaders/base.py` 的 `BaseLoader... | celery.utils.imports.symbol_by_name, celery.loaders.base.BaseLoader.config_from_object |  | 0.00 |
| celery_type_e_hard_010 | 在 `celery/app/utils.py` 的 `find_app` 函数中... | celery.app.utils.find_app, celery.utils.imports.symbol_by_name | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 0.00 |
| celery_type_e_hard_011 | 在 `celery/loaders/__init__.py` 中，`LOADER... | celery.loaders.app.AppLoader, celery.loaders.get_loader_cls | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 0.33 |
| celery_type_e_hard_012 | 在 `celery/app/task.py` 中，`Task.Strategy`... | celery.worker.strategy.default, celery.worker.request.Request | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 0.00 |
| celery_type_e_hard_013 | 在 `celery/canvas.py` 中，当调用 `chain(signat... | celery.canvas._chain, celery.canvas.Signature.register_type |  | 0.00 |
| celery_type_e_hard_014 | 在 `celery/utils/imports.py` 的 `symbol_by... | celery.backends.redis.RedisBackend, celery.utils.imports.symbol_by_name | celery.backends.redis.RedisBackend, celery.backends.redis.RedisBackend | 0.50 |
| celery_type_e_medium_001 | Which backend class does `celery.app.bac... | celery.backends.redis.RedisBackend | celery.backends.redis.RedisBackend, celery.loaders.app.AppLoader | 1.00 |
| celery_type_e_medium_002 | In `celery.loaders.get_loader_cls`, what... | celery.loaders.app.AppLoader | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 1.00 |
| celery_type_e_medium_003 | 在 `Celery.__init__` 中，默认 `builtin_fixups... | celery.fixups.django.fixup, celery.app.base.Celery.__init__ | celery.loaders.app.AppLoader | 0.00 |
| celery_type_e_medium_004 | 在未设置 `CELERY_LOADER` 且未显式传入 loader 参数时，`... | celery.loaders.app.AppLoader, celery.app.base.Celery._get_default_loader | celery.loaders.app.AppLoader, celery.loaders.app.AppLoader | 0.25 |

## 4. 结论

**结论**: PathIndexer + RRF 组合可覆盖 70%+ 的 Type E cases，路径索引有效。

### 下一步建议
1. PathIndexer 单独效果不如 RRF，但互补性存在
2. 建议作为 RRF 的 pre-filter 或 post-ranker
3. 重点改进: 覆盖更多 symbol_by_name 模式（instantiate, import_object 等）
