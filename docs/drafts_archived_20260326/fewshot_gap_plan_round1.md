## 现状缺口
- 目标配比：Type B 5、Type C 5、Type D 4、Type E 4、Type A 2（总计 20）。
- 当前正式 `docs/fewshot_examples.md` 可用条目推算：
  - Type B：4/5（缺 1）
  - Type C：3/5（缺 2）
  - Type D：0/4（缺 4）
  - Type E：3/4（缺 1）
  - Type A：0/2（缺 2）
- 关键缺口集中在 Type A（长链上下文）与 Type D（命名/空间冲突），本轮优先补这两类。

## 候选方向（不少于 6 条，A≥2，D≥4）
| 编号 | 类型 | 入口文件 | 问题骨架 | 为何适合 few-shot 而非 eval |
| --- | --- | --- | --- | --- |
| A-01 | Type A | `celery/bin/celery.py` ➜ `celery/bin/worker.py` | “CLI `celery -A proj worker` 从 main 到 Worker 启动的长链：哪些函数依次解析 app、loader、control/consumer？” | 长链多跳（CLI 入口、命令解析、App 加载、Worker 启动）；上下文重、易超长，不宜做单点 FQN eval，适合作为 CoT 案例教模型分段定位。 |
| A-02 | Type A | `celery/app/base.py` + `celery/_state.py` + `celery/local.py` | “第一次访问 `celery.current_app` 时，Proxy 触发的 auto-finalize / default_app 回填全链路是什么？” | 涉及 Proxy、default app fallback、finalize、pending task drain，多阶段状态机；作为 few-shot 可示范拆链路，避免 eval 里混淆 direct/implicit。 |
| D-01 | Type D | `celery/app/registry.py` | “`TaskRegistry.register` 遇到同名任务时谁覆盖谁？最终表项指向哪个 Task 类/实例？” | 典型命名冲突（后注册覆盖并告警），FQN 取决于导入顺序；few-shot 可教模型识别“最后 wins”模式，eval 难保复现导入顺序。 |
| D-02 | Type D | `celery/app/base.py`（`create_task_cls` / `task` 装饰器） | “未显式指定 `name` 的任务，自动生成的 `task.name` 如何避免与已有任务/模块名冲突？” | 重点在名称推导（模块.函数）、去重与覆写提示；属于命名策略而非单一符号解析，适合 few-shot 讲逻辑而非硬 FQN 断言。 |
| D-03 | Type D | `celery/worker/control.py` | “自定义 control 命令与内置同名时，control registry 如何决议最终可用的命令实现？” | 命令表基于 dict/registry，后写覆盖；需要理解注册顺序与装饰器行为，few-shot 用于示范“同名覆盖”模式。 |
| D-04 | Type D | `celery/utils/dispatch/signal.py` | “多次 connect 同一 receiver/sender 时，signal registry 如何去重或保留？最终会触发几次？” | 信号去重依赖 weakref/receiver key，属命名/标识冲突处理；适合作为 few-shot 说明“同名/同 id”合并规则，而非 eval 确定唯一 FQN。 |
| D-05（备选） | Type D | `celery/utils/imports.py` (`symbol_by_name`, `qualname`) | “同名短路径与全路径同时出现时，`symbol_by_name` 如何决定解析顺序与 fallback？” | 展示名称歧义与 fallback 规则；few-shot可示范“先假定 module path，再 fallback kombu.utils.imports”模式。 |
| A-03（备选） | Type A | `celery/canvas.py` + `celery/app/base.py` | “`chain(group(sig1, sig2))` 组合执行时，apply -> freeze -> backend 保存的长链关键节点是什么？” | 跨 canvas 组合、序列化与执行管线，链路长且依赖上下文，适合作 few-shot 的链路分解示范。 |

> 说明：已给出 A 类 2 条主力 + 1 备选，D 类 4 条主力 + 1 备选，可按需要取前 6 条或增补到 20 条总体缺口。后续具体出稿时需按 `fewshot_examples` 结构补全 question / ground_truth / reasoning。 
