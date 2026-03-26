# Review Round 2 Findings

本轮按 `docs/drafts/review_round1.md` 的严格标准执行：优先打击 FQN 不精确、证据链跳步、样本重复、难度误判、few-shot 泄漏、不可复核。以下结论默认从严，不替作者补台。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / easy_005`
- verdict: `hold`
- reasons:
  - `ground_truth.direct_deps` 给的是 `celery._state.current_app`，但该符号本身是 `Proxy(get_current_app)`；题面却写“最终对应到哪个真实符号”，会把“Proxy 符号本身”与“Proxy 背后的取值入口”混成两个合理答案。
  - schema 明确要求 `ground_truth` 不应停在中间跳板。当前写法如果想保留 `celery._state.current_app`，题目就不能再用“真实”措辞。
  - 证据链能复核，但问法和答案口径不一致，当前不能直接入集。
- required_fix:
  - 二选一：要么把问题改成“顶层 `celery.current_app` 重导出到哪个 backing proxy 符号”；要么把目标改成 `celery._state.get_current_app`，明确问“该 Proxy 背后的取值入口函数”。
  - 删除题面里的“真实”字样，显式标注这是 `Proxy` 场景。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / easy_006`
- verdict: `hold`
- reasons:
  - 和 `easy_005` 是同型问题：`celery._state.current_task` 也是 `Proxy(get_current_task)`，当前题面没有说明到底要答 Proxy 符号、取值函数，还是运行时返回对象。
  - `ground_truth.direct_deps` 与 `indirect_deps` 的边界不稳定。若评分器按“最终真实目标”理解，`current_task` 就会被视为中间层。
  - 该条可复核，但现在的问法会制造无谓歧义。
- required_fix:
  - 明确问题是在问“顶层 alias 最终落到哪个 Proxy 符号”，还是“该 Proxy 调用哪个函数取当前 task”。
  - 若保留当前答案，题面必须显式写出 “Proxy 符号”。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / easy_007`
- verdict: `pass`
- reasons:
  - 问题单一，`celery.Task -> celery.app.task.Task` 的再导出链闭合清楚。
  - FQN 精确，证据链没有把中间跳板误写成最终目标。
  - 难度与 `easy` 匹配，和现有 `easy_001` 不同但仍在同一稳定类型内。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / easy_008`
- verdict: `hold`
- reasons:
  - `celery.group` 对应的是 `celery.canvas.group` 这个类定义，但题面写“最终映射到哪个真实实现”，容易被理解成 `group(...)` 调用后的运行时对象，而不是顶层符号定义。
  - `ground_truth.indirect_deps` 填了 `celery.canvas.Signature`，这对回答“顶层 alias 指到哪个符号”并非必要依赖，属于把继承背景混进主答案。
  - 作者自审已经承认“类定义 vs 调用入口”存在口径摇摆，这说明当前版本不够稳。
- required_fix:
  - 把问题改成“顶层符号 `celery.group` 指向哪个类定义”。
  - 删掉 `Signature` 这类非必要依赖，避免评分边界漂移。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / medium_005`
- verdict: `pass`
- reasons:
  - 该条不是简单 alias，而是 `Celery.loader` 默认分支、字符串 loader、实例化三步闭环，和现有 `medium_002` 的直接 `get_loader_cls('app')` 不同。
  - `direct_deps`、`indirect_deps`、`implicit_deps` 的拆分合理，`AppLoader` 作为最终类目标稳定。
  - 难度与 `medium` 相符，没有硬拗成 `hard`。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / medium_006`
- verdict: `pass`
- reasons:
  - `rpc://...` 通过 `_get_backend -> by_url -> by_name -> symbol_by_name` 收敛到 `celery.backends.rpc.RPCBackend`，链路完整。
  - 与现有 `medium_001` 的差异成立：现有样本是直接 alias，本条是 URL-scheme 入口。
  - 题面单一，FQN 精确，可复核性足够。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / medium_007`
- verdict: `hold`
- reasons:
  - `Celery.Worker` 实际返回的是 `subclass_with_self(...)` 动态构造出的 app-bound 子类，不是裸的 `celery.apps.worker.Worker`；当前答案只给基类，和“最终解析结果”不是同一个对象。
  - 题面写“底层基类指向哪个真实类”，这和 schema 里通常追求“最终目标 FQN”的口径不一致，存在两个都说得通的答案。
  - 作者自审已明确承认“如果评测口径把动态生成类本身也当目标，会有偏差”，这条不能直接放过。
- required_fix:
  - 如果要问基类，就把问题明确收窄到“传给 `symbol_by_name` 的原始类字符串最终解析到哪个类”。
  - 如果要问返回对象，就不能再用 `celery.apps.worker.Worker` 作为最终答案，需单独描述动态子类语义。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / medium_008`
