# GLM-5 官方评测整理报告

## 总览

- 样本数：`54`
- 平均 Precision：`0.0691`
- 平均 Recall：`0.0895`
- 平均 F1：`0.0666`
- Pass Rate (F1>0)：`13.0%`
- Exact Match Rate (F1=1)：`1.8%`
- F1=0 数量：`47`
- 平均 reasoning 长度：`7113.4` 字符

## 原始 thinking 结束状态

| Finish Reason | Count |
|---------------|-------|
| length | 49 |
| stop | 5 |

## 难度分层

| Difficulty | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |
|------------|-------|---------------|------------|--------|------|
| easy | 15 | 0.1000 | 0.1111 | 0.1048 | 13 |
| medium | 19 | 0.0544 | 0.1009 | 0.0681 | 16 |
| hard | 20 | 0.0600 | 0.0625 | 0.0367 | 18 |

## Failure Type 分层

| Failure Type | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |
|--------------|-------|---------------|------------|--------|------|
| Type E | 16 | 0.1583 | 0.2240 | 0.1485 | 11 |
| Type C | 11 | 0.0909 | 0.0909 | 0.0909 | 10 |
| Type D | 11 | 0.0182 | 0.0227 | 0.0202 | 10 |
| Type A | 7 | 0.0000 | 0.0000 | 0.0000 | 7 |
| Type B | 9 | 0.0000 | 0.0000 | 0.0000 | 9 |

## Category 分层 Top 15

| Category | Count | Avg Precision | Avg Recall | Avg F1 | F1=0 |
|----------|-------|---------------|------------|--------|------|
| extension_class_entry_point | 1 | 0.5000 | 0.6667 | 0.5714 | 0 |
| symbol_by_name_resolution_chain | 1 | 0.5000 | 0.6667 | 0.5714 | 0 |
| loader_smart_import_fallback | 1 | 1.0000 | 0.2500 | 0.4000 | 0 |
| symbol_by_name_resolution | 1 | 0.2000 | 1.0000 | 0.3333 | 0 |
| loader_alias | 2 | 0.1666 | 0.5000 | 0.2500 | 1 |
| re_export | 4 | 0.2500 | 0.2500 | 0.2500 | 3 |
| task_string_class_reference | 1 | 0.2000 | 0.2500 | 0.2222 | 0 |
| acks_late_failure_matrix | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| alias_re_export_confusion | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| alias_resolution | 2 | 0.0000 | 0.0000 | 0.0000 | 2 |
| app_task_registration | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| autodiscover_signal_lazy_chain | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| autodiscovery_fixup_import | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| autodiscovery_import_error_gate | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |
| autodiscovery_signal_chain | 1 | 0.0000 | 0.0000 | 0.0000 | 1 |

## 表现最好的 10 个 case

| Case | Difficulty | Category | F1 | Matched / Gold |
|------|------------|----------|----|----------------|
| easy_001 | easy | re_export | 1.0000 | 1 / 1 |
| celery_easy_020 | easy | extension_class_entry_point | 0.5714 | 2 / 3 |
| celery_medium_019 | medium | symbol_by_name_resolution_chain | 0.5714 | 2 / 3 |
| medium_002 | medium | loader_alias | 0.5000 | 1 / 1 |
| celery_hard_019 | hard | loader_smart_import_fallback | 0.4000 | 1 / 4 |
| hard_004 | hard | symbol_by_name_resolution | 0.3333 | 1 / 1 |
| celery_medium_025 | medium | task_string_class_reference | 0.2222 | 1 / 4 |
| celery_easy_018 | easy | gen_task_name_cross_module | 0.0000 | 0 / 1 |
| celery_easy_019 | easy | cwd_import_scope | 0.0000 | 0 / 2 |
| celery_easy_021 | easy | signature_class_definition | 0.0000 | 0 / 1 |

## 表现最差的 10 个 case

