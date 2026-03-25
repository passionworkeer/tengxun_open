# Review Round 16 - Eval Round 4 Gate

本文件只定义 `round 4 高价值 eval` 的审稿门槛，不对尚未成稿的具体题逐条裁决。目标是提前拦截前几轮已经反复出现的脏链、双问、值语义越界、运行时前提未封口等问题，尤其针对 `Type A / Type D / hard`。

---

## Scope

本轮 gate 只面向以下类型的候选题：

- 优先覆盖 `Type A`
- 补强 `Type D`
- 严格校准 `hard`
- 避免继续堆简单 alias / 单跳 re-export

本轮默认立场：

- 宁可少收，不收口径摇摆题
- 宁可 `hold` 等作者补前提，不把运行时猜测混进正式池
- 不允许把 schema 不能稳定表达的“值语义 / 顺序语义 / 次数语义”硬塞进 FQN 判题结构

---

## Round 4 Gate Verdicts

### 必须 `reject`

出现以下任一情况，直接退回，不进入 formal eval 起草：

1. 题目不是单问单判
   - 同时问“最终是谁”与“为什么”与“何时发生”与“会不会再发生”
   - 同时问 FQN 和值结果
   - 同时问多个异常分支 / 多个配置分支，但只允许一个 ground truth 结构

2. 答案无法稳定落到当前 schema
   - 真正要回答的是次数、顺序、布尔条件组合、返回值 payload、状态转移矩阵
   - 需要表达“先 A 后 B”“可能 A 或 B”“返回 tuple 第二项”等值语义，但 `ground_truth` 只能稳定承载 FQN
   - 题干本质是行为解释题、设计意图题、后果题，而不是可稳定落到依赖链终点的依赖解析题

3. 最小闭包不成立
   - `ground_truth` 混入不参与判题的 side effects
   - 把中间跳板、便利 wrapper、缓存属性、装饰器表层当作最终目标
   - 需要 5 个节点才能闭环，却只写了 2 个“猜得出来”的节点

4. 运行时前提没封口
   - 依赖 env、feature flag、Django settings、模块导入时机、weakref/GC、broker capability、native delayed delivery、acks 配置，却没写成可复核前提
   - 不同入口都能触发同一行为，但题面把某个触发者写死
   - 依赖测试上下文或 monkeypatch 才成立，却未转写成源码前提

5. `hard` 只是“绕”，不是“硬”
   - 本质仍是一跳 alias / 一层字符串解析 / 简单重导出，只是入口写得更远
   - 没有运行时副作用、没有延迟触发、没有多层动态收敛、没有分支闭合，却强标 `hard`

6. `Type D` 其实不是命名空间歧义
   - 实际没有同名竞争目标、局部遮蔽、helper 误认、lookup key 冲突
   - 只是普通 helper tracing，却硬贴 `Type D`

7. `Type A` 其实不是长上下文风险
   - 题目只是单文件短链
   - 不需要跨文件拼接、跨阶段追踪、跨 runtime 前提收束
   - 只是“看起来长”但没有真实断点风险

---

### 必须 `hold`

以下情况先挂起，补最小信息后可再审：

1. 题目方向对，但题干边界不够尖
   - “触发点”与“最终执行点”混用
   - “最终类”与“动态生成类的基类”混用
   - “符号定义”与“运行时取值入口”混用

2. `ground_truth` 主体正确，但 direct / indirect / implicit 拆分不稳
   - direct 写成触发点，问题却在问最终目标
   - implicit 放入其实属于 direct 的关键节点
   - 把环境前提误写成 FQN

3. 候选题依赖值语义，但可以收缩成 FQN 题
   - 例如“哪些错误会被吞、哪些会重抛”这类矩阵题
   - 若能收缩为“真正做分类 / 决策的关键函数是哪一个”，可 `hold`
   - 若不能收缩，转 `reject`

4. `hard` 候选链路真实存在，但题面尚未把运行时约束写死
   - 例如导入时机、acks 开关、broker 能力、scheduler 启动阶段、worker/CLI 双入口
   - 这种题不能原样过，但也不必直接扔掉

