# Repo Snapshot

## 外部分析对象

- 仓库名称：Celery
- 远程地址：`https://github.com/celery/celery.git`
- 本地路径：`external/celery/`

## 当前绑定版本

- 分支：`main`
- 提交号：`b8f85213f45c937670a6a6806ce55326a0eb537f`
- 提交信息：`Fix: prioritize request ignore_result over task definition (#10184)`
- 拉取时间：`2026-03-25 15:08 +08:00`
- 拉取方式：`git clone --depth 1`

## 使用约束

- 后续评测集和微调集默认都绑定到这个提交号
- 如果后续重新拉取或切换提交号，需要在本文件追加新的快照记录
- 报告中引用源码行为时，优先使用相对 `external/celery/` 的路径

## 关键源码目录

- `celery/__init__.py` - 顶层懒加载、再导出
- `celery/app/__init__.py` - `shared_task` 注册逻辑
- `celery/app/base.py` - `Celery.task`、`_task_from_fun` 等核心方法
- `celery/app/builtins.py` - 内置任务通过 `connect_on_app_finalize` 注册
- `celery/loaders/*` - 动态加载模块
- `celery/utils/imports.py` - `symbol_by_name` 等动态符号解析
- `celery/concurrency/__init__.py` - pool 名称动态选择
- `celery/beat.py` - scheduler 动态加载
- `celery/bootsteps.py` - 组件依赖解析
- `celery/worker/strategy.py` - `task.Request` 解析链
