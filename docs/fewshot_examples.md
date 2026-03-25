# Few-shot Examples Pool

## 文档目标

本文件给出 20 条高质量 few-shot 示例的候选清单，按失效类型配比，用于 Prompt Engineering 优化。

## 配比原则

- 按失效类型配比，不允许偏向 Easy
- 优先覆盖从 Day 2 bad case 中识别的高频失效模式
- 每条示例必须包含完整的推理过程

## 按失效类型配比

| 覆盖类型 | 数量 | 重点内容 |
|---------|------|---------|
| Type B 装饰器 | 5 条 | `@app.task`、`@shared_task`、`connect_on_app_finalize` |
| Type C 再导出 | 5 条 | `__init__.py` 多层转发、别名 |
| Type D 命名空间 | 4 条 | 同名函数、局部覆盖 |
| Type E 动态加载 | 4 条 | `symbol_by_name`、`importlib.import_module`、配置字符串 |
| Type A 长上下文 | 2 条 | 超长链路的截断补偿策略 |

---

## Type B 装饰器（5 条）

### Few-shot B01: @shared_task 装饰器注册

**问题**: 给定 `@shared_task` 装饰后的函数，最终注册到哪个任务对象路径？

**推理过程**:
1. Step 1: 定位 `shared_task` 在 `celery/app/__init__.py`
2. Step 2: 发现 `shared_task` 返回一个 `_create_shared_task` 调用
3. Step 3: 追踪 `_create_shared_task`，它使用 `connect_on_app_finalize` 延迟注册
4. Step 4: 在 app finalized 时，调用 `Celery._task_from_fun` 完成注册

**答案**:
```json
{
  "direct_deps": ["celery.app.base.Celery._task_from_fun"],
  "indirect_deps": ["celery.app.task.create_task_cls"],
  "implicit_deps": ["celery.app.builtins.add_backend_cleanup_task"]
}
```

### Few-shot B02-B05: （待补充）

---

## Type C 再导出（5 条）

### Few-shot C01: celery.Celery 再导出

**问题**: `celery.Celery` 最终映射到哪个真实类？

**推理过程**:
1. Step 1: 定位 `celery/__init__.py`
2. Step 2: 发现 `Celery` 通过 `recreate_module` 懒加载
3. Step 3: 追踪到 `celery.app.Celery`
4. Step 4: 最终实现在 `celery.app.base.Celery`

**答案**:
```json
{
  "direct_deps": ["celery.app.base.Celery"],
  "indirect_deps": [],
  "implicit_deps": []
}
```

### Few-shot C02-C05: （待补充）

---

## Type D 命名空间（4 条）

### Few-shot D01-D04: （待从 bad case 中补充）

---

## Type E 动态加载（4 条）

### Few-shot E01: symbol_by_name 动态解析

**问题**: `symbol_by_name('celery.app.trace.build_tracer')` 最终返回什么？

**推理过程**:
1. Step 1: 定位 `symbol_by_name` 在 `celery/utils/imports.py`
2. Step 2: 发现它使用 `importlib.import_module` 动态加载模块
3. Step 3: 然后使用 `getattr` 获取符号
4. Step 4: 最终返回 `celery.app.trace.build_tracer` 函数

**答案**:
```json
{
  "direct_deps": ["celery.app.trace.build_tracer"],
  "indirect_deps": [],
  "implicit_deps": []
}
```

### Few-shot E02-E04: （待补充）

---

## Type A 长上下文（2 条）

### Few-shot A01-A02: （待从 bad case 中补充）

---

## 使用说明

1. 这些 few-shot 示例应该写入 `pe/prompt_templates_v2.py`
2. 每条示例必须包含完整的推理过程（CoT 风格）
3. 优先从 Day 2 的 bad case 中提取真实案例
4. 保持 20 条的配比，不要偏向 Easy 样本

## 后续工作

- [ ] 从 bad case 中补充完整的 20 条示例
- [ ] 每条示例验证在 Celery 源码中可复现
- [ ] 写入 `pe/prompt_templates_v2.py`
- [ ] 创建 `data/fewshot_examples_20.json` 文件
