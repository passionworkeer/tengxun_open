# Review Round 4 Arbitration

本文件只处理 3 个分歧项。仲裁标准仍以 `docs/drafts/review_round1.md`、`docs/dataset_schema.md` 和当前 `external/celery/` 源码为准，不替任一路 reviewer 圆场。

## Arbitration Item
- target: `E:\desktop\tengxun\docs\drafts\eval_easy_medium_round1.md / medium_006`
- round2 position: `pass`
- challenge reviewer position: `hold`
- final_arbitration: `keep`
- disagreement_focus:
  - Round 2 认为该题的问题单一，目标是“最终解析并实例化的 backend 类”，因此 `celery.backends.rpc.RPCBackend` 作为 `direct_deps` 足够稳定；`_get_backend -> by_url -> by_name -> symbol_by_name` 放在间接链即可。
  - Challenge reviewer 认为 `Celery._get_backend` 才是“真实触发实例化”的调用点，若 `direct_deps` 只写最终类，字段分层就不完整；同时质疑它与 `medium_001` 太像、`implicit_level=3` 偏高。
- arbitration_reasoning:
  - 挑战 reviewer 对“触发点”提出了一个可讨论视角，但不足以阻断集成。该题题面明确问的是 “最终解析并实例化的 backend 类是什么”，不是“哪个方法触发了实例化”。在这个问法下，把最终类 `celery.backends.rpc.RPCBackend` 作为 `direct_deps`，把 `_get_backend`、`by_url`、`by_name` 作为 `indirect_deps`，是与 schema 兼容的。
  - 源码链条是闭合的：`Celery._get_backend` 调 `backends.by_url(...)`，`by_url` 从 `rpc://` 抽出 scheme `rpc`，再进 `by_name` 查 `BACKEND_ALIASES['rpc']`，最后经 `symbol_by_name` 得到 `celery.backends.rpc.RPCBackend`。最终答案没有歧义。
  - “与 `medium_001` 重叠”这条 objection 也不够强。`medium_001` 的入口是 `by_name('redis')`，本条的入口是 `_get_backend` 下的 URL-scheme 路径，错误模式不同：前者是静态 alias 查表，后者多了 URL 解析这一步。
  - `implicit_level=3` 没有明显越界。该题包含 URL scheme 解析、alias 映射、字符串到类对象解析三层，不是纯一跳 alias。
- why_challenge_objection_not_blocking:
  - challenge reviewer 指出的不是事实错误，而是另一种字段分层偏好。当前写法不影响答案唯一性、证据链闭合性和可复核性，因此不足以阻断集成。
- integration_note:
  - 可原样先集成，无需因为 challenge reviewer 的 hold 暂停。

## Arbitration Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_013`
- round2 position: `pass`
- challenge reviewer position: `hold`
- final_arbitration: `repair`
- disagreement_focus:
  - Round 2 认为题面问的是“哪个关键方法触发 finalize 并执行回调链”，因此将 `celery.app.base.Celery.finalize` 作为 `direct_deps` 是自洽的；`_announce_app_finalized` 和 `_task_from_fun` 分别作为后续链路。
  - Challenge reviewer 认为真正的首次触发点是 `app.tasks` 属性访问，因为 `task_by_cons()` 先访问 `app.tasks[...]`，而 `tasks` 属性内部才调用 `self.finalize(auto=True)`；因此当前题面和 `direct_deps` 之间存在口径偏移。
- arbitration_reasoning:
  - 挑战 reviewer 这次抓到了真正的稳定性问题。源码里 `shared_task` 返回的 `Proxy(task_by_cons)` 在第一次求值时，先运行 `task_by_cons()`，再访问 `app.tasks[...]`；而 `Celery.tasks` 这个 `cached_property` 内部才执行 `self.finalize(auto=True)`。所以“触发 finalize”与“执行 finalize 逻辑”的确是两个相邻但不同的节点。
  - Round 2 的 `pass` 并非事实判断错误，因为 `finalize` 确实是执行 callback chain 的关键方法；但 challenge reviewer 指出的问题在于题面用了“触发 finalize”的表述，这会让 `Celery.tasks` 与 `Celery.finalize` 都变成可辩护答案。这个歧义足以阻止原样集成。
  - 不需要 drop。该题的核心价值仍然成立：`Proxy` 首次求值、`tasks` 自动 finalize、shared task finalize 回调、`_task_from_fun` 注册，这是一条真实的 hard 链。
  - `implicit_level=5` 虽然略偏保守，但不构成阻断项；真正要修的是题面与 direct/indirect 的边界。