- verdict: `pass`
- reasons:
  - `Task.Strategy` 字符串经 `instantiate -> symbol_by_name` 解析到 `celery.worker.strategy.default`，链条清楚。
  - 与现有 `hard_004` 不重复：`hard_004` 问的是 `task.Request`，本条问的是 `Task.Strategy` 本身。
  - 难度判定为 `medium` 合理。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_013`
- verdict: `pass`
- reasons:
  - 这是标准的 Type B 隐式链：`Proxy` 首次取值触发 `app.tasks`，`tasks` 自动 `finalize(auto=True)`，再由 finalize 跑回调链。
  - 题目问的是“关键触发方法”，不是“最终任务对象”，当前把 `Celery.finalize` 作为直接目标是自洽的。
  - 运行时副作用、延迟注册、跨文件链路都成立，`hard` 成立。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_014`
- verdict: `pass`
- reasons:
  - 问题单一：内置任务 `celery.backend_cleanup` 最终由谁实际创建 Task 实例。
  - `connect_on_app_finalize -> add_backend_cleanup_task -> @app.task(..., lazy=False) -> _task_from_fun` 的链条闭合，没有把装饰器表层误当终点。
  - 难度和 failure type 对齐，复核成本低。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_015`
- verdict: `hold`
- reasons:
  - 题面问“真正触发 `_autodiscover_tasks` 执行的调用点是哪个函数”，至少有三个合理候选：`BaseLoader.init_worker`、`BaseLoader.import_default_modules`、`signals.import_modules.send`。当前答案只选了其中一个，没有封死其余解释。
  - `ground_truth.direct_deps` 填的是触发点，`indirect_deps` 却放实际被触发的 `_autodiscover_tasks`，这和其他样本“direct 是最终命中目标”的口径不一致。
  - 这不是事实错误，而是问题定义不够尖，现阶段不能直接集成。
- required_fix:
  - 明确题目到底要问“谁直接调用 signal.send”，还是“谁直接调用注册的 `starpromise` 回调”。
  - 按确定后的口径重排 `direct_deps` 和 `indirect_deps`。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_016`
- verdict: `pass`
- reasons:
  - `packages=None` 时通过 fixup 产出包名，再落到 `loader.autodiscover_tasks -> find_related_module -> importlib.import_module`，最终执行真实 import 的函数定位准确。
  - 题目明确、答案单一，没有把“包名收集函数”错认成“执行 import 的函数”。
  - 这条具备真正的 hard 特征：fixup、loader、全局函数、`importlib` 四段链。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_017`
- verdict: `hold`
- reasons:
  - 该条核心只是常量字符串 `'celery.fixups.django:fixup'` 经一次 `symbol_by_name` 解析到函数对象，复杂度更像 `medium` 的单层字符串映射，不够硬。
  - `implicit_deps` 放了 `celery.fixups.django.DjangoFixup.install`，但题目只问字符串最终解析到哪个函数；`install` 是解析后的后续副作用，不是回答该问题所必需的依赖。
  - 证据链把“解析到 fixup 函数”与“fixup 执行后会安装什么”混在一起，边界不够干净。
- required_fix:
  - 要么降级到 `medium`，并删掉与 `install` 相关的噪声依赖。
  - 要么把题目改成“该字符串入口在 app 初始化时最终触发哪条安装路径”，再保留 hard 定级。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_018`
- verdict: `hold`
- reasons:
  - 可复核前提没有闭合。题面只说“Django fixup 生效”，但这在代码里依赖 `DJANGO_SETTINGS_MODULE`、`django` 可导入、且 app 未自定义 `task_cls` 等条件；当前样本没有把这些写成可执行前提。
  - `app.Task` 返回的是动态生成的 app-bound 子类，而 `celery.contrib.django.task.DjangoTask` 只是被解析出来的基类。当前答案把“最终基类”与“最终返回类”混成一层。
  - 这类样本如果不把前提和目标类型写死，会直接伤害评分稳定性。
