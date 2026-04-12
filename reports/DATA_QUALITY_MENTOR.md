# 数据质量毒舌审查报告

**审查人**: 数据质量洁癖患者  
**日期**: 2026-04-12  
**审查对象**: `data/eval_cases.json` (81条) + `data/finetune_dataset_500_strict.jsonl` (500条)  
**结论先行**: **数据能用，但不能闭眼用。有3个必须修的硬伤，修完才能拿出去见人。**

---

## 一、新增 27 条评测用例质量审查

### 1.1 总体情况

新增 27 条分布如下：

| 难度 | 数量 | 占比 |
|------|------|------|
| hard | 23   | 85.2% |
| medium | 4  | 14.8% |
| easy | 0   | **0% ← 零！** |

**类型分布**:

| failure_type | 数量 |
|-------------|------|
| Type E | 11 |
| Type A | 5 |
| Type D | 7 |
| Type B | 3 |
| Type C | 1 |

**问题一**: 27条新增全部堆在 Hard 或 Medium，一条 Easy 都没加。旧 54 条里 Easy 有 15 条，新增后 Easy 占比从 27.8% 跌到 18.5%。如果这叫"补Hard样本"，你得说清楚为什么一刀砍掉 Easy 的补充需求——还是说实习生压根没想过这件事？

**问题二**: Type C 只补了 1 条 (`celery_type_c_003`)，但 `celery_type_c_004` 的 ID 以 `type_c_` 开头，`failure_type` 字段却写的是 `"Type E"`，source_note 也写的是 "Type E"。这条数据是改了 type 忘了改 ID，还是一开始就贴错标签？**标注标签和 ID 对不上，这是基本质量事故**。

### 1.2 Hard 样本真的够 Hard 吗？——抽检 5 条

**Case 1: `celery_type_e_002`** (hard, Type E)  
问题: `symbol_by_name('celery.concurrency.prefork:TaskPool')` 最终解析到哪个类?  
GT: `direct_deps: [celery.concurrency.prefork.TaskPool], indirect_deps: [celery.utils.imports.symbol_by_name]`  
**评价**: 够 Hard。解析路径要跨 celery → kombu → importlib，三跳链路，且 symbol_by_name 本身是从 kombu 透传的。模型必须理解冒号分隔符语义。**通过**。

**Case 2: `celery_type_b_001`** (hard, Type B)  
问题: `app.autodiscover_tasks(force=True)` 时哪个函数直接被调用？  
GT: `direct_deps: [Celery._autodiscover_tasks], indirect_deps: [autodiscover_tasks, BaseLoader.autodiscover_tasks]`  
**评价**: 够 Hard。force=True 绕过 lazy signal 机制，直接调内部方法，非熟悉源码不易发现。**通过**。

**Case 3: `celery_type_d_014`** (hard, Type D)  
问题: `Task` 是 Proxy 对象，`Task.send` 时实际执行哪个方法？  
GT: `direct_deps: [], indirect_deps: [celery.app.task.Task], implicit_deps: [create_task_cls, subclass_with_self, Proxy]`  
**亮点**: direct_deps 为空是正确的——通过 Proxy 无法静态确定。这个 case 的 GT 在语义上相当精准。**通过，且是质量较高的 case**。

**Case 4: `celery_type_d_011`** (medium, Type D)  
问题: ConfigurationView 继承 ChainMap，first-found-wins 是什么效果？  
GT: `direct_deps: [celery.utils.collections.ConfigurationView]`  
**评价**: 单跳，直接答 ConfigurationView。这题标 medium 都算高估，easy 差不多。依赖链深度=1，对模型没什么挑战。**质量偏低**。

**Case 5: `celery_type_a_014`** (hard, Type A)  
问题: `Blueprint.apply` 执行顺序，`StartStopStep.include()` 返回 False 时 `create` 是否执行？  
GT: 6个FQN，覆盖 Blueprint.apply 的完整调用链。  
**评价**: 这才叫 Hard。需要理解 bootstep 生命周期：实例化 → create → include check → mount，条件分支复杂。**通过，最难的 case 之一**。

**整体评价**: 5 条抽检中 4 条 Hard/难度匹配，1 条 (type_d_011) 明显偷懒。主体质量可接受，但不算惊艳。

