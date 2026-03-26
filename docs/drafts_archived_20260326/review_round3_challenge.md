# Review Round 3 (Challenge Path)

> 只审以下草稿，不改其他文件：  
> - `docs/drafts/eval_easy_medium_round1.md`  
> - `docs/drafts/eval_hard_round1.md`  
> - `docs/drafts/fewshot_round1.md`  
> 审核依据：`dataset_schema.md`、`fewshot_examples.md`、`review_round1.md` 以及当前 `external/celery/` 源码。

---

## Eval Easy / Medium

### easy_005
- verdict: hold  
- reasons:  
  - `ground_truth.direct_deps` 直接指向 `celery._state.current_app`（Proxy 对象），未落到可解析的最终提供者；问题问“最终对应到哪个真实符号”，更合理的 direct 应是提供实际 app 的 getter 结果。  
  - `implicit_level=2` 低估了 Proxy -> getter -> default_app 的隐式链深度，当前标注与链路复杂度不符。  
- required_fix:  
  - 把 direct/indirect 重新划分：direct 应落在实际返回对象（默认 app 或 `_get_current_app`），Proxy 可移到 implicit。  
  - 复核 implicit_level，若保留 Proxy + default fallback，建议 ≥3。

### easy_006
- verdict: hold  
- reasons:  
  - 同样把 Proxy 本身作为 direct 目标，未明确 `_task_stack.top` 才是最终值提供者，FQN 精度不足。  
  - `failure_type=Type C` 但隐式层（线程栈取值）未体现到 implicit_deps，分类与字段拆分不自洽。  
- required_fix:  
  - direct 落到最终数据提供点（例如 `_task_stack.top` 或具体函数），Proxy 放 implicit；补充隐式依赖。  
  - 重新说明 Type B/C 边界或调整 failure_type。

### easy_007
- verdict: pass  
- reasons:  
  - FQN 精确落到 `celery.app.task.Task`，问题与答案单一。  
  - 证据链闭合且不与现有 12 条重复（现有无顶层 Task 映射）。  
- required_fix: 无（可直接进入待集成队列）。

### easy_008
- verdict: hold  
- reasons:  
  - 问题问“真实实现”，当前 direct_deps 选的是类 `celery.canvas.group`，但该符号在运行时既是类又经 lazy 导出，可被视作 callable；未澄清预期形态，易与函数式入口混淆。  
  - `implicit_level=2` 但链路只有单跳再导出 + 类继承，按现有口径应为 1；难度与 implicit_level 不匹配。  
- required_fix:  
  - 明确问题文本是“类定义”或“可调用入口”，并据此调整 direct_deps/implicit_deps。  
  - 校准 implicit_level 与 difficulty，建议 easy + implicit_level=1。

### medium_005
- verdict: pass  
- reasons:  
  - 覆盖 `Celery.loader` 默认分支，direct/indirect/implicit 拆分合理，FQN 落点精确。  
  - 与已有 medium_002 在入口和链路上有实质差异（默认值决策 + 实例化），无重复冲突。  
- required_fix: 无。

### medium_006
- verdict: hold  
- reasons:  
  - 问题询问“最终解析并实例化的 backend 类”，但 indirect_deps 中仍包含 `_get_backend`，而 direct_deps 只落到最终类，缺少真正触发实例化的调用点（`_get_backend` 自身应在 direct/indirect 取舍中说明）。  
  - implicit_level=3 但实际链路为 alias 查表 + symbol_by_name，隐式深度偏低，且未写明 `result_backend` 配置来源，易与 medium_001 高度重叠。  
- required_fix:  
  - 明确 direct/indirect：可将 `_get_backend` 作为 direct 触发点，类本身为目标；或保留现状但在 reasoning_hint 解释实例化位置。  
  - 重新评估 implicit_level，并在 source_note 标注与 medium_001 的差异以避免重复。

### medium_007
- verdict: reject  
- reasons:  
  - 问题指向 “底层基类指向哪个真实类”，但 direct_deps 仅给出基类 `celery.apps.worker.Worker`，未体现 `subclass_with_self` 动态生成的新类型，FQN 与问题不一致。  
  - implicit_level=3 偏低；链路含字符串解析 + 动态 type 生成 + app 绑定，应≥4；当前链路描述不足以支撑 hard/medium 判定。  
- required_fix:  
  - 重新定义 direct 目标（应描述生成的绑定子类或明确 why 基类即最终落点），补充分支和动态生成细节。  
  - 调整 implicit_level，补充 symbol_by_name → type(...) 的关键跳步。