- required_fix:
  - 把环境前提提升到题面或 `source_note`，明确“在 `DJANGO_SETTINGS_MODULE` 存在且未自定义 `task_cls` 的条件下”。
  - 明确要问的是“解析得到的基类”还是“`app.Task` 返回的动态类”。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_019`
- verdict: `pass`
- reasons:
  - 该条不是静态 alias，而是 `_smart_import` 的双分支：先尝试按模块导入，失败后回退到 `symbol_by_name`。这正是容易幻觉的动态场景。
  - 题目聚焦“最终由谁完成符号解析”，`celery.utils.imports.symbol_by_name` 作为直接目标清晰稳定。
  - 证据链覆盖了失败回退这一关键分叉，质量合格。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_020`
- verdict: `reject`
- reasons:
  - 作为 `hard` 不成立。链条本质是 `_get_current_app` 包一层默认 app，再回到 `get_loader_cls('default') -> LOADER_ALIASES`，复杂度没有超过现有 `easy_003` 与 `medium_005` 的组合包装。
  - 新意不足。核心答案仍是 `celery.loaders.default.Loader`，只是换了一个更绕的入口，容易把 hard 桶稀释成“同题换皮”。
  - 没有延迟回调、没有多分支冲突、没有真正运行时不确定性，不符合当前 hard 桶校准标准。
- required_fix:
  - 不要微修。直接换题，补一个真正依赖回调/动态加载/多分支收敛的 hard 样本。
  - 若坚持保留当前链路，只能降级到 `medium`，不能占 hard 名额。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot B02`
- verdict: `reject`
- reasons:
  - 最终答案仍是 `celery.app.base.Celery._task_from_fun`，主链与正式 eval 的 `hard_001`、`hard_002` 高度重合，只是叠加了 `shared=True`、`lazy=True` 细节；这属于 few-shot 泄漏高风险。
  - 一个 few-shot 同时塞入 finalize 回调链和 pending `PromiseProxy` 链，信息量大但不聚焦，容易把模型训练成“见到 task decorator 就盲答 `_task_from_fun`”。
  - 当前 few-shot 配额本来就缺 Type A / Type D，再拿一个名额去覆盖已被 eval 主链占据的 Type B，不值。
- required_fix:
  - 直接换题，改成一个不以 `_task_from_fun` 为终点的 Type B 例子。
  - 如果保留 `@app.task` 场景，必须选一个和现有 eval 不同的最终目标与推理主链。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot B03`
- verdict: `hold`
- reasons:
  - 结构上是完整的，但如果 `celery_hard_014` 被收进正式 eval，这条就会形成直接泄漏：同一个 built-in 任务、同一个 finalize 路径、同一个最终答案 `_task_from_fun`。
  - few-shot 的价值应当是校正失败模式，而不是预先喂给模型正式考题的主答案模板；当前去重风险过高。
  - 这条不是事实错误，但在样本池整体编排上不安全。
- required_fix:
  - 先与 eval hard 池做去重决策。若保留 `celery_hard_014`，本条必须更换。
  - 可改成另一个 finalize 回调链，但最终目标不能仍是 `_task_from_fun`。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot B04`
- verdict: `reject`
- reasons:
  - 题目问“Proxy 首次访问时如何定位真实任务对象”，但 `ground_truth.direct_deps` 一次给了 `get_current_app`、`gen_task_name`、`_task_from_fun` 三个目标，已经不是单一问题。
  - 这条同时复用了 `hard_001` 的 shared-task 注册链和 `celery_hard_013` 的 Proxy 首次求值链，few-shot 泄漏风险高。
  - few-shot 应该示范“如何拆歧义并锁定唯一目标”，本条反而把多个目标打包给模型背。
- required_fix:
  - 拆成两个单独示例，或重写成只问一个唯一终点的 Type B 案例。
  - 不要再围绕 `shared_task -> _task_from_fun` 这条已过度出现的主链。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot C02`
- verdict: `reject`
- reasons:
  - 这是标准低难度顶层 re-export，和现有 `easy_001`、草稿 `easy_007` 属于同一族，几乎没有 few-shot 增益。
  - 当前 few-shot 池严重缺 Type A / Type D，却又投一个 easy 级 Type C，覆盖失衡。
  - few-shot 应优先用于矫正模型常错的复杂模式，不该浪费在显式再导出直线题上。
- required_fix:
  - 直接替换成多跳 re-export、命名空间遮蔽或跨两层 `__init__.py` 的 Type C 案例。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot C03`
- verdict: `reject`
- reasons:
  - 和 `easy_005` 同样存在目标歧义：`celery.current_app`、`celery._state.current_app`、`get_current_app`、`_get_current_app` 都可能被辩成“最终入口”。
  - few-shot 不该拿一个本身就容易口径摇摆的样本去做示范，这会放大而不是修复幻觉。
  - 即便按作者当前解释，这条也只是中等难度 Proxy/re-export 题，不足以占用稀缺 few-shot 名额。
- required_fix:
  - 不建议微修，直接换成目标唯一、无 Proxy 口径漂移的 Type C 样本。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot E02`
