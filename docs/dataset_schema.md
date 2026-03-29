# Dataset Schema

## 文档目标

本文件用于统一评测集与微调集的数据口径，避免后续在样本构建、标注、评测和报告阶段出现字段漂移。

## 评测集 `data/eval_cases.json`

### 目标

- 面向 `Celery` 的跨文件依赖分析任务
- 至少 50 条人工构建样本
- 每条样本都必须可回溯到真实源码路径
- 任务定义是 `entry-guided`：问题文本之外，还要提供入口文件 anchor，少量样本可再提供入口符号 anchor

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | 是 | 全局唯一 ID，例如 `celery_hard_021` |
| `difficulty` | string | 是 | `easy` / `medium` / `hard` |
| `category` | string | 是 | 对应失效类型或任务类型 |
| `failure_type` | string | 是 | `Type A` / `Type B` / `Type C` / `Type D` / `Type E` |
| `implicit_level` | integer | 是 | 隐式程度等级（1-5），用于工程落地判断 |
| `question` | string | 是 | 给模型的任务描述 |
| `source_file` | string | 是 | 任务显式提供的入口文件 anchor（相对 `external/celery/`） |
| `source_commit` | string | 是 | 来源提交号，保证版本绑定 |
| `ground_truth` | object | 是 | 正确答案，包含三个子字段 |
| `ground_truth.direct_deps` | string[] | 是 | 直接依赖 FQN 列表 |
| `ground_truth.indirect_deps` | string[] | 是 | 间接依赖 FQN 列表 |
| `ground_truth.implicit_deps` | string[] | 是 | 隐式依赖 FQN 列表 |
| `reasoning_hint` | string | 否 | 仅供人工标注和质检，不直接喂给 baseline |
| `source_note` | string | 否 | 样本来源说明，例如源码位置或 issue 线索 |

### 标注原则

- 一条样本只解决一个清晰问题，不把多个问题捆绑成一题
- `ground_truth` 必须是最终要命中的真实符号，而不是中间跳板
- `difficulty` 由链路深度和隐式程度共同决定，不只看文件数量
- 每条样本要能由他人重新从源码复核
- `failure_type` 必须明确，用于后续热力图绘制
- `source_file` 是任务提供的入口锚点，评测和提示词可使用它，但不能把它当作模型自己推理出的中间答案

### 难度分布目标

| 难度 | 数量 | 特征描述 |
|------|------|---------|
| Easy | 15 条 | 显式直接跨文件 import |
| Medium | 20 条 | 跨多层 `__init__.py` 再导出链、浅层类继承 |
| Hard | 15 条 | `@app.task` 装饰器隐式挂载、`importlib` 动态加载 |

---

## 微调集 `data/finetune_dataset_500.jsonl`

### 目标

- 至少 500 条高保真记录
- 先生成候选，再通过 `data_guard.py` 自动校验剔除脏数据
- 保留困难样本占比，避免训练集被简单样本稀释

### 字段定义

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `instruction` | string | 是 | 任务描述 |
| `input` | string | 是 | 提供给模型的上下文（源码片段） |
| `output` | string | 是 | 包含推理过程和最终 JSON 结果 |
| `difficulty` | string | 是 | `easy` / `medium` / `hard` |
| `failure_type` | string | 否 | `Type B` / `Type C` / `Type D` / `Type E` |
| `category` | string | 否 | 装饰器、再导出、动态导入等 |
| `repo_path` | string | 否 | 来源文件路径 |
| `verified` | boolean | 是 | 是否通过 `data_guard.py` 校验 |
| `verify_method` | string | 视情况 | `jedi+ast` / `manual` |

补充约束：

- `output` 末尾必须包含一个可解析的 JSON 答案块，至少能还原 `direct_deps / indirect_deps / implicit_deps` 三个列表；也可以额外冗余一个独立 `ground_truth` 字段，方便 `data_guard.py` 校验。
- 当 `verified=true` 时，`verify_method` 视为条件必填，不能留空。

### 数据来源配比

| 来源 | 数量 | 方式 |
|------|------|------|
| Celery 源码自动提取 | 200 条 | AST 解析 + 脚本生成候选 QA |
| 基线模型错误案例纠正 | 150 条 | 直接从 Day 2 Bad Case 转化 |
| 5 类失效类型专项 | 100 条 | 针对 Type B/C/D/E 人工构造 |
| 跨项目泛化样本 | 50 条 | 防止过拟合到 Celery 特定代码 |

### 清洗原则

- 严禁保留无法在物理源码中连通的伪链路
- 对动态加载样本需要保留"为什么这条链成立"的辅助说明，便于抽检
- 至少保留 30% 的 Hard 样本
- 预计剔除 15-20% 脏数据

---

## Few-shot 示例库 `data/fewshot_examples_20.json`

### 目标

- 至少 20 条高质量示例
- 按失效类型配比，不允许偏向 Easy

### 按失效类型配比

| 覆盖类型 | 数量 | 重点内容 |
|---------|------|---------|
| Type B 装饰器 | 5 条 | `@app.task`、`@shared_task`、`connect_on_app_finalize` |
| Type C 再导出 | 5 条 | `__init__.py` 多层转发、别名 |
| Type D 命名空间 | 4 条 | 同名函数、局部覆盖 |
| Type E 动态加载 | 4 条 | `symbol_by_name`、`importlib.import_module`、配置字符串 |
| Type A 长上下文 | 2 条 | 超长链路的截断补偿策略 |

---

## 命名规范

- 统一使用小写难度标签：`easy`、`medium`、`hard`
- FQN 使用 Python 模块路径格式，例如 `celery.app.base.Celery.task`
- 文件路径统一相对 `external/celery/` 记录
- `failure_type` 使用 `Type A` / `Type B` / `Type C` / `Type D` / `Type E`

---

## 版本绑定

- 每轮评测和数据构建都要记录对应的 Celery 提交号
- 一旦目标仓库版本变更，需要明确区分"旧评测集"和"新评测集"
- 当前绑定提交号：`b8f85213f45c937670a6a6806ce55326a0eb537f`