### medium_008
- verdict: pass  
- reasons:  
  - 对 `Task.Strategy` 字符串解析链的拆分准确，direct/indirect/implicit 自洽。  
  - 与硬样本 hard_004 聚焦点区分清楚（本题关注 Strategy 入口，hard_004 关注 Request 解析），无重复。  
- required_fix: 无。

---

## Eval Hard

### celery_hard_013
- verdict: hold  
- reasons:  
  - direct_deps 写为 `Celery.finalize`，但问题问“通过哪个关键方法触发 finalize 回调链”；真正触发点在 `tasks` 属性访问，且 `_task_from_fun` 是最终注册点，direct/implicit 分层与问题不匹配。  
  - implicit_level=5 过高；链路主要是属性触发 finalize + 回调，未涉及更深动态加载，可下调或给出额外隐式跳步说明。  
- required_fix:  
  - 重写 direct/implicit：可将 `Celery.tasks`/`finalize` 组合为 direct 触发点，`_task_from_fun` 作为目标或 indirect。  
  - 校准 implicit_level，并在 reasoning_hint 明确“首次访问 tasks 触发 finalize”这一关键跳步。

### celery_hard_014
- verdict: pass  
- reasons:  
  - 终点落在 `_task_from_fun`，与问题“最终由哪个方法创建任务实例”一致。  
- required_fix: 无。

### celery_hard_015
- verdict: hold  
- reasons:  
  - 问题问“真正触发 `_autodiscover_tasks` 的调用点”，direct_deps 却设为 `import_default_modules`，未把 `_autodiscover_tasks` 自身或信号回调放入 direct/indirect，目标与字段拆分不符。  
  - evidence chain缺少 `signals.import_modules.send` 到 `_autodiscover_tasks` 的闭合，当前链路停在 loader.init_worker。  
- required_fix:  
  - 调整 direct/indirect：可将 `_autodiscover_tasks` 设为 direct 目标，`import_default_modules` 作为 indirect 触发。  
  - 补充信号触发与 starpromise 解包的关键一步。

### celery_hard_016
- verdict: pass  
- reasons:  
  - 动态包名 -> find_related_module -> importlib 链路完整，implicit_deps 正确包含 importlib。  
- required_fix: 无。

### celery_hard_017
- verdict: pass  
- reasons:  
  - 字符串入口解析到真实函数，direct/indirect 分层合理。  
- required_fix: 无。

### celery_hard_018
- verdict: hold  
- reasons:  
  - 依赖 Django 环境前置条件（`DJANGO_SETTINGS_MODULE` 可导入、fixup 生效），未在 question/notes 明确，当前表述默认环境满足，复核性差。  
  - `implicit_deps` 只列 symbol_by_name，遗漏对环境注入和 settings 解析的依赖，隐式链不完整。  
- required_fix:  
  - 在 source_note 或 question 中明确前置条件；补充隐式依赖（环境变量 / Django settings 加载）。  
  - 说明若无 Django 环境该链不成立，以免混入正式集。

### celery_hard_019
- verdict: pass  
- reasons:  
  - 双分支（import_module 失败回退 symbol_by_name）被标出，direct 落到最终解析函数，符合问题。  
- required_fix: 无。

### celery_hard_020
- verdict: hold  
- reasons:  
  - 入口为 fallback app lazy 创建，链路主要是 alias -> symbol_by_name，复杂度更像 medium；`implicit_level=4` 与实际隐式程度不符。  
  - indirect_deps 同时包含 `_get_current_app`、`Celery.loader`、`get_loader_cls`，但 direct_deps 仅给出最终类，缺少真正触发实例化的具体节点，分层模糊。  
- required_fix:  
  - 重新校准 difficulty/implicit_level，建议降为 medium / implicit_level=3。  
  - 明确 direct/indirect：将实例化触发点（`app.loader` 访问）列为 direct 或补充 reasoning_hint 解释。

---

## Few-shot

### Few-shot B02
- verdict: hold  
- reasons:  
  - 与既有 hard_002 链路高度重叠，仅增加 pending/finalize 双路径，增益有限，存在重复风险。  
  - 输出只给 ground_truth，未明确 few-shot 期望的推理格式/口径（如是否提供任务名生成细节），难以直接放入正式库。  
- required_fix:  
  - 强调与 hard_002 的差异点（lazy/pending 双路径），在答案中显式点出 pending 队列分支。  
  - 补充清晰的 few-shot 输出示例格式（含问题+推理+答案），对齐 fewshot_examples 口径。

