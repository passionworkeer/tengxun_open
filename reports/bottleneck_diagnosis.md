# Bottleneck Diagnosis

## 目标

- 基于真实 Celery 评测集分析 baseline 低分原因
- 用错误样本而不是主观描述来定义失效模式
- 绘制 5 类失效在 Easy/Medium/Hard 上的**分布热力图**

## 模型配置

| 角色 | 模型 | 用途 |
|------|------|------|
| 评测基线 A | `GPT-5.4`（API） | 国际顶尖商业模型，作为上界参照 |
| 评测基线 B | `GLM-5`（API） | 开源代码最强模型，国产自研 |
| 评测基线 C | `Qwen3.5-9B`（未微调） | 微调前的对照基座 |

## 评测集概况

| 属性 | 值 |
|------|------|
| 总样本数 | 50 条 |
| Easy / Medium / Hard | 15 / 20 / 15 |
| 评测模型 | GPT-5.4（API: ai.td.ee/v1） |
| Celery 版本 | `b8f85213f45c937670a6a6806ce55326a0eb537f` |

## 分层指标表

| Model | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GPT-5.4** | **0.4475** | **0.2670** | **0.2373** | **0.3122** | 已实测 |
| GLM-5 | TBD | TBD | TBD | TBD | 未评测 |
| Qwen3.5-9B | TBD | TBD | TBD | TBD | 未评测 |

> **关键发现**：GPT-5.4 在 Easy 上 F1=0.4475，但在 Hard 上仅 0.2373，跌幅达 47%。这说明当前模型的共性天花板不是规模问题，而是对 Hard 场景（隐式依赖、动态加载）的处理能力。

---

## 失效模式定义

### Type A: 长上下文截断丢失

- **现象**: 超出窗口导致上游定义节点被遗漏
- **典型案例**: `celery/app/base.py` 超长文件、跨多层 bootstep 初始化链
- **对最终输出的影响**: 遗漏关键跳转节点，召回率下降

### Type B: 隐式依赖断裂（幻觉）

- **现象**: `@app.task` 装饰器注册时 LLM 编造不存在的内部调用，或返回过多中间层而非最终目标
- **典型案例**: `celery/app/__init__.py`、`celery/app/builtins.py`
- **对最终输出的影响**: 精确率下降，幻觉内容进入 direct_deps

### Type C: 再导出链断裂

- **现象**: 跨多层 `__init__.py` 别名转发，链路在中间节点中断；混淆懒加载 Proxy 与真实函数
- **典型案例**: `celery/__init__.py`、`celery/app/__init__.py`
- **对最终输出的影响**: 停在中间跳板而非最终符号

### Type D: 跨文件命名空间混淆

- **现象**: 同名函数/类导致 LLM 张冠李戴
- **典型案例**: `celery.canvas.subtask` 和 `celery.canvas.signature` 是同一对象，模型混淆
- **对最终输出的影响**: 指向错误模块的实现

### Type E: 动态加载与字符串引用失配

- **现象**: `importlib`/配置字符串，LLM 无法把字符串入口映射回真实符号
- **典型案例**: `loaders/*`、`utils/imports.py`、`beat.py`、`bootsteps.py`
- **对最终输出的影响**: 只输出文件路径而非类名，或使用错误分隔符（`:` 而非 `.`）

---

## 失效分布热力图

### GPT-5.4 失败案例分布（19 个 F1=0）

| Failure Type | Count | Percentage | Description |
|-------------|-------|------------|-------------|
| **Type E** | 8 | 42% | 动态符号解析 (symbol_by_name/string resolution) |
| **Type B** | 5 | 26% | 信号回调链 (signal/callback chains) |
| **Type C** | 3 | 16% | Re-export/名称生成 |
| **Type A** | 2 | 11% | Bootstep 生命周期 |
| **Type D** | 1 | 5% | 命名空间混淆 |

### 分难度 × 失效类型矩阵

| Difficulty | Type A | Type B | Type C | Type D | Type E |
|:-----------|:------:|:------:|:------:|:------:|:------:|
| **Easy** (15) | 0 | 1 | 1 | 0 | 2 |
| **Medium** (20) | 0 | 2 | 2 | 1 | 5 |
| **Hard** (15) | 2 | 2 | 0 | 0 | 1 |
| **Total** | 2 | 5 | 3 | 1 | 8 |

### Type E 深度分析（42% 失败占比，最严重瓶颈）

| Root Cause | Count | Percentage | Example |
|------------|-------|------------|---------|
| **格式问题**（System Prompt 可修复） | 2 | 25% | `celery.concurrency.eventlet:TaskPool` 应为 `.` |
| **语义问题**（RAG/FT 需解决） | 6 | 75% | 输出文件路径而非 FQN，或追踪到错误符号 |

**格式问题详情**：

