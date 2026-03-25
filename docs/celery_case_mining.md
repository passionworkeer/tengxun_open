# Celery Case Mining Guide

## 文档目标

本文件用于指导“50 条人工评测样本”从 Celery 源码中的哪些位置优先提取，避免盲扫整个仓库。

当前绑定源码快照见 [repo_snapshot.md](repo_snapshot.md)。

## 优先挖掘区域

### 第一优先级：任务注册与应用入口

| 文件/目录 | 价值 | 推荐样本类型 |
| :--- | :--- | :--- |
| `external/celery/celery/__init__.py` | 顶层懒加载、再导出和 `recreate_module` 映射非常集中 | `easy` 再导出、`medium` 懒加载转发 |
| `external/celery/celery/app/__init__.py` | `shared_task` 的真实注册逻辑在这里，不在表面导入处 | `hard` 装饰器隐式注册 |
| `external/celery/celery/app/base.py` | `Celery.task`、`_task_from_fun`、`gen_task_name`、`get_loader_cls` 都在这里汇合 | `medium` 调用链、`hard` 任务注册、动态解析 |
| `external/celery/celery/app/builtins.py` | 内置任务通过 `connect_on_app_finalize` 注册，适合 Hard 样本 | `hard` finalize 回调、隐式任务生成 |

### 第二优先级：动态加载与字符串映射

| 文件/目录 | 价值 | 推荐样本类型 |
| :--- | :--- | :--- |
| `external/celery/celery/loaders/__init__.py` | `get_loader_cls` 通过 alias 转类，适合字符串到类的映射 | `medium` alias 解析 |
| `external/celery/celery/loaders/base.py` | `importlib`、`symbol_by_name`、模块装载逻辑集中 | `hard` 动态加载 |
| `external/celery/celery/utils/imports.py` | `symbol_by_name`、`instantiate`、`gen_task_name` 是很多链路的跳板 | `medium`/`hard` 动态符号解析 |
| `external/celery/celery/app/backends.py` | backend 名称到类的映射清晰，适合构造标准化问答 | `medium` 名称映射 |

### 第三优先级：并发、调度与 worker 组件装配

| 文件/目录 | 价值 | 推荐样本类型 |
| :--- | :--- | :--- |
| `external/celery/celery/concurrency/__init__.py` | pool 名称经 alias 动态选择实现 | `medium` alias 到类 |
| `external/celery/celery/beat.py` | scheduler 类的动态加载路径比较典型 | `medium`/`hard` 字符串配置到类 |
| `external/celery/celery/bootsteps.py` | 组件依赖通过 `symbol_by_name` 解析 | `hard` 组件装配链 |
| `external/celery/celery/worker/strategy.py` | `task.Request` 到 Request 实现的解析链典型 | `hard` 属性字符串映射 |

## 推荐样本配比

### Easy：15 条

- 显式跨文件 import
- 顶层 `__init__.py` 再导出
- 简单别名引用

优先来源：

- `celery/__init__.py`
- `celery/app/__init__.py`
- `celery/backends/__init__.py`
- `celery/concurrency/__init__.py`

### Medium：20 条

- 多层 `__init__.py` 再导出链
- alias 到类
- 浅层继承
- 简单字符串到类 / 函数映射

优先来源：

- `celery/app/base.py`
- `celery/loaders/__init__.py`
- `celery/app/backends.py`
- `celery/utils/imports.py`
- `celery/beat.py`

### Hard：15 条

- `@app.task` / `@shared_task`
- `connect_on_app_finalize`
- `symbol_by_name`
- `importlib`
- 自动发现 / 延迟导入 / 字符串入口

优先来源：

- `celery/app/__init__.py`
- `celery/app/base.py`
- `celery/app/builtins.py`
- `celery/loaders/base.py`
- `celery/bootsteps.py`
- `celery/worker/strategy.py`

## 失效类型到源码区域映射

| 失效类型 | 典型触发区域 |
| :--- | :--- |
| Type A 长上下文截断丢失 | `celery/app/base.py` 这类超长文件 |
| Type B 隐式依赖断裂 | `celery/app/__init__.py`、`celery/app/builtins.py` |
| Type C 再导出链断裂 | `celery/__init__.py`、`celery/app/__init__.py` |
| Type D 命名空间混淆 | 多个模块里同名类/函数、顶层导出与真实实现分离的场景 |
| Type E 动态加载与字符串引用失配 | `loaders/*`、`utils/imports.py`、`beat.py`、`bootsteps.py` |

## 推荐标注顺序

1. 先做 10 条 Easy，把 FQN 标注流程跑顺。
2. 再做 10 条 Medium，优先选再导出链和 alias。
3. 然后做 10 条 Hard，优先选 `shared_task` 和 `connect_on_app_finalize`。
4. 最后补足 15 / 20 / 15 的目标比例。

## 质检清单

- 入口符号是不是来自真实文件而不是文档示例
- `gold_fqns` 是不是最终目标而非中间跳板
- 样本难度是不是和链路复杂度匹配
- 样本能不能被另一个人根据源码独立复核