5. `Type D` 候选存在歧义源，但歧义对象未限定
   - 需要先明确“究竟在辨认哪个同名对象 / lookup key / helper”
   - 否则模型会答对思路、答错口径

6. 证据链基本成立，但最小闭包仍多一层噪声
   - 典型表现：把 `install()`、`sync()`、`mark_as_failure()` 这类后效链混进主答案
   - 这类题可保留，先收紧闭包再说

---

### 可 `accept_with_fix`

出现以下情况，可以带修进入下一轮正式起草：

1. 主问题单一，最终目标唯一，证据链闭合，只差题面措辞校准
   - 例如把“最终真实实现”改成“最终解析到的类定义”
   - 例如把“谁触发”改成“谁执行”

2. 依赖链正确，只差前提显式化
   - 把 `acks_late=True`
   - 把 `DJANGO_SETTINGS_MODULE` 已配置
   - 把“在导入模块前已设置 env”
   - 把“在 scheduler 启动重建阶段，不是运行期 sync”
   写进题干或 `source_note`

3. `hard` 判定成立，但 `implicit_level` 偏 1 档
   - 允许边写边修，不阻断入池
   - 前提是不会影响题目唯一性和复核性

4. `Type A` / `Type D` 方向正确，但题目仍夹杂一个可删的值语义尾巴
   - 可以删尾巴保留主链
   - 不允许保留双问结构硬过

---

## Core Gate Checks

以下检查适用于 round 4 所有候选题。

### 1. 单问单判

必须同时满足：

- 题干只问一个核心判断点
- `ground_truth` 只承载一个稳定终点或一个稳定最小闭包
- 不把“对象是谁”和“对象为什么这样”和“对象后果如何”捆成一题

一旦需要出现“分别”“哪些”“何时会/何时不会”“A 和 B 各怎样”，默认先判高风险。若无法收缩成单点问题，直接 `reject`。

### 2. 最小闭包

`ground_truth` 只能保留判题必需的最小闭包：

- `direct_deps`: 题目真正命中的最终目标
- `indirect_deps`: 为了到达 direct 不可缺的中间节点
- `implicit_deps`: 延迟触发、动态解析、导入时副作用、信号/回调/环境前提对应的稳定依赖

禁止：

- 把后续 side effects 混进主答案
- 把测试辅助、日志、无关 helper 塞进闭包
- 用“多写几个总没错”的方式掩盖边界不清

### 3. FQN 与值语义分离

本轮尤其要卡死这一点。

可以收：

- “哪个函数负责做决定”
- “哪个类最终被解析出来”
- “哪个 helper 参与 lookup key 生成”

不能直接收：

- “哪些异常分别会 ack / reject / mark_as_failure”
- “会不会漏发一次 / 会不会重试”
- “哪个字段会保留、哪个会覆盖”
- “为什么先 reserve 再 send，后果是什么”

这类题若不能重写为“关键决策函数 / 稳定实现节点”，直接 `reject`。

---

## Type A Gate

`Type A` 在 round 4 里是高价值，但也最容易写坏。

### Type A 必须满足

1. 真有长链断点风险
   - 至少跨两层以上阶段或语义切换
   - 例如：入口 API -> signal/registry -> loader/runtime -> 真正实现

2. 真有“截断就会错”的关键跳步
   - 漏掉某一层就会把触发点误当终点
   - 漏掉某一层就会把配置入口误当运行时行为

3. 题面必须先把前提钉死
   - 启动阶段还是运行阶段
   - worker 入口还是 CLI 入口
   - 哪些配置已开启
   - 是否存在 broker / scheduler / env 假设

### Type A 必须 `reject`

- 题面实质在问行为矩阵或设计后果
- 需要同时回答多条分支路径
- 真相依赖测试 case 才补得齐，源码本身不足以封闭

### Type A 可 `accept_with_fix`

- 链路很强，但题干仍带一个“后果解释”尾巴
- 只要把题目收缩到“真正做决策的关键节点是谁”，即可放行

---

## Type D Gate

