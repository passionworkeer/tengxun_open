# 严格数据质检报告

**日期**: 2026-03-27
**Celery 版本**: `b8f85213f45c937670a6a6806ce55326a0eb537f`

## 结果摘要

| 数据集 | 处理结果 |
|------|------|
| `data/eval_cases.json` | 保留 54 条，修正 10 处 gold / 题面口径 |
| `data/fewshot_examples_20.json` | 保留 20 条，补齐 20 条 `difficulty`，并修正 1 条示例 |
| `data/finetune_dataset_500_clean_strict.jsonl` | 从 488 条严格清到 470 条，删除 18 条，修补 12 条 |

## 正式评测集修正

- celery_hard_016: 去掉外部 helper `importlib.import_module`
- celery_hard_015: 去掉外部 helper `vine.starpromise`
- celery_hard_018: 仅保留 Celery 内部可复核链路，移除 `os.environ.get` / `django.conf.settings`
- celery_hard_019: 去掉外部 helper `importlib.import_module`
- celery_hard_121: 去掉外部 helper `vine.starpromise`
- celery_type_d_001: 修正为稳定的内部解析函数问题
- celery_type_d_006: 修正为稳定且可复核的内部目标类
- celery_type_a_003: 去掉外部 helper `vine.starpromise`
- celery_medium_019: 用内部最终目标替换外部 re-export 细节
- celery_easy_020: 改成纯内部扩展加载链问题

## Few-shot 修正

- E04: 改为内部可复核的 alias 解析结果
- fewshot: 20 条全部补齐 difficulty 字段

## 微调集删除项

- line 33: `stdlib_import` 删除。原因：清洗后无有效 direct_deps。
- line 36: `data_structure_choice` 删除。原因：清洗后无有效 direct_deps。
- line 37: `lock_per_instance` 删除。原因：清洗后无有效 direct_deps。
- line 50: `source_analysis` 删除。原因：清洗后无有效 direct_deps。
- line 52: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 53: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 61: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 63: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 69: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 70: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 71: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 72: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 73: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 88: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 89: `import_chain` 删除。原因：清洗后无有效 direct_deps。
- line 145: `importlib_usage` 删除。原因：清洗后无有效 direct_deps。
- line 200: `thread_safety` 删除。原因：清洗后无有效 direct_deps。
- line 253: `thread_local_distinction` 删除。原因：清洗后无有效 direct_deps。

## 微调集修补项

- line 48: `env_driven_loading` 修补为 `{'direct_deps': ['celery.concurrency.get_implementation'], 'indirect_deps': ['kombu.utils.imports.symbol_by_name'], 'implicit_deps': []}`。
- line 78: `import_chain` 修补为 `{'direct_deps': ['celery.utils.log.get_logger'], 'indirect_deps': [], 'implicit_deps': []}`。
- line 143: `conditional_string_resolution` 修补为 `{'direct_deps': ['celery.fixups.django.fixup', 'celery.fixups.django.DjangoFixup.install'], 'indirect_deps': ['celery.utils.imports.symbol_by_name'], 'implicit_deps': []}`。
- line 147: `import_chain_with_fallback` 修补为 `{'direct_deps': ['celery.utils.imports.find_module'], 'indirect_deps': ['celery.loaders.base.BaseLoader.find_module'], 'implicit_deps': []}`。
- line 166: `config_env_chain` 修补为 `{'direct_deps': ['celery.utils.imports.symbol_by_name'], 'indirect_deps': ['celery.app.base.Celery.config_from_object', 'celery.loaders.base.BaseLoader.config_from_object'], 'implicit_deps': []}`。
- line 173: `fork_cleanup` 修补为 `{'direct_deps': ['celery.app.base._after_fork_cleanup_app'], 'indirect_deps': ['celery._state._deregister_app'], 'implicit_deps': []}`。
- line 350: `finalize_detailed_steps` 修补为 `{'direct_deps': ['celery.app.base.Celery.finalize'], 'indirect_deps': ['celery._state._announce_app_finalized', 'celery.local.maybe_evaluate'], 'implicit_deps': []}`。
- line 426: `long_context` 修补为 `{'direct_deps': ['celery.app.registry.TaskRegistry'], 'indirect_deps': [], 'implicit_deps': []}`。
- line 434: `entry_point_loading` 修补为 `{'direct_deps': ['celery.utils.imports.load_extension_classes'], 'indirect_deps': [], 'implicit_deps': ['celery.utils.imports.symbol_by_name']}`。
- line 442: `task_name_generation` 修补为 `{'direct_deps': ['celery.utils.imports.gen_task_name'], 'indirect_deps': [], 'implicit_deps': []}`。
- line 457: `name_generation` 修补为 `{'direct_deps': ['celery.utils.imports.gen_task_name'], 'indirect_deps': [], 'implicit_deps': []}`。
- line 466: `registry_structure` 修补为 `{'direct_deps': ['celery.app.registry.TaskRegistry'], 'indirect_deps': [], 'implicit_deps': []}`。