---

## 二、Ground Truth 准确率验证

### 2.1 FQN 验证方法

用 AST 解析 Celery 源码（`external/celery/`），提取所有 function/class 定义，共找到 **2936 个 FQN**，然后逐一比对新增 27 条的 ground truth。

**第一轮扫描结果（仅 def/class）**:
- 检查 FQN 总数: 83
- 找到: 68 (81.9%)
- 未找到: 15 (18.1%)

**先别急着判死刑**——深查发现那 15 个"缺失"FQN 分为三类：

| 类别 | 代表FQN | 实际状态 |
|------|---------|---------|
| 模块级变量 | `celery.app.backends.BACKEND_ALIASES` | 定义在 app/backends.py 第13行，是个 dict ✓ |
| 模块级变量 | `celery.loaders.LOADER_ALIASES` | 定义在 loaders/__init__.py 第8行 ✓ |
| 模块级变量 | `celery.signals.import_modules` | signals.py 第107行 Signal 实例 ✓ |
| 公开别名 | `celery.canvas.chord` | canvas.py 第2373行 `chord = _chord` ✓ |
| kombu 透传 | `celery.utils.imports.symbol_by_name` | 在 celery 的 __all__ 中声明，官方公开 API ✓ |

**修正后结论**: 83/83 个 FQN 实际上都是可访问的有效路径，**准确率 100%**。

但这里有个**深坑**需要警觉：

`celery.utils.imports.symbol_by_name` 的**实现在 kombu**，celery 只是 re-export：
```python
# celery/utils/imports.py
from kombu.utils.imports import symbol_by_name  # 真正的实现在 kombu
__all__ = ('NotAPackage', 'qualname', 'instantiate', 'symbol_by_name', ...)
```

新增 27 条中有 **10 条**（占 37%）将 `celery.utils.imports.symbol_by_name` 列为依赖。这些 case 的 GT 使用的是 celery 命名空间路径，但如果评估时检查"该函数是否在 celery 源码中实现"，会得到 False。

**这不是错误，但是个陷阱**：评估脚本、批阅人、以及将来对比模型输出时，需要明确"我们接受 re-export 路径"。如果没有文档说明这一点，迟早出问题。

### 2.2 重点存疑 case 手动验证

**1. `celery_type_e_009` (hard, Type E)**  
GT: `indirect_deps: [celery.loaders.get_loader_cls], implicit_deps: [celery.loaders.LOADER_ALIASES]`  
手动验证: `celery/loaders/__init__.py` 确实定义了 `get_loader_cls` 函数和 `LOADER_ALIASES` dict。GT 正确。

**2. `celery_type_a_013` (hard, Type A)**  
GT: `direct_deps: [celery.signals.import_modules]`  
手动验证: `celery/signals.py` 第107行 `import_modules = Signal(name='import_modules')`。GT 正确。

**3. `celery_type_d_013` (hard, Type D)**  
GT: `implicit_deps: [celery.canvas.chord]`  
手动验证: `celery/canvas.py` 第2373行 `chord = _chord`，`chord` 也在 `__all__` 中声明。GT 正确。

**结论**: 验证了27条新增 case 的共83个FQN，**100% 可在 Celery 源码或其官方公开 API 中找到**。Ground truth 准确率达标。

---

## 三、数据一致性审查

### 3.1 Schema 不一致 —— 最丢人的地方

81条数据里有 **11 条** 字段集与主流不一致：

| 问题类型 | 影响 case 数 | 具体ID |
|---------|------------|--------|
| 缺少 `source_note` 字段 | 6条 | easy_005, easy_006, easy_008, medium_006, medium_007, celery_medium_020 |
| 多出 `entry_symbol` + `entry_file` 字段 | 5条 | celery_medium_025, celery_easy_021, celery_easy_022, celery_easy_023, celery_easy_024 |

这 11 条数据在不同批次生成，没有做统一格式校验就合入。**这是基本 hygiene 问题，属于不可辩解的低级错误**。

### 3.2 `type` 字段 —— 死字段烂在那里

81 条数据，`type` 字段全部为 `null`。没有一条有值。

