# Review Round 17 - Eval Round 4 Findings

本轮按以下门槛审稿：

- `E:\desktop\tengxun\docs\drafts\review_round16_eval_round4_gate.md`
- `E:\desktop\tengxun\docs\drafts\review_round15_formal_pool_safety.md`
- `E:\desktop\tengxun\docs\dataset_schema.md`

默认立场仍然是 strict reviewer 口径：

- 不替作者脑补前提
- 不把值语义硬塞进 FQN 判题结构
- 不因“题目方向不错”而放松 `Type A / Type D / hard` 的门槛

---

## Global Findings

### Global-01
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md` + `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md`
- verdict: `hold`
- reasons:
  - 两份草案直接复用了同一组 ID：`celery_hard_021`、`celery_hard_022`、`celery_hard_023`。`dataset_schema.md` 明确要求 `id` 全局唯一，这不是小瑕疵，是 formal pool 阶段的硬门槛。
  - 两份文件标题都写成 `EVAL-021`，会继续放大追踪混乱，后续 reviewer、annotator、数据合并脚本都容易串号。
- required_fix:
  - 在进入正式池前，对 6 条草案全部重新编号，保证全局唯一。
  - 文件级批次编号也要拆开，不要继续共用 `EVAL-021`。

### Global-02
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md` + `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md`
- verdict: `hold`
- reasons:
  - 本轮 round 4 明确优先 `Type A / Type D / hard`，但多条草案在“收缩为单问单判”的过程中，把原本高价值的运行时/生命周期问题缩成了局部 helper 题，导致 failure type 与 difficulty 标签失真。
  - 这不是个别题目的问题，而是两份草案共同存在的收缩过头风险：题目变稳了，但也变浅了。
- required_fix:
  - 每条题在进入 formal pool 前，补一条自检说明：为什么它仍然是 `Type A / Type D / hard`，而不是普通 medium helper tracing。

---

## File Review

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_021`
- verdict: `hold`
- reasons:
  - `id` 与另一份草案中的 `celery_hard_021` 冲突，当前不能直接入池。
  - 题目已经收缩成单问单判，这是对的，但现在更像“单文件异常分支定位题”，不再符合 `review_round16_eval_round4_gate.md` 对 `Type A` 的定义。它没有真实的长上下文截断风险，也没有跨阶段收敛，主判断基本停留在 `Request.on_failure` 局部。
  - `hard` 也站不稳。当前链路主要是 `on_failure -> reject` 的条件分支，虽然有运行时前提，但缺少延迟触发、动态解析或多阶段收敛，按 round 4 gate 不足以单凭这一点占 hard 名额。
  - `implicit_deps` 里放 `celery.worker.request.WorkerLostError` 勉强能解释分支谓词，但这不是隐式依赖链，最多算题目条件的一部分，闭包偏松。
- required_fix:
  - 先解决 ID 冲突。
  - 若保留当前问题，不建议继续挂 `Type A / hard`；应降级并重判 `failure_type`、`difficulty`、`implicit_level`。
  - 若作者坚持 round 4 高价值定位，就必须把题目重新扩回真正的跨阶段判断点，而不是停在 `on_failure` 单函数分支。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_022`
- verdict: `accept_with_fix`
- reasons:
  - 单问单判成立，且成功把“吞掉还是重抛”这种值语义问题收缩成“真正做判定的函数是谁”，符合 `review_round15_formal_pool_safety.md` 的 gate。
  - `direct_deps = celery.loaders.base.find_related_module` 是稳定终点，问题与答案口径一致。
  - 这条确实具备 round 4 想要的 `Type A / hard` 特征：`force=False` 的延迟注册、`signals.import_modules`、loader 链、真正 import 错误判定点，截断任何一层都容易答错。
  - 主要缺点不是链错，而是编号冲突，以及 `indirect_deps` 还可以再收紧或补齐为更稳定的最小闭包。
- required_fix:
  - 先解决 ID 冲突。
  - 在 `indirect_deps` 中补清楚 `celery.loaders.base.BaseLoader.autodiscover_tasks` 这一层，或者在 `reasoning_hint` 明说为何可直接从 loader 级 `autodiscover_tasks` 跳到全局 `find_related_module`。
  - 保持题面不要把触发者写死成 worker 路径；当前问题文本已经避免了这个坑，后续不要再回退。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_023`
- verdict: `reject`
- reasons:
  - `id` 与另一份草案中的 `celery_hard_023` 冲突。
  - 题目过度收缩后已经失去 round 4 高价值形态。当前只是 `Blueprint.apply -> step.include -> _should_include -> include_if` 的局部调用题，没有真实的长上下文截断风险，不符合 `Type A`。
  - `hard` 明显虚高。没有运行时前提、没有延迟触发、没有动态解析、没有多阶段收敛，只是同文件内部调用关系。
  - `direct/indirect/implicit` 也不够干净。问题问“谁决定不把 step 挂进 `parent.steps`”，那 decisive node 是 `StartStopStep.include`；`Blueprint.apply` 是显式调用者，不应被当作 `implicit_deps`。
  - 它保留了“单问单判”，但牺牲了 round 4 题目应有的区分度，继续修字段已经没有意义。
- required_fix:
  - 不建议微修当前版本。
  - 直接重写 bootstep 题，重新围绕真正的生命周期断点出题，例如“实例化发生了没有”“依赖展开发生了没有”“include gate 对 create/挂载的边界是什么”，但一次只问一个判断点。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_021`