`Type D` 不允许空喊“命名空间风险”，必须给出真实歧义源。

### Type D 必须满足

1. 存在至少两个合理竞争对象
   - 同名函数 / 类
   - wrapper 与 original function
   - lookup key 与 receiver object
   - route 参数与 route 配置

2. 题目必须明确在判哪个名字空间层
   - 符号名
   - lookup key
   - helper 决策点
   - route merge 结果归属

3. 证据链必须说明“为什么不是另一个同名对象”
   - 不能只追到目标，还要排除最像的错误答案

### Type D 必须 `reject`

- 题目没有真正竞争对象，只是普通 tracing
- 需要回答的是 merge 后的值结果，而不是 merge 使用的关键 helper / lookup 规则
- 同时问“谁覆盖谁”和“为什么 None 不清空值”，这是双问

### Type D 可 `accept_with_fix`

- 候选题有真实歧义，但题干未明确在问 helper、lookup key 还是最终对象
- 把口径写死后可继续

---

## Hard Gate

round 4 明确要优先 `hard`，所以 hard 门槛必须更高。

### `hard` 必须满足

至少满足以下两项：

1. 延迟触发
   - signal、callback、Proxy、cached_property、pending queue、bootstep lifecycle

2. 运行时前提
   - env、broker capability、Django settings、acks flags、import timing、scheduler stage

3. 动态解析
   - `symbol_by_name`
   - `importlib.import_module`
   - 动态 subclass / registry lookup

4. 多阶段收敛
   - 真正目标不在入口文件
   - 需要跨模块追到执行点才能落地

### `hard` 必须 `reject`

- 只有字符串映射或 alias 查表
- 只有一层 wrapper，没有运行时条件
- 只是入口远，不是逻辑难
- 只是“题干长”，不是链路硬

### `hard` 可 `accept_with_fix`

- `hard` 成立，但题目把“触发点”和“执行点”混了
- `hard` 成立，但 `implicit_level` 偏高或偏低一档
- `hard` 成立，但遗漏了一个必须显式写出的运行时前提

---

## Runtime Risk Gate

round 4 最容易再次踩雷的，是把运行时行为题写成静态 FQN 题。以下风险一旦出现，必须先判：

1. 导入时机风险
   - env 在模块导入前还是导入后注入
   - fixup / extension 是否只在 init 阶段生效

2. 配置开关风险
   - `acks_late`
   - disable-prefetch
   - native delayed delivery
   - timezone / utc / scheduler persistence

3. 生命周期风险
   - CLI 解析阶段
   - app finalize 阶段
   - worker init 阶段
   - beat 启动重建阶段
   - 运行期发送 / ack / reserve 阶段

4. 弱引用与对象身份风险
   - retry wrapper
   - original receiver
   - lookup key 如何保持可 disconnect

这些风险若未转写成“可复核前提 + 单点问题”，默认不放过。

---

## Formal Entry Checklist

候选题进入 round 4 正式起草前，必须全部满足：

1. 能写成一个单句问题，且不含“分别”“哪些”“什么时候又会”
2. 能在 `ground_truth` 中用 FQN 最小闭包表达
3. 题面已显式写出所有必要运行时前提
4. `direct_deps` 是真正命中的最终目标，不是中间跳板
5. `indirect_deps` 与 `implicit_deps` 没有把 side effects 混进来
6. `difficulty` 与 `implicit_level` 彼此一致
7. 若标 `Type D`，必须能指出至少一个最像的错误竞争对象
8. 若标 `Type A`，必须能指出至少一个“截断就会错”的关键跳步
9. 若标 `hard`，必须能说明它为什么不是 medium

---

## Round 4 Reviewer Default Stance

对本轮高价值候选题，默认按以下顺序怀疑：

1. 这是不是一题里偷偷塞了两个判断点
2. 这是不是在问值语义，却假装能用 FQN 判
3. 这是不是依赖运行时前提，却没把前提写出来
4. 这是不是只有“入口远”，没有“逻辑硬”
5. 这是不是把 side effects 塞进了最小闭包

只要有一条答不稳，就不应直接进 formal eval pool。
