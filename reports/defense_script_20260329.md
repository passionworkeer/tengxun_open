# 答辩稿（2026-03-29）

## 1. 30 秒版本

我这个项目做的是 Celery 真实开源代码上的跨文件依赖分析优化，目标是比较系统地验证 `PE / RAG / FT` 三类方法在代码分析任务上的真实收益。

我最终做了三件关键事：

1. 基于真实 Celery 源码构建了 `54` 条全手工标注评测集，覆盖 `easy / medium / hard` 和 `Type A-E` 五类失效模式。
2. 把 Prompt Engineering 从“写更长 prompt”变成了系统实验，最后证明最优策略不是更强规则，而是 `targeted few-shot selection + layer-preserving postprocess`。
3. 把 Qwen 的 `PE / RAG / FT / PE+FT / PE+RAG / PE+RAG+FT` 消融矩阵补齐，明确了开源模型里历史正式最优组合和适用边界。

如果只看 strict 口径下的 GPT PE 最优结果，当前最好的是：

- `postprocess_targeted = union 0.6338 / macro 0.4757 / mislayer 0.1620`

## 2. 2 分钟版本

### 2.1 我做的任务是什么

我选的代码分析方向是：

- Celery 跨文件依赖分析
- 重点覆盖动态符号解析、再导出链、Proxy/finalize/shared_task 这类传统静态分析容易丢链的场景

这个方向的难点不只是“能不能找到 FQN”，而是：

- 能不能跨文件走到最终真实符号
- 能不能区分 `direct / indirect / implicit` 三层依赖

所以我做了两套评分：

- 主评分：union F1
- strict 增补：`active-layer macro F1` + `mislayer rate`

### 2.2 我怎么构建数据和评测

我在真实 Celery 项目上构建了：

- `54` 条正式评测集，全部手工标注
- `20` 条 strict few-shot
- `500` 条微调数据

评测集按两个维度覆盖：

- Difficulty：`easy 15 / medium 19 / hard 20`
- Failure Type：`Type A 7 / Type B 9 / Type C 11 / Type D 11 / Type E 16`

这里我最强调的一点是：

> 评测集不是合成 toy case，而是真实开源项目里的可验证链路。

### 2.3 我的核心发现是什么

第一个结论是 Prompt Engineering 是最强单项优化。

在正式 54-case 口径下：

- GPT-5.4 baseline：`0.2745`
- GPT-5.4 postprocess：`0.6062`

但是我后来发现只看 union F1 不够，因为很多 case 是“FQN 找到了，但层放错了”。  
所以我又补做 strict PE 搜索，结果发现：

- 真正有效的不是更强的 system prompt
- 也不是 assistant few-shot 这种更像标准 chat 的格式
- 真正有效的是 `targeted few-shot selection + layer-preserving postprocess`

最后最优结果是：

- `postprocess_targeted = 0.6338 / 0.4757 / 0.1620`

也就是：

- union 更高
- strict macro 更高
- mislayer 更低

### 2.4 为什么这个结论重要

因为它说明：

> 代码分析任务里，Prompt Engineering 的关键不是“把规则写得更狠”，而是“把正确的 failure-mode 示例喂给模型”。

我把 `Type B / Type E / Type D` 这些最容易错层的样例做成 targeted anchors：

- `shared_task / finalize / proxy / pending` 对应 Type B
- `symbol_by_name / loader / backend / string import` 对应 Type E
- 冲突和歧义路由对应 Type D

这个改动比一味加强 system prompt 更有效，也更容易解释。

## 3. 为什么其他方案失败

### 3.1 为什么不是 layer_guard

我专门试了更强的 layer guard 提示。

结果是：

- union 可能会上升
- 但 strict macro 会下降
- mislayer 反而更高

原因是模型会变得更模式化，开始“强行分层”，而不是基于真实调用链分层。

### 3.2 为什么不是 assistant few-shot

我也试了把 few-shot 改成标准 `user -> assistant JSON` 对话对。

结果也退化了，说明这个任务里决定效果的不是消息角色，而是 few-shot 内容本身。

### 3.3 为什么不是 GLM thinking

我尝试补测了 GLM 官方 `thinking` 路线，但：

- `thinking + stream` smoke 在首个 case 阻塞
- `thinking + non-stream` 也无法稳定完成首题

所以我没有把它纳入正式主实验矩阵，而是保留稳定 baseline，把 thinking 写成探索路径。

## 4. RAG 和 FT 的结论

### 4.1 RAG 不是默认全开

RAG 的整体提升不大，但对 hard case 很有帮助。

比如 GPT 端到端：

- `No-RAG 0.2783 -> With-RAG 0.2940`

总体只提升一点，但 hard 从：

- `0.1980 -> 0.3372`

说明 RAG 更像定向修复器，不是默认全开加分器。

### 4.2 微调不是单独就够

Qwen strict baseline 非常低，strict-clean `FT only` 依然只有 `0.0932`，而当前最强的完整 strict-clean 路线已经是 `PE + RAG + FT = 0.5018`。

这说明：

- FT 负责领域模式适配
- PE 负责把模式转成稳定可评分输出
- RAG 只有在模型已经具备领域模式和输出约束后，才真正变成增益项

所以开源模型里最值得讲的结论不是“微调万能”，而是：

> 微调必须和 PE 结合，才会真正转化成代码分析效果。

## 5. 如果导师追问“你最自豪的地方是什么”

我会答：

> 不是把分数跑高，而是把“为什么会高、为什么有些套路反而会掉分”这件事讲清楚了。

具体就是三点：

1. 我构建了真实项目上的手工评测集，而不是只跑公开 benchmark。
2. 我把 strict 层级评分补进来，证明很多方法只是“提高 union”，并没有真正提升依赖层级分析质量。
3. 我做了负例实验，证明更强规则 prompt 和 assistant few-shot 都不是最优，这让最终的 `postprocess_targeted` 结论更可信。

## 6. 如果导师追问“现在最推荐的策略是什么”

可以直接按这个口径答：

### 商业模型

- 推荐：`GPT-5.4 + postprocess_targeted`
- 原因：strict 指标最优，且可解释性最好

### 开源模型

- strict-clean 最强完整路线：`Qwen PE + RAG + FT = 0.5018`
- strict-clean 低复杂度路线：`Qwen PE + FT = 0.3865`
- 历史正式 `Qwen PE + FT = 0.4315` 只作为归档对照，不再作为主口径

### 工程上怎么落地

1. 默认先走 `PE`
2. Hard / Type A / Type E 场景再开 `RAG`
3. 如果用开源模型部署并追求当前最强完整结果，就选 `Qwen PE + RAG + FT`；如果强调较低复杂度，则选 strict-clean `Qwen PE + FT`

## 7. 一句话总结

这个项目最终证明的不是“Prompt 越复杂越好”，而是：

> 在真实代码分析任务里，最有效的优化来自对失败模式的精确定义、针对性 few-shot 选例、以及不破坏层级信息的后处理。