- minimal_required_fix:
  - 二选一修法，选一种即可：
  - 修法 A：保留 `direct_deps = celery.app.base.Celery.finalize`，把题面改成“最终由哪个关键方法执行 finalize 逻辑并跑 shared-task 回调链”。
  - 修法 B：保留原题“触发 finalize”的说法，但把 `celery.app.base.Celery.tasks` 提升为 `direct_deps`，将 `Celery.finalize` 下放到 `indirect_deps`。
  - 同时在 `reasoning_hint` 里补一句：`task_by_cons()` 先访问 `app.tasks[...]`，而 `tasks` 属性内部调用 `self.finalize(auto=True)`。

## Arbitration Item
- target: `E:\desktop\tengxun\docs\drafts\eval_hard_round1.md / celery_hard_017`
- round2 position: `hold`
- challenge reviewer position: `pass`
- final_arbitration: `repair`
- disagreement_focus:
  - Round 2 认为这条链本质上只是 `BUILTIN_FIXUPS` 常量中的字符串 `'celery.fixups.django:fixup'` 经一次 `symbol_by_name` 解析成函数对象，复杂度更像 `medium`；此外 `implicit_deps` 混入 `DjangoFixup.install`，把“解析到哪个函数”与“后续执行副作用”混在了一起。
  - Challenge reviewer 认为 direct/indirect 分层已经成立，字符串入口最终解析到 `celery.fixups.django.fixup` 的事实清晰，因此可以 `pass`。
- arbitration_reasoning:
  - Challenge reviewer 对“事实是否正确”的判断没错，这条样本不是错样本；但 Round 2 对“是否适合作为当前 hard 样本原样入库”的保守判断更有说服力。
  - 题面明确问的是“builtin_fixups 字符串入口最终解析到哪个真实函数”。若按这个问题，最终唯一答案确实是 `celery.fixups.django.fixup`。问题不在答案错，而在两个工程口径问题：
  - 第一，当前 `implicit_deps` 写了 `celery.fixups.django.DjangoFixup.install`，这不是回答“解析到哪个函数”所必需的依赖，属于把解析后的副作用链混进答案结构。
  - 第二，`difficulty=hard` 与 `implicit_level=4` 偏高。当前链主要是 `BUILTIN_FIXUPS -> Celery.__init__ -> symbol_by_name -> celery.fixups.django.fixup`，虽然属于动态字符串入口，但复杂度没有达到本轮 hard 桶里其他题目的水平。
  - 因此它不该 `drop`，因为题材有效、答案稳定、也有区分度；但也不该按 challenge reviewer 的意见原样 `pass`。
- minimal_required_fix:
  - 保留该题，但降级为 `medium`，并把 `implicit_level` 下调到与一层字符串解析相匹配的范围。
  - 删除 `implicit_deps` 中的 `celery.fixups.django.DjangoFixup.install`，避免把后续副作用混进主答案。
  - 如果作者坚持保留 `hard`，则必须改题，不再问“解析到哪个函数”，而改问“该字符串入口在 app 初始化时最终触发哪条安装路径”，并重写依赖拆分。

## Arbitration Summary
- `medium_006`: `keep`
- `celery_hard_013`: `repair`
- `celery_hard_017`: `repair`

## Integration Guidance
- 可以直接进入集成：`medium_006`
- 修完再集成：`celery_hard_013`, `celery_hard_017`
- 本轮无须 `drop` 的条目，但 `celery_hard_013` 和 `celery_hard_017` 都不能按原稿直接放行
