# 数据质检报告

**Owner**: codex
**日期**: 2026-03-27
**Celery 版本**: `b8f85213f45c937670a6a6806ce55326a0eb537f`
**状态**: ✅ 三份正式数据已严格收敛

## 正式数据集清单

| 文件 | 条目数 | 用途 | 状态 |
|------|--------|------|------|
| `data/eval_cases.json` | **54条** | 正式评测集 | ✅ 严格通过 |
| `data/finetune_dataset_500.jsonl` | **500条** | 微调训练集 | ✅ 严格通过 |
| `data/fewshot_examples_20.json` | **20条** | Few-shot 示例 | ✅ 严格通过 |

## 微调数据集结果

- 最终有效记录：`500`
- 难度分布：`easy=163` / `medium=175` / `hard=162`
- hard_ratio：`0.324`
- 严格补充样本：`0` 条

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

## 微调集严格清洗

- seed: data/finetune_dataset_500.jsonl

## 微调集补充样本


## 已删除的过渡工件

- 无新增过渡工件需要删除。