| Case | Prediction | Ground Truth | Fix |
|------|------------|--------------|-----|
| easy_012 | `celery.concurrency.eventlet:TaskPool` | `celery.concurrency.eventlet.TaskPool` | 将 `:` 替换为 `.` |
| easy_013 | `celery.concurrency.solo:TaskPool` | `celery.concurrency.solo.TaskPool` | 将 `:` 替换为 `.` |

**语义问题详情**：

| Case | Prediction | Ground Truth | 问题描述 |
|------|------------|--------------|---------|
| hard_004 | `celery.worker.request:Request` | `celery.worker.request.Request` | 格式对但 indirect 全错 |
| medium_008 | `celery/app/task.py: Task.start_strategy` | `celery.worker.strategy.default` | 追踪到了错误的符号入口 |
| medium_007 | `celery/_state.py, celery/app/base.py...` | `celery.loaders.default.Loader` | 只知道涉及哪些文件，不知道最终实例化的类 |
| celery_hard_018 | `celery/fixups/django.py` | `celery.contrib.django.task.DjangoTask` | 完全不知道 Django fixup 条件下 Task 类的动态解析终点 |
| celery_medium_020 | `celery/_state.py...` | `celery.loaders.default.Loader` | 只知道涉及哪些文件，不知道 loader 属性的动态解析链 |
| medium_021 | `celery/__init__` 实现细节 | `celery.utils.imports.symbol_by_name` | 追踪到使用位置而非函数定义 |

---

## Bad Case 清单（GPT-5.4）

| Case ID | Difficulty | F1 | Failure Type | Baseline Answer | Gold Answer | Root Cause |
|:--------|:-----------|:---|:------------|:---------------|:-----------|:-----------|
| easy_002 | easy | 0.0 | Type C | `celery.__init__.shared_task` | `celery.app.shared_task` | 停在懒加载 Proxy 而非最终函数 |
| easy_006 | easy | 0.0 | Type B | `celery.__init__.current_task -> ...` (过度复杂) | `celery._state.get_current_task` | 返回完整调用链而非最终目标 |
| easy_012 | easy | 0.0 | Type E | `celery.concurrency.eventlet:TaskPool` | `celery.concurrency.eventlet.TaskPool` | 错误分隔符 `:` |
| easy_013 | easy | 0.0 | Type E | `celery.concurrency.solo:TaskPool` | `celery.concurrency.solo.TaskPool` | 错误分隔符 `:` |
| medium_004 | medium | 0.0 | Type C | `gen_task_name` | `celery.utils.imports.gen_task_name` | 缺少模块前缀 |
| medium_007 | medium | 0.0 | Type E | 文件列表 | `celery.loaders.default.Loader` | 只输出文件路径而非类 |
| medium_008 | medium | 0.0 | Type E | 文件路径格式 | `celery.worker.strategy.default` | 追踪到错误的符号入口 |
| medium_012 | medium | 0.0 | Type B | `null` | `celery.app.base.Celery._task_from_fun` | 解析完全失败 |
| medium_014 | medium | 0.0 | Type B | `_acquire_tasks` | `celery._state.connect_on_app_finalize` | 完全错误 |
| medium_018 | medium | 0.0 | Type C | 错误链路 | `celery._state.disable_trace` | 完全追踪错 |
| medium_020 | medium | 0.0 | Type D | 混淆 subtask/signature | `celery.canvas.signature` | 命名空间混淆 |
| medium_021 | medium | 0.0 | Type E | 文件路径 | `celery.utils.imports.symbol_by_name` | 追踪到使用位置而非定义 |
| celery_medium_020 | medium | 0.0 | Type E | 文件列表 | `celery.loaders.default.Loader` | 只输出文件路径 |
| hard_003 | hard | 0.0 | Type B | `connect_on_app_finalize` | `celery._state._announce_app_finalized` | 缺少 `celery._state` 前缀 |
| hard_004 | hard | 0.0 | Type E | `celery.worker.request:Request` | `celery.worker.request.Request` | 错误分隔符 |
| celery_hard_015 | hard | 0.0 | Type B | 4 个方法的复杂链 | `celery.app.base.Celery._autodiscover_tasks` | 过度复杂化 |
| celery_hard_018 | hard | 0.0 | Type E | 文件路径 | `celery.contrib.django.task.DjangoTask` | 不知道动态解析终点 |
| celery_hard_122 | hard | 0.0 | Type A | 错误断点方法 | `celery.bootsteps.Blueprint.apply` | Bootstep 生命周期混淆 |
| celery_hard_024 | hard | 0.0 | Type A | `setup_schedule` | `celery.beat.PersistentScheduler._create_schedule` | 方法混淆 |

---

## Bad Case 专栏

### Bad Case 1: easy_012（Type E — FQN 格式错误）

**1. 原始问题**: In `celery.concurrency.get_implementation`, what does `get_implementation('eventlet')` resolve to?