- verdict: `reject`
- reasons:
  - `id` 与另一份草案中的 `celery_hard_021` 冲突。
  - `failure_type = Type D` 不成立。题目没有真实命名空间冲突、没有同名竞争对象、没有 lookup key 歧义，只是在问 `Scheduler.tick` 中发送前先推进状态的方法是谁。
  - `hard` 也不成立。核心链路几乎停留在 `tick -> reserve -> _next_instance`，是局部 helper tracing，不是 round 4 gate 要的高价值 hard。
  - `source_note` 还带入了“advance before execute”的设计意图注释，但题目本身并不判设计意图；这会诱导作者把行为/后果题重新塞回来。
- required_fix:
  - 不建议把这条继续留在 round 4 Type A/D 池里。
  - 若要保留这个素材，只能改造成普通 medium helper 题，并改掉 `failure_type`、`difficulty`、`id`；否则直接丢弃。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_022`
- verdict: `accept_with_fix`
- reasons:
  - `id` 与另一份草案中的 `celery_hard_022` 冲突。
  - 单问单判成立，值语义没有越界。题目没有再问“会清掉哪些 schedule”“后续 merge 怎么办”，而是收缩到“谁直接触发 clear”，这点是合格的。
  - 这条比 set1 的 `celery_hard_023` 更像真正的 `Type A`：它明确限制在启动阶段、持久化 store 缺失元数据、追到 `_create_schedule` 的 reset 分支，存在阶段性断点。
  - 主要风险在于同文件里还有别的 `clear()` 路径，例如后面的 timezone / utc change reset；虽然题面写了“缺失 `utc_enabled` 元数据”，但 `reasoning_hint` 还应更主动地排除这些近邻竞争分支。
- required_fix:
  - 先解决 ID 冲突。
  - 在 `reasoning_hint` 或 `source_note` 中显式排除 `setup_schedule` 里“值变化导致 clear”的另外两条 reset 分支，避免 reviewer/标注员把相邻 `clear()` 误判成同一答案。

## Review Item
- target: `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_023`
- verdict: `hold`
- reasons:
  - `id` 与另一份草案中的 `celery_hard_023` 冲突。
  - 题目方向是对的，具备 round 4 需要的运行时风险：CLI/config 前提、Redis broker 限制、consumer bootstep 启动、运行时 monkey-patch `channel_qos.can_consume`。这条链有资格做 `Type A / hard`。
  - 但当前最小闭包没收紧。题目问的是“真正改写 `can_consume` 的方法是谁”，那 `direct_deps = celery.worker.consumer.tasks.Tasks.start` 没问题；可 `implicit_deps` 里塞 `celery.worker.state.reserved_requests` 就偏离主问题了。`reserved_requests` 只属于 patched closure 的内部实现，不是识别 rewrite 点所必需的闭包。
  - `source_file` 与 `indirect_deps` 也偏 CLI 路径，但题目本身并没有限定必须从 `--disable-prefetch` 进入；只写“`worker_disable_prefetch=True` 且 Redis”。这导致 entry 口径和题面口径不完全一致。
- required_fix:
  - 先解决 ID 冲突。
  - 二选一收口：
  - 如果题目要问“运行时真正改写 `can_consume` 的方法”，应把 entry/indirect 重点放到 `celery/worker/consumer/tasks.py`，并删掉 `reserved_requests` 这类噪声依赖。
  - 如果题目要问“从 CLI `--disable-prefetch` 到生效的端到端入口”，就必须把题面明确改成 CLI 路径题，并补足从 `worker()` 到 consumer bootstep 的中间链，而不是只写一个 `celery.bin.worker.worker`。

---

## Round 4 Risk Summary

### 可继续推进
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_022`
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_022`

### 需要修完再看
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_021`
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_023`

### 不建议继续沿当前版本打磨
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_023`
- `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_021`

---

## Most Dangerous Drafts

当前最危险的 3 条，不是“最错”，而是“最容易看起来像能进，实际上会污染 formal pool”：

1. `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_021`
   - 错把局部 helper tracing 包装成 `Type D / hard`，分类风险最大。
2. `E:\desktop\tengxun\docs\drafts\eval_round4_type_a_set1.md / celery_hard_023`
   - 过度收缩后几乎失去 round 4 高价值特征，但表面上字段很整齐，最容易误放行。
3. `E:\desktop\tengxun\docs\drafts\eval_round4_type_ad_set2.md / celery_hard_023`
   - 方向对、风险也真，但当前 entry 口径和最小闭包没收紧，最容易在“看起来很高级”的错觉下带着脏链入池。