| Case | Difficulty | Category | F1 | Missing FQNs | Extra FQNs |
|------|------------|----------|----|--------------|------------|
| celery_easy_018 | easy | gen_task_name_cross_module | 0.0000 | celery.utils.imports.gen_task_name | celery/app/base.py, celery/utils/names.py |
| celery_easy_019 | easy | cwd_import_scope | 0.0000 | celery.utils.imports.cwd_in_path, celery.utils.imports.import_from_cwd | os, os.getcwd, contextlib.contextmanager |
| celery_easy_021 | easy | signature_class_definition | 0.0000 | celery.canvas.Signature | celery.app.task.Task, dict |
| celery_easy_022 | easy | cross_package_re-export | 0.0000 | kombu.utils.uuid.uuid | - |
| celery_easy_023 | easy | nodename_function_definition | 0.0000 | celery.utils.nodenames.nodename | celery.utils.nodenames |
| celery_easy_024 | easy | worker_direct_re-export | 0.0000 | celery.utils.nodenames.worker_direct | celery.utils.nodenames |
| celery_hard_013 | hard | shared_task_proxy_autofinalize | 0.0000 | celery.app.base.Celery.tasks, celery.app.base.Celery.finalize, celery._state._announce_app_finalized | celery/app/task.py, celery/app/base.py, celery/local.py |
| celery_hard_014 | hard | builtin_finalize_registration | 0.0000 | celery.app.base.Celery._task_from_fun, celery.app.builtins.add_backend_cleanup_task, celery.app.base.Celery.task | celery/app/builtins.py, celery/app/task.py |
| celery_hard_015 | hard | autodiscovery_signal_chain | 0.0000 | celery.app.base.Celery._autodiscover_tasks, celery.loaders.base.BaseLoader.init_worker, celery.loaders.base.BaseLoader.import_default_modules | celery/app/autodiscover.py, celery/loaders/base.py, celery/utils/imports.py |
| celery_hard_016 | hard | autodiscovery_fixup_import | 0.0000 | celery.loaders.base.find_related_module, celery.app.base.Celery._autodiscover_tasks_from_fixups, celery.fixups.django.DjangoFixup.autodiscover_tasks | celery/app/trace.py, celery/loaders/base.py, celery/fixups/__init__.py |

## 与 GPT-5.4 对比

- GLM 更好：`5`
- GPT 更好：`27`
- 持平：`22`

### GLM 提升最大的 10 个 case

| Case | Difficulty | GPT F1 | GLM F1 | Delta |
|------|------------|--------|--------|-------|
| easy_001 | easy | 0.3333 | 1.0000 | +0.6667 |
| medium_002 | medium | 0.0000 | 0.5000 | +0.5000 |
| hard_004 | hard | 0.0000 | 0.3333 | +0.3333 |
| celery_easy_020 | easy | 0.2500 | 0.5714 | +0.3214 |
| celery_medium_019 | medium | 0.4444 | 0.5714 | +0.1270 |
| medium_001 | medium | 0.0000 | 0.0000 | +0.0000 |
| medium_003 | medium | 0.0000 | 0.0000 | +0.0000 |
| hard_002 | hard | 0.0000 | 0.0000 | +0.0000 |
| hard_003 | hard | 0.0000 | 0.0000 | +0.0000 |
| celery_hard_014 | hard | 0.0000 | 0.0000 | +0.0000 |

### GPT 提升最大的 10 个 case

| Case | Difficulty | GPT F1 | GLM F1 | Delta |
|------|------------|--------|--------|-------|
| easy_002 | easy | 1.0000 | 0.0000 | -1.0000 |
| medium_004 | medium | 1.0000 | 0.0000 | -1.0000 |
| celery_type_d_001 | hard | 1.0000 | 0.0000 | -1.0000 |
| celery_easy_023 | easy | 1.0000 | 0.0000 | -1.0000 |
| celery_medium_017 | medium | 0.7500 | 0.0000 | -0.7500 |
| celery_type_d_002 | hard | 0.7273 | 0.0000 | -0.7273 |
| celery_easy_018 | easy | 0.6667 | 0.0000 | -0.6667 |
| celery_hard_121 | hard | 0.6154 | 0.0000 | -0.6154 |
| easy_005 | easy | 0.5714 | 0.0000 | -0.5714 |
| celery_hard_013 | hard | 0.5556 | 0.0000 | -0.5556 |