这个字段存在于 schema 里，但从来没被填充。要么删掉，要么补充，放在那里是在告诉所有读数据的人"这个项目的 schema 没人认真管过"。

### 3.3 ID 命名体系混乱

数据集里存在 **3套完全不同的命名规范**：
```
easy_001            # 旧格式：难度_序号
celery_hard_014     # 中期格式：celery_难度_序号（且序号不连续，有014/016跳序）
celery_type_e_002   # 新格式：celery_类型_序号
```

跨三套命名混在一个文件里，没有任何注释说明历史。`celery_hard_014` 之后直接跳到 `celery_hard_016`，`015` 去哪了？没有记录，没有说明。

**额外失误**: `celery_type_c_004` 的 ID 明示这是 Type C case，但 `failure_type` 字段是 `"Type E"`。要么是改了类型忘了改 ID，要么是 ID 生成脚本有 bug。

### 3.4 difficulty 分布与 failure_type 是否匹配？

**新增 27 条**的 cross-tab：

| | Type A | Type B | Type C | Type D | Type E |
|--|-------|-------|-------|-------|-------|
| hard | 5 | 3 | 0 | 5 | 10 |
| medium | 0 | 0 | 1 | 2 | 1 |
| easy | 0 | 0 | 0 | 0 | 0 |

Type E 的 Hard 案例独大（10条），而 Type B/C 的 Hard 覆盖严重不足。Type C 全部 81 条只有 12 条 Hard，新增只贡献 0 条 Hard Type C。

整体 81 条评测集：

| 难度 | 数量 | 比例 |
|------|------|------|
| easy | 15 | 18.5% |
| medium | 23 | 28.4% |
| hard | 43 | **53.1%** |

超过一半的评测用例是 Hard。这对于衡量模型"平均能力"而言严重偏斜，会让基线指标看起来比实际更差。

---

## 四、评测集偏差审查

### 4.1 最严重的问题：Eval vs 微调数据分布错位

| 难度 | Eval 占比 | Finetune 占比 | 差值 |
|------|----------|--------------|------|
| easy | 18.5% | **33.8%** | -15.3 pp |
| medium | 28.4% | 35.2% | -6.8 pp |
| hard | **53.1%** | 31.0% | **+22.1 pp** |

**这是严重问题**。模型在 Hard 样本上只训练了 31% 的数据，但 Eval 里有 53% 是 Hard。评测分数系统性偏低不是因为模型差，而是因为你拿了一把更难的尺子来量。

如果汇报指标时没有注明这个分布差，评委/老板会得到错误印象。

### 4.2 训练集和评测集 Overlap 检查

**无 overlap**。精确比对 eval 的 81 个 question 和 finetune 的 500 个 input，以及完整 ground truth JSON 字符串对比：
- Question/input 完全匹配: **0 条**
- Ground truth 完全匹配: **0 条**

数据隔离做得好，这点给满分。

### 4.3 Category 覆盖代表性

Finetune 数据包含 **300+ 个 category**（严重碎片化），而 eval 集只覆盖约 80 个 category。两者的 category 分布有大量不重叠：
- Finetune 有大量 `kombu_*`、`driver_type_chain`、`connection_pool` 等纯 kombu/底层场景
- Eval 集集中在 `re_export`、`alias_resolution`、`symbol_by_name_*`、`bootstep_*` 等 celery 核心路径

Finetune 训练了大量 eval 不会考的场景，eval 考了很多 finetune 较少覆盖的多跳链路。**覆盖错位，导致评测结果低估了模型在 finetune 主场景上的实际能力**。

---

## 五、微调数据质量审查

### 5.1 数量够吗？

500 条，覆盖 300+ category，平均每个场景不到 2 条训练样本。**不够**。LLM 微调一般需要每类场景 20-50 条才能稳定泛化。这个数量适合 few-shot 演示，不适合真正意义上的"微调使模型学会推理路径"。

### 5.2 质量声称

所有 500 条标注 `"verified": true`，其中：
- `manual`: 476 条 (95.2%)
- `manual_strict_variant`: 24 条 (4.8%)

