# Prompt Engineering Optimization

## 实验设计

**严格单变量逐步叠加**（不允许跳步）：

```
Baseline → +System Prompt → +CoT → +Few-shot → +后处理
```

每步独立记录 Easy / Medium / Hard / Avg F1，不允许跳步或合并。

## 已知基线数据（GPT-5.4）

| Variant | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token Cost | Notes |
|:--------|:-------:|:---------:|:--------:|:------:|:----------:|:------|
| **Baseline (GPT-5.4)** | **0.4475** | **0.2670** | **0.2373** | **0.3122** | 基准 | 已实测 |

## 指标表（PE 逐步叠加实验）

| Variant | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token Cost | Notes |
|:--------|:-------:|:---------:|:--------:|:------:|:----------:|:------|
| Baseline | 0.4475 | 0.2670 | 0.2373 | 0.3122 | 基准 | GPT-5.4 零样本 |
| + System Prompt | TBD | TBD | TBD | TBD | +40% | 含格式约束 |
| + CoT | TBD | TBD | TBD | TBD | +60% | 分步推理引导 |
| + Few-shot | TBD | TBD | TBD | TBD | +80% | 20 条按类型配比 |
| + Post-processing | TBD | TBD | TBD | TBD | +85% | FQN 校验净化 |

## 分难度增益分析

基于 GPT-5.4 基线 bad case 推断（待实验验证）：

| Variant | Easy 增益 | Medium 增益 | Hard 增益 | 最大提升失效类型 | 推断依据 |
|:--------|:---------:|:-----------:|:---------:|:---------------|:---------|
| + System Prompt | +0.05~0.10 | +0.02~0.05 | +0.01~0.03 | Type E 格式问题 | easy_012/013 可从 F1=0 修复（2/50 case） |
| + CoT | TBD | TBD | TBD | Type B/C | 分步推理可能减少幻觉中间层 |
| + Few-shot | TBD | TBD | TBD | Type C/D/E | 20 条样本按类型配比，针对性强 |
| + Post-processing | +0.01~0.03 | +0.01~0.03 | +0.01~0.03 | 全部 | 不修改事实，只净化格式 |

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
  7. FQN 必须使用 `.` 分隔符，禁止使用 `:`
```

> **格式约束说明**：GPT-5.4 baseline 中 easy_012/easy_013 使用了 `:` 分隔符导致 F1=0。这个约束只需在 System Prompt 加一句话即可修复，是 PE 叠加实验中 **最容易量化的单步增益**。

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

### ③ Few-shot 示例库（20 条）

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

## PE 各维度针对的失效类型

| PE 组件 | 最能解决 | 无法解决 | 原因 |
|---------|---------|---------|------|
| System Prompt | Type E 格式问题 | Type B 幻觉 | 格式约束有效，推理错误无法通过 prompt 修复 |
| CoT | Type C 再导出链 | Type E 动态解析 | 分步推理帮助追踪链路，但无法教会动态符号映射 |
| Few-shot | Type C/D/E | Type B 深层幻觉 | 示例可以演示模式，但无法教会全新推理能力 |
| Post-processing | 全部 | 0 | 只做格式净化，不涉及推理 |

## 待实验验证的核心问题

1. **哪一步提升最大**：基于 bad case 推断 System Prompt 格式约束增益最可量化（+0.02~0.04 Avg F1），但需要实验验证
2. **哪一步对 Hard 样本最有效**：Few-shot 和 CoT 应该对 Hard 有效，但数据待补
3. **是否存在收益递减**：需要逐步叠加实验才能回答
4. **最终推荐 PE 组合**：待实验数据
5. **哪些失效类型 PE 无法解决**：**Type B（隐式依赖幻觉）** 是 PE 的硬边界，RAG/FT 是唯一出路

## 结论

- **已完成**：PE 四维度设计方案、基线数据、bad case 推断
- **待执行**：PE 逐步叠加实验（System Prompt → CoT → Few-shot → Post-processing）
- **核心发现预备**：Type B（幻觉）是 PE 的硬边界，RAG/FT 才能解决
