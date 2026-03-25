# Few-shot BC Tail Round 1 Draft

范围说明：本稿仅补齐 `B05 / C04 / C05` 三条候选 few-shot。  
约束说明：不修改正式文档；答案字段仅使用 `ground_truth.direct_deps / indirect_deps / implicit_deps`。

---

## Few-shot B05：`@app.task` 在 execv 场景的分支转发

**问题**：当进程处于 execv 兼容场景（`FORKED_BY_MULTIPROCESSING` 为真）且 `@app.task` 未显式关闭 lazy 时，装饰器流程会先转发到哪个入口，而不是直接走当前 app 的 `_task_from_fun`？

**环境前置条件**：
1. `os.environ['FORKED_BY_MULTIPROCESSING']` 为真值（触发 `USING_EXECV`）。  
2. 调用 `@app.task(...)` 时 `lazy` 未显式设为 `False`（保持默认可懒注册分支）。  
3. 关注的是“首跳转发入口”，不是最终任务实例创建终点。  

**推理过程（>=4步）**：
1. `Celery.task` 开头先判断 `if USING_EXECV and opts.get('lazy', True): ...`。  
2. 该条件成立时，函数不会继续走当前 app 的 `inner_create_task_cls` 主分支。  
3. 代码显式执行 `from . import shared_task`，随后 `return shared_task(*args, lazy=False, **opts)`。  
4. 因而 decorator 首跳入口从 `Celery.task` 转发到 `celery.app.shared_task`。  
5. 后续 `shared_task` 再通过 finalize 回调与已 finalized app 分支触发 `_task_from_fun`，但这已是下一阶段链路。  

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.app.shared_task"
    ],
    "indirect_deps": [
      "celery.app.base.Celery.task"
    ],
    "implicit_deps": [
      "celery._state.connect_on_app_finalize",
      "celery.app.base.Celery._task_from_fun"
    ]
  }
}
```

**为什么适合作 few-shot**：
- 这是 Type B 高频误判点：模型常忽略 `USING_EXECV` 条件分支，误答为“总是直接 `_task_from_fun`”。  
- 该题强调“decorator 分支决策 + 首跳转发”，更适合作 few-shot 教推理流程，而不是 eval 的单终点打分。  
- 与现有 B01-B04 不高重复：已有条目聚焦 `shared_task`/pending/finalize；本题核心是 `@app.task` 的运行时分支改道。  

---

## Few-shot C04：`celery.chord` 的再导出 + 兼容别名链

**问题**：顶层 `celery.chord` 最终落到 `celery.canvas` 中哪个真实类定义，而不是停在兼容别名符号名上？

**环境前置条件**：
1. 使用当前 Celery 源码快照（`b8f85213f45c937670a6a6806ce55326a0eb537f`）。  
2. 按正常导入路径访问顶层 `celery.chord`。  

**推理过程（>=4步）**：
1. `celery/__init__.py` 通过 `local.recreate_module` 把顶层 `chord` 懒导出到 `celery.canvas`。  
2. 在 `celery.canvas` 中，公开名 `chord` 不是独立定义的新类，而是兼容别名赋值：`chord = _chord`。  
3. 真正类定义位置是 `class _chord(Signature): ...`。  
4. 因此顶层 `celery.chord` 的“真实定义落点”应追到 `celery.canvas._chord`，而不仅是别名名义上的 `celery.canvas.chord`。  
5. 这类链路是“顶层再导出 + 模块内 back-compat alias”的两段式路径。  

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "celery.canvas._chord"
    ],
    "indirect_deps": [
      "celery.canvas.chord",
      "celery.local.recreate_module"
    ],
    "implicit_deps": []
  }
}
```

**为什么适合作 few-shot**：
- 这是 Type C 典型断链点：模型容易停在公开别名 `chord`，不继续追到真实定义 `_chord`。  
- 题目强调“再导出 + 别名”组合模式，适合作为 few-shot 迁移模板。  
- 与现有 C01/C02/C03 不高重复：它覆盖的是 canvas 内部 back-compat alias，不是 Celery/bugreport/subtask 路径。  

---

## Few-shot C05：`celery.uuid` 的跨模块再导出链

**问题**：顶层 `celery.uuid` 最终解析到哪个真实函数符号（跨到 `celery.utils` 之外的提供者）？

**环境前置条件**：
1. 正常导入顶层 `celery` 包。  
2. 不对 `celery.utils` 做本地 monkey patch。  

**推理过程（>=4步）**：
1. `celery/__init__.py` 的 `recreate_module` 将顶层 `uuid` 映射到 `celery.utils` 模块下的同名符号。  
2. `celery/utils/__init__.py` 并未在本地实现 `uuid`，而是 `from kombu.utils.uuid import uuid`。  
3. 因此 `celery.utils.uuid` 本身是一次转发引用。  
4. 顶层 `celery.uuid` 继续沿该转发链，最终真实提供者落到 `kombu.utils.uuid.uuid`。  
5. 这是“顶层懒再导出 + 子模块二次再导出（跨包）”的复合链路。  

**标准答案**：
```json
{
  "ground_truth": {
    "direct_deps": [
      "kombu.utils.uuid.uuid"
    ],
    "indirect_deps": [
      "celery.utils.uuid",
      "celery.local.recreate_module"
    ],
    "implicit_deps": []
  }
}
```

**为什么适合作 few-shot**：
- 这是 bad case 高频模式之一：模型常在 `celery.utils.uuid` 提前停步，漏掉跨包最终提供者。  
- 更适合 few-shot 训练“追到真实定义”的习惯，而不是 eval 的单点记忆题。  
- 与当前正式 few-shot 主题区分明显（未与 B01-B04、C01-C03、D/E/A 已有条目高重复）。  