`manual_strict_variant` 到底是什么含义？代码里没有定义，报告里没有说明。这 24 条和普通 manual 有什么区别？如果没有文档，这个字段就是噪音。

### 5.3 重复数据

全量精确比对 input 字段：
- **2 条完全重复的 input**（`chord_callback` 相关场景 + `recreate_module` 相关场景）
- 占比 0.4%，属于可接受范围，但说明 dedup 没做

### 5.4 strict-clean 清洗标准是什么？

对比 `finetune_dataset_500.jsonl` 和 `finetune_dataset_500_strict.jsonl`：
- strict 版本文件更大（550,959 bytes vs 539,464 bytes）
- **strict 版本比原版更大？** 这通常说明 strict 是通过添加内容（比如更详细的 reasoning chain）而非删除内容来"清洗"的。`strict` 到底严格在哪里，没有文档说明。

---

## 六、这份数据能不能用来训练？

**能用，但必须带着清醒的认知用。**

**可以做的**：
- 用于当前项目的评测基线，结果有参考价值
- 用于 demo 和技术答辩，样本设计思路是对的
- Ground truth 本身在语义层面准确率达标

**不能做的**：
- 不能拿 eval 分数直接对外宣称"模型准确率 X%"而不注明难度分布偏斜
- 不能认为 500 条微调数据足够让模型在所有场景上泛化
- 不能假设 eval 和实际生产数据分布一致

---

## 七、优先级修复清单

### P0 —— 必须修，不修等于数据烂

| # | 问题 | 操作 |
|---|------|------|
| 1 | `celery_type_c_004` 的 ID 和 `failure_type` 字段不一致 | 要么把 ID 改为 `celery_type_e_xxx`，要么把 failure_type 改为 Type C 并验证 GT |
| 2 | 11 条 schema 不一致（missing/extra 字段） | 统一补齐 `source_note`，删除多余的 `entry_symbol`/`entry_file` 或在 schema 文档中声明它们 |
| 3 | `type` 字段全部 null | 要么删除该字段，要么补充数据；烂在那里影响所有人 |

### P1 —— 必须说清楚，否则结论会被质疑

| # | 问题 | 操作 |
|---|------|------|
| 4 | eval 难度分布 (Hard 53%) vs finetune (Hard 31%) 严重错位 | 在所有报告/答辩材料里注明这一差异；或补充 Easy/Medium Hard 评测样本使分布更均衡 |
| 5 | `celery.utils.imports.symbol_by_name` 的 re-export 语义 | 在数据文档中明确：项目接受 celery 命名空间下 re-export 的 FQN，不要求"定义在 celery 源码中" |
| 6 | ID 命名混乱 | 写一个 ID 命名规范文档，或统一重命名（建议不动旧 ID，只对新增统一用 `celery_type_{X}_{nnn}` 格式） |

### P2 —— 有时间就修，没时间记录技术债

| # | 问题 | 操作 |
|---|------|------|
| 7 | `manual_strict_variant` 含义未文档化 | 在 data README 里说明这 24 条和普通 manual 的区别 |
| 8 | finetune 2 条完全重复 input | dedup 后删除 |
| 9 | finetune strict 版本比原版更大 | 写清楚 strict 清洗逻辑（是 augmentation 还是 refinement） |
| 10 | 新增 27 条零 Easy 覆盖 | 补充 5-8 条 Easy Type A/B/D/E 样本保持分布平衡 |
| 11 | Type C 没有 Hard 样本 | 补充 2-3 条 Hard Type C（re_export 场景中有足够的 celery 案例） |

---

## 附：核验记录

| 验证项 | 结果 |
|--------|------|
| 新增 27 条中 FQN 可在 celery 源码中找到（含 re-export） | **83/83 = 100%** |
| 新增 27 条 GT 语义正确性（抽检 5 条） | **4/5 正确，1条偏易** |
| eval vs finetune question overlap | **0 条 overlap** |
| eval vs finetune GT overlap | **0 条 overlap** |
| finetune 500 条内部重复 | **2 条重复 input** |
| schema 不一致 case 数 | **11/81** |
| `type` 字段非 null 数量 | **0/81** |

---

*报告完毕。修 P0 的时间不超过半天，不要以"先用着"为借口拖。*
