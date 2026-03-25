# Prompt Engineering Optimization

## 实验设计

**严格单变量逐步叠加**（不允许跳步）：

```
Baseline → +System Prompt → +CoT → +Few-shot → +后处理
```

## 四维度优化策略

### ① System Prompt

```
角色：资深 Python 静态分析专家，专注跨文件依赖图分析
任务约束：
  1. 严格区分直接依赖 / 间接依赖 / 隐式依赖三级
  2. 必须追踪 __init__.py 的完整再导出链
  3. 对装饰器函数，必须递归分析装饰器本身的依赖
  4. 搜索 importlib / __import__ 等动态加载模式
  5. 输出格式：严格 JSON，含 direct_deps / indirect_deps / implicit_deps 三字段
  6. 禁止输出任何解释性文字，只输出 JSON
```

### ② CoT 推理引导模板

```
Step 1: 定位入口函数，识别其所在文件
Step 2: 枚举当前文件所有显式 import 语句
Step 3: 检查函数上的装饰器，递归分析装饰器依赖（Type B 专项）
Step 4: 搜索 __init__.py 再导出链，追踪别名（Type C 专项）
Step 5: 搜索 importlib / symbol_by_name 等动态加载（Type E 专项）
Step 6: 检查同名函数/类的命名空间，避免混淆（Type D 专项）
Step 7: 按 direct / indirect / implicit 分类汇总输出
```

### ③ Few-shot 示例库（≥ 20 条）

| 覆盖类型 | 数量 | 重点内容 |
|---------|------|---------|
| Type B 装饰器 | 5 条 | `@app.task`、`@shared_task`、`connect_on_app_finalize` |
| Type C 再导出 | 5 条 | `__init__.py` 多层转发、别名 |
| Type D 命名空间 | 4 条 | 同名函数、局部覆盖 |
| Type E 动态加载 | 4 条 | `symbol_by_name`、`importlib.import_module`、配置字符串 |
| Type A 长上下文 | 2 条 | 超长链路的截断补偿策略 |

### ④ 输出后处理规则

- JSON 解析 + FQN 格式校验（正则：`^[a-zA-Z_][a-zA-Z0-9_.]*$`）
- 去重（同一 FQN 多次出现）
- 非法路径过滤（`jedi` 验证路径在源码中可连通）
- **严禁修改事实内容，只做格式净化**

## 指标表

| Variant | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token Cost | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Baseline | TBD | TBD | TBD | TBD | 基准 | |
| + System Prompt | TBD | TBD | TBD | TBD | +40% | |
| + CoT | TBD | TBD | TBD | TBD | +60% | |
| + Few-shot | TBD | TBD | TBD | TBD | +80% | |
| + Post-processing | TBD | TBD | TBD | TBD | +85% | |

## 分难度增益分析

| Variant | Easy 增益 | Medium 增益 | Hard 增益 | 最大提升失效类型 |
| :--- | :--- | :--- | :--- | :--- |
| + System Prompt | TBD | TBD | TBD | |
| + CoT | TBD | TBD | TBD | |
| + Few-shot | TBD | TBD | TBD | |
| + Post-processing | TBD | TBD | TBD | |

## 结论

- 哪一步提升最大：
- 哪一步对 Hard 样本最有效：
- 是否存在收益递减：
- 最终推荐 PE 组合：
- 哪些失效类型 PE 无法解决（需 RAG/FT）：
