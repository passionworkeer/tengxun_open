# Eval Remaining Round 3

> 本文件仅处理剩余未过线条目：`celery_hard_017`、`celery_hard_020`。  
> 不改正式数据文件，只给出最终建议稿（新 schema 字段齐全）。

---

## 1) celery_hard_017

- 处理方式：**降级保留**
- 结论：不再保留 hard；降为 medium，并去掉不必要的 `DjangoFixup.install` 副作用依赖。
- ID 处理：建议废弃旧 ID `celery_hard_017`，改用新 ID **`celery_medium_017`**。

### 最终建议 JSON

```json
{
  "id": "celery_medium_017",
  "difficulty": "medium",
  "category": "fixup_string_entry_resolution",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "在 `Celery.__init__` 中，默认 `builtin_fixups` 的字符串入口 `'celery.fixups.django:fixup'` 最终会被解析到哪个真实函数符号（不考虑后续 install 副作用）？",
  "source_file": "celery/app/base.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.fixups.django.fixup"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.__init__",
      "celery.utils.imports.symbol_by_name"
    ],
    "implicit_deps": [
      "celery.app.base.BUILTIN_FIXUPS"
    ]
  },
  "reasoning_hint": "`Celery.__init__` 在构造 `_fixups` 时执行 `symbol_by_name(fixup)(self)`；这里先要把字符串入口解析成函数对象，题目只要求该解析终点，不延伸到条件执行/安装副作用。",
  "source_note": "Round3 arbitration: downgraded from hard to medium; trimmed side-effect dependency (`DjangoFixup.install`) to keep target single and review-stable."
}
```

---

## 2) celery_hard_020

- 处理方式：**降级保留**
- 结论：维持 medium 定位，但必须更换 ID，避免与 `hard_020` 命名冲突。
- ID 处理：废弃旧 ID `celery_hard_020`，改用新 ID **`celery_medium_020`**（不复用 hard 槽位）。

### 最终建议 JSON

```json
{
  "id": "celery_medium_020",
  "difficulty": "medium",
  "category": "default_app_loader_alias_chain",
  "failure_type": "Type E",
  "implicit_level": 3,
  "question": "`_state._get_current_app` 懒创建 fallback app 后，首次访问 `app.loader` 时，最终实例化到哪个具体 Loader 类？",
  "source_file": "celery/_state.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": [
      "celery.app.base.Celery.loader",
      "celery.loaders.default.Loader"
    ],
    "indirect_deps": [
      "celery._state._get_current_app",
      "celery.loaders.get_loader_cls"
    ],
    "implicit_deps": [
      "celery.utils.imports.symbol_by_name",
      "celery.utils.imports.import_from_cwd"
    ]
  },
  "reasoning_hint": "`_get_current_app` 只把 loader 设为 `'default'`；真正触发解析的是 `Celery.loader` 属性，内部通过 `get_loader_cls` 的 alias + `symbol_by_name` 解析后实例化 `celery.loaders.default.Loader`。",
  "source_note": "Round3 naming fix: migrated from `celery_hard_020` to `celery_medium_020` to remove hard-slot collision."
}
```