**2. Baseline 错误答案**:
```json
{"direct_deps": ["celery.concurrency.eventlet:TaskPool"]}
```
使用了 `:` 分隔符而非 `.`，且没有完整理解 `symbol_by_name` 的解析机制。

**3. 失效归因**: Type E（动态加载与字符串引用失配）。模型记住了 alias 表里写的是 `celery.concurrency.eventlet:TaskPool`，但不知道应该翻译成 `.` 分隔的标准 FQN 格式。

**4. 优化后答案**: 
- PE（System Prompt）：加一句"必须用 `.` 分隔 FQN，禁用 `:`" → 可从 F1=0 修复到接近满分
- 这是 PE 消融实验里最漂亮的数据点：只加一句话解决 4% 的 case

**5. 纠正机理**: 这本质上是输出格式问题，不是推理问题。System Prompt 可以直接约束，不需要 RAG 或 FT。

---

### Bad Case 2: medium_007（Type E — 输出文件路径而非 FQN）

**1. 原始问题**: 当线程中没有 current app 且未设置 `CELERY_LOADER` 时，首次访问 `celery.current_app.loader` 最终会实例化哪个 Loader 类？

**2. Baseline 错误答案**:
```json
{"direct_deps": ["celery/_state.py", "celery/app/base.py", "celery/loaders/__init__.py", "celery/loaders/default.py"]}
```
返回的是文件路径列表，不是最终实例化的类。

**3. 失效归因**: Type E。模型知道涉及哪些文件，但不知道 `symbol_by_name` 最终会把 `celery.loaders.default:Loader` 解析成 `celery.loaders.default.Loader` 这个真实类。

**4. 优化后答案**:
- PE 效果有限：Few-shot 示例可以演示"什么是正确终点"，但无法教会推理机制
- RAG：检索到 `symbol_by_name` 的源码和 `LOADER_ALIASES` 的定义，能帮助理解解析逻辑
- FT：需要在训练数据中包含足够多的 `symbol_by_name` 解析样本，让模型学会这个模式

**5. 纠正机理**: RAG 检索到源码上下文，模型才能理解 `Loader` 是实例化结果而非文件路径。

---

### Bad Case 3: celery_hard_018（Type E — Django fixup 动态解析终点）

**1. 原始问题**: 在满足 Django fixup 前置条件（`DJANGO_SETTINGS_MODULE` 已设置、`django` 可导入、且 `app.loader_cls` 不含 `django`）且未自定义 `task_cls` 时，`app.Task` 的最终基类解析到哪个真实类？

**2. Baseline 错误答案**:
```json
{"direct_deps": ["celery/fixups/django.py"]}
```
只返回了文件路径，不知道 `app.Task` 在 Django fixup 条件下被改写成了 `DjangoTask`。

**3. 失效归因**: Type E。这是条件动态解析的典型失败——模型不知道 Django fixup 会在运行时把 `app.Task` 的字符串值从默认 `celery.app.task:Task` 改写成 `celery.contrib.django.task:DjangoTask`。

**4. 优化后答案**:
- PE：Few-shot 可以演示"Django fixup 条件下的解析结果"，但无法教会识别条件本身
- RAG：检索到 `celery/fixups/django.py` 的 `fixup` 函数和 `DjangoTask` 定义，可以建立连接
- FT：需要大量同类条件解析样本

**5. 纠正机理**: 这类问题 RAG 比 PE 更有效，因为需要源码级别的上下文才能理解 fixup 的改写机制。

---

## 结论

| 问题 | 答案 |
|------|------|
| 最主要的失效类型是 | **Type E（动态符号解析）**，占 42% 的失败 case |
| 对 Hard 样本影响最大的失效类型是 | **Type E** 和 **Type B** |
| PE 最能解决的失效类型是 | **Type E 中的格式问题**（加 System Prompt 一句话可修复 2 个 case） |
| RAG 最能解决的失效类型是 | **Type C（再导出链）**、**Type E 中的语义问题**（提供 `symbol_by_name` 源码上下文） |
| FT 最能解决的失效类型是 | **Type B（隐式依赖幻觉）**——这是 RAG 无法解决的核心问题 |

---

## 后续实验计划

| 优先级 | 实验 | 预期结论 |
|--------|------|---------|
| P0 | GLM-5 / Qwen3.5-9B baseline | 确认 GPT-5.4 是唯一上界，还是普遍水平 |
| P1 | PE 格式修复（System Prompt 禁用 `:`） | 验证 easy_012/easy_013 能从 F1=0 修复到 >0.8 |
| P2 | PE 逐步叠加实验 | 量化 CoT / Few-shot 对各失效类型的独立增益 |
| P2 | RAG 端到端实验 | 验证 RAG 对 Type C/D/E 的补偿效果 |
| P3 | FT 训练 | 验证 FT 对 Type B 幻觉的解决能力 |