### Few-shot B03
- verdict: hold  
- reasons:  
  - 与 hard_002 / hard_014 主链重合（最终落点 `_task_from_fun`），差异主要在内置任务触发，需阐明新增信息以避免重复。  
  - 推理步骤未写出 `@connect_on_app_finalize` 到 `_announce_app_finalized` 的执行细节，证据链未闭合。  
- required_fix:  
  - 标清与已有样本的差异（内置任务 vs 用户任务），补上 finalize 回调执行路径。  
  - 规范 few-shot 输出格式，确保可直接放入 fewshot_examples。

### Few-shot B04
- verdict: hold  
- reasons:  
  - direct_deps 同时写了 `get_current_app` 与 `_task_from_fun`，但问题核心是 Proxy 首次解析 -> 任务名生成，缺少对 `gen_task_name` 与 tasks 查表失败/成功路径的区分。  
  - 与 hard_001 共享主链，增量信息有限；未说明“未显式 name”对任务名生成的具体影响。  
- required_fix:  
  - 把任务名生成和查表作为显式步骤写入推理，并在答案中区分 direct/indirect。  
  - 说明与 hard_001 的差异点，否则易判重复。

### Few-shot C02
- verdict: reject  
- reasons:  
  - 与 eval 样本 easy_007 问题和答案几乎一致，重复度高，难以作为 few-shot 增益。  
  - 链路过短（单跳再导出），不足以对 Type C 复杂再导出提供示范，偏 easy。  
- required_fix:  
  - 更换为多层 `__init__.py` 再导出或别名链路的示例；确保与 eval 样本区分度。  
  - 提升难度或明确 few-shot 目标（如两跳以上再导出）。

### Few-shot C03
- verdict: hold  
- reasons:  
  - 与 easy_005 主题重叠（current_app Proxy），差异度不足；难度定位偏 medium，未体现多跳隐式。  
  - implicit_deps 只写到 `_get_current_app`，未包含 default_app 初始化等运行时前提，证据链不完整。  
- required_fix:  
  - 补充 default_app 初始化与线程局部栈的依赖，完善 implicit 部分。  
  - 明确与 eval 样本的差异或更换为多层再导出链路示例。

### Few-shot E02
- verdict: hold  
- reasons:  
  - `symbol_by_name` 实际来源为 `celery.utils.imports`，答案写成 `kombu.utils.imports`，FQN 精度有误。  
  - 未说明 fixup 执行的前置条件与返回对象（DjangoFixup.install），对抗 Type E 的“字符串入口 → 函数执行”机理描述不足。  
- required_fix:  
  - 修正 FQN 到 `celery.utils.imports.symbol_by_name` 并补充调用栈，注明返回对象。  
  - 在 reasoning 中强调“字符串解析后立即执行”的隐式跳步。

### Few-shot E03
- verdict: hold  
- reasons:  
  - 与现有 medium_001/backends alias 机制高度相似，仅增加 `+` 拆分，增益有限，易判重复。  
  - 答案未体现 `by_url` 返回 `(cls, url)` 二元组的细节，直接落到类，容易误导模型忽视 URL 改写。  
- required_fix:  
  - 补充 `by_url` 拆分和返回值细节，强调与 `by_name` 的区别。  
  - 说明与 medium_001 的差异或选取不重复的 backend 场景。

### Few-shot E04
- verdict: hold  
- reasons:  
  - 依赖环境变量注入 alias，未在问题或答案中明确“必须预设 env”这一前置；可复核性不足。  
  - implicit_deps 仅列环境变量本身，缺少模块导入时机（`celery.concurrency.__init__`）这一关键隐式节点。  
- required_fix:  
  - 在问题或答案中写明环境变量前置，并把模块导入时机加入 implicit。  
  - 说明如果未设置 env 链路不成立，避免误导 few-shot。

---

## 系统性风险（若直接集成）
- 多条样本/示例与现有 12 条或彼此高度重复（`celery.Task` 再导出、shared_task/_task_from_fun、backend alias by_url），会降低评测/提示的区分度。  
- 多处 direct/indirect/implicit 划分不清（尤其 Proxy 场景、autodiscover、subclass_with_self），若直接入库会导致模型在评测时被“中间节点”打分，偏离 schema 定义的“最终目标”。  
- 难度与 implicit_level 多处偏移（把短链标成 hard 或 implicit_level 过高/过低），会破坏难度分布和后续指标。  
- 若不补充环境/前置条件（Django fixup、env 注入 alias），正式集可能包含不可复核样本，影响稳定性。
