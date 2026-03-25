# Dataset Schema

## 文档目标

本文件用于统一评测集与微调集的数据口径，避免后续在样本构建、标注、评测和报告阶段出现字段漂移。

## 评测集 `eval_cases.json`

### 目标

- 面向 `Celery` 的跨文件依赖分析任务
- 至少 50 条人工构建样本
- 每条样本都必须可回溯到真实源码路径

### 推荐字段

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | 是 | 全局唯一 ID，例如 `easy_001` |
| `difficulty` | string | 是 | `easy` / `medium` / `hard` |
| `category` | string | 是 | 对应失效类型或任务类型，如 `re_export` / `decorator` |
| `question` | string | 是 | 给模型的任务描述 |
| `entry_file` | string | 是 | 入口文件相对路径 |
| `entry_symbol` | string | 是 | 入口符号的 FQN |
| `gold_fqns` | string[] | 是 | 正确答案列表 |
| `reasoning_hint` | string | 否 | 仅供人工标注和质检，不直接喂给 baseline |
| `source_note` | string | 否 | 样本来源说明，例如源码位置或 issue 线索 |

### 标注原则

- 一条样本只解决一个清晰问题，不把多个问题捆绑成一题
- `gold_fqns` 必须是最终要命中的真实符号，而不是中间跳板
- `difficulty` 由链路深度和隐式程度共同决定，不只看文件数量
- 每条样本要能由他人重新从源码复核

## 微调集 `finetune_dataset.jsonl`

### 目标

- 至少 500 条高保真记录
- 先生成候选，再通过自动校验剔除脏数据
- 保留困难样本占比，避免训练集被简单样本稀释

### 推荐字段

| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| `question` | string | 是 | 任务描述 |
| `context` | string | 是 | 提供给模型的上下文 |
| `answers` | string[] | 是 | 标准 FQN 列表 |
| `difficulty` | string | 是 | `easy` / `medium` / `hard` |
| `category` | string | 否 | 装饰器、再导出、动态导入等 |
| `repo_path` | string | 否 | 来源文件路径 |
| `validation_status` | string | 否 | 例如 `passed_ast_check` |

### 清洗原则

- 严禁保留无法在物理源码中连通的伪链路
- 对动态加载样本需要保留“为什么这条链成立”的辅助说明，便于抽检
- 至少保留 30% 的 Hard 样本

## 命名规范

- 统一使用小写难度标签：`easy`、`medium`、`hard`
- FQN 使用 Python 模块路径格式，例如 `celery.app.base.Celery.task`
- 文件路径统一相对 `external/celery/` 记录

## 版本绑定

- 每轮评测和数据构建都要记录对应的 Celery 提交号
- 一旦目标仓库版本变更，需要明确区分“旧评测集”和“新评测集”
