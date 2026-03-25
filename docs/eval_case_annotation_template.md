# Eval Case Annotation Template

## 使用方式

每整理出一条人工样本，先按本模板在文档里完成一次人工标注和自查，确认没问题后再写入 `data/eval_cases.json`。

## 单条样本标注模板

```md
### Case ID
- id:
- difficulty: easy / medium / hard
- category:

### 问题定义
- question:
- 任务目标:

### 入口信息
- entry_file:
- entry_symbol:
- 入口所在行号:

### 正确答案
- gold_fqns:
- 是否有多个正确目标:

### 证据链
- step 1:
- step 2:
- step 3:
- step 4:

### 来源备注
- source_note:
- 关联 issue / PR（如果有）:

### 质检
- 是否能在当前 Celery 提交号下复现: yes / no
- 是否存在歧义: yes / no
- 复核人:
```

## 推荐 JSON 结构

```json
{
  "id": "hard_001",
  "difficulty": "hard",
  "category": "shared_task_registration",
  "question": "给定 celery.app.__init__.shared_task 装饰后的函数，最终注册到哪个任务对象路径？",
  "entry_file": "celery/app/__init__.py",
  "entry_symbol": "celery.app.__init__.shared_task",
  "gold_fqns": [
    "celery.app.base.Celery._task_from_fun"
  ],
  "reasoning_hint": "shared_task 内部通过 connect_on_app_finalize 延迟注册，并在 finalized app 上调用 _task_from_fun。",
  "source_note": "来自 shared_task 装饰器注册路径"
}
```

## category 建议枚举

- `direct_import`
- `re_export`
- `alias_resolution`
- `inheritance_chain`
- `shared_task_registration`
- `app_task_registration`
- `loader_alias`
- `backend_alias`
- `symbol_by_name_resolution`
- `importlib_dynamic_load`
- `bootstep_dependency`

## 难度判断规则

### `easy`

- 主要靠显式 import 就能完成
- 不需要跨多层中间节点
- 几乎没有运行时映射

### `medium`

- 存在再导出、alias、浅层继承或一层字符串映射
- 需要跨 2 到 3 个模块才能锁定目标

### `hard`

- 依赖装饰器、回调注册、动态加载、延迟导入或字符串入口
- 需要结合运行时约定才能确定真实目标

## 人工复核要求

- 每 10 条样本至少抽检 3 条
- Hard 样本必须单独复核
- 出现争议时，优先在本模板中写清证据链，再决定是否纳入正式评测集