- verdict: `hold`
- reasons:
  - FQN 不够精确。`Celery.__init__` 调用的是从 `celery.utils.imports` 引入的 `symbol_by_name`，但本条把 `kombu.utils.imports.symbol_by_name` 写成间接依赖，口径跳过了 Celery 本地调用点。
  - 与 `celery_hard_017` 是同一主链：builtin fixup 字符串 -> `symbol_by_name` -> `celery.fixups.django.fixup`。如果 hard 池采纳那条，这里就是直接泄漏。
  - 结构可用，但当前版本既有 FQN 精度问题，又有去重风险，不能直接收。
- required_fix:
  - 把依赖改成 `celery.utils.imports.symbol_by_name`，必要时在说明里补充它 re-export 自 kombu。
  - 只有在正式 eval 不收 `celery_hard_017` 时，才考虑保留；否则必须换题。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot E03`
- verdict: `reject`
- reasons:
  - 与现有 `medium_001` 和草稿 `medium_006` 主机制相同，都是 backend alias / URL scheme / `symbol_by_name` 收敛，换的只是 backend 名和 URL 写法。
  - few-shot 用这条只会教会模型“见到 backend alias 就去查 `BACKEND_ALIASES`”，而这个模式在正式 eval 已经覆盖。
  - 难度偏低，不值得占 Type E few-shot 配额。
- required_fix:
  - 更换为一个当前 eval 未覆盖的 Type E 失败模式，例如 entry points、fallback 冲突、或多阶段字符串入口解析。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / Few-shot E04`
- verdict: `hold`
- reasons:
  - 该样本的成立依赖模块导入时机：`CELERY_CUSTOM_WORKER_POOL` 必须在 `celery.concurrency` 导入前设置。当前题面只说环境变量存在，没有把 import-order 前提写死，复核不闭合。
  - `implicit_deps` 写了 `os.environ.CELERY_CUSTOM_WORKER_POOL`，这不是 Python FQN，违反当前 schema 对依赖路径的风格要求。
  - 与现有 `easy_004`、`medium_003` 的 worker pool alias 主机制高度相近，新增价值主要来自环境变量注入，必须写清前提才勉强成立。
- required_fix:
  - 把“需在导入 `celery.concurrency` 前设置环境变量”写入问题或 `source_note`。
  - 删除 `os.environ.CELERY_CUSTOM_WORKER_POOL` 这种伪 FQN，把它改成前提说明，不要塞进依赖列表。

## Batch Finding
- target: `E:\desktop\tengxun\docs\drafts\fewshot_round1.md / file-level`
- verdict: `reject`
- reasons:
  - 当前只有 8 条，离规划要求的 20 条差距过大。
  - Type A 与 Type D 完全缺席，直接违反 `docs/fewshot_examples.md` 里的覆盖配比。
  - 至少 6 条与现有或拟收录 eval 主链高度重合，few-shot 泄漏风险系统性存在，不是个别条目失手。
- required_fix:
  - 先按配比把 Type A / D 补齐，再对全量 few-shot 与 eval 池做去重。
  - few-shot 只保留“修错模式”价值明确且不泄漏正式评测答案的例子。

## 可先集成的内容
- `eval_easy_medium_round1.md`: `easy_007`, `medium_005`, `medium_006`, `medium_008`
- `eval_hard_round1.md`: `celery_hard_013`, `celery_hard_014`, `celery_hard_016`, `celery_hard_019`
- 以上 8 条可以先进入正式整合，不需要等待人工二次判读。

## 必须退回重写的内容
- `eval_easy_medium_round1.md`: `easy_005`, `easy_006`, `easy_008`, `medium_007`
- `eval_hard_round1.md`: `celery_hard_015`, `celery_hard_017`, `celery_hard_018`, `celery_hard_020`
- `fewshot_round1.md`: `Few-shot B02`, `Few-shot B03`, `Few-shot B04`, `Few-shot C02`, `Few-shot C03`, `Few-shot E02`, `Few-shot E03`, `Few-shot E04`
- 其中 `celery_hard_020`, `Few-shot B02`, `Few-shot B04`, `Few-shot C02`, `Few-shot C03`, `Few-shot E03` 属于重写优先级最高，不能靠小修补救。
