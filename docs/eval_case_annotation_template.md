# Eval Case Annotation Template

## 使用方式

每整理出一条人工样本，先按本模板在文档里完成一次人工标注和自查，确认没问题后再写入 `data/eval_cases_celery.json`。

## 单条样本标注模板

```md
### Case ID
- id: celery_easy_001
- difficulty: easy / medium / hard
- category: re_export / direct_import / alias_resolution / ...
- failure_type: Type A / Type B / Type C / Type D / Type E
- implicit_level: 1-5

### 问题定义
- question: （只问一个清晰问题）
- 任务目标:

### 入口信息
- source_file: （相对 external/celery/ 的路径）
- source_commit: b8f85213f45c937670a6a6806ce55326a0eb537f
- 入口所在行号:

### 正确答案
- ground_truth:
  - direct_deps: []
  - indirect_deps: []
  - implicit_deps: []
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
  "id": "celery_hard_021",
  "difficulty": "hard",
  "category": "shared_task_registration",
  "failure_type": "Type B",
  "implicit_level": 4,
  "question": "给定 celery.app.__init__.shared_task 装饰后的函数，最终注册到哪个任务对象路径？",
  "source_file": "celery/app/__init__.py",
  "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
  "ground_truth": {
    "direct_deps": ["celery.app.base.Celery._task_from_fun"],
    "indirect_deps": [],
    "implicit_deps": ["celery.app.builtins.add_backend_cleanup_task"]
  },
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

## failure_type 定义

| 类型 | 失效特征 | Celery 典型案例 |
|------|---------|----------------|
| **Type A** | 长上下文截断丢失 | 超出窗口导致上游定义节点被遗漏 |
| **Type B** | 隐式依赖断裂（幻觉） | `@app.task` 装饰器注册时 LLM 编造不存在的内部调用 |
| **Type C** | 再导出链断裂 | 跨多层 `__init__.py` 别名转发，链路在中间节点中断 |
| **Type D** | 跨文件命名空间混淆 | 同名函数/类导致 LLM 张冠李戴 |
| **Type E** | 动态加载与字符串引用失配 | `importlib`/配置字符串，LLM 无法把字符串入口映射回真实符号 |

## 难度判断规则

### `easy`

- 主要靠显式 import 就能完成
- 不需要跨多层中间节点
- 几乎没有运行时映射
- implicit_level: 1-2

### `medium`

- 存在再导出、alias、浅层继承或一层字符串映射
- 需要跨 2 到 3 个模块才能锁定目标
- implicit_level: 2-3

### `hard`

- 依赖装饰器、回调注册、动态加载、延迟导入或字符串入口
- 需要结合运行时约定才能确定真实目标
- implicit_level: 3-5

## 人工复核要求

- 每 10 条样本至少抽检 3 条
- Hard 样本必须单独复核
- 出现争议时，优先在本模板中写清证据链，再决定是否纳入正式评测集
- 证据链必须能回到源码，不能只写"可推测"
