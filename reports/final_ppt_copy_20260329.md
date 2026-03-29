# 最终 PPT 逐页文案（2026-03-29）

## Slide 1

### 标题

基于 PE / RAG / FT 的代码分析效果优化

### 副标题

以 Celery 跨文件依赖分析为例

### 页面要点

- 任务：真实开源项目上的代码分析优化
- 方向：跨文件依赖分析、动态符号解析、再导出链追踪
- 目标：比较 `PE / RAG / FT` 的独立与组合收益

### 我口播时说

这个项目不是跑公开 benchmark，而是围绕真实 Celery 源码做跨文件依赖分析优化，重点看模型能不能跨文件走到最终真实符号，并把依赖层级放对。

## Slide 2

### 标题

数据与评测设计

### 页面要点

- 正式评测集：`54` 条，全手工标注
- Few-shot：`20` 条 strict 资产
- 微调数据：`500` 条
- Difficulty：`easy 15 / medium 19 / hard 20`
- Failure Type：`Type A 7 / Type B 9 / Type C 11 / Type D 11 / Type E 16`

### 建议配图

- 一个双轴分布图，左边 difficulty，右边 failure type

### 我口播时说

这里最重要的是评测集不是合成样本，而是基于 Celery 真实源码手工构建。它覆盖了动态符号解析、shared_task、Proxy、再导出链这些真实难点。

## Slide 3

### 标题

为什么这个任务难

### 页面要点

- 长调用链容易丢失上下文
- 再导出 / alias 容易断链
- finalize / Proxy / symbol_by_name 属于隐式依赖
- 找到 FQN 不等于层级放对

### 建议配图

- 一张三段式依赖链示意图：entry -> intermediate -> runtime edge

### 我口播时说

这个任务的难点不是简单的 import 匹配，而是跨文件、多跳、带动态行为的依赖恢复。很多模型的问题不是找不到符号，而是找到了 FQN 但把 direct / indirect / implicit 放错了。

## Slide 4

### 标题

基线模型表现

### 页面要点

- GPT-5.4：商业模型上界
- GLM-5：结构化输出适配较弱
- Qwen3.5-9B：strict baseline 很低

### 建议放表

| 模型 | Avg |
|---|---:|
| GPT-5.4 | `0.2815` |
| GLM-5 | `0.0666` |
| Qwen3.5-9B | `0.0370` |

### 我口播时说

这一步的目的不是单纯比较模型强弱，而是确认后面 PE、RAG、FT 的增益空间和出问题的环节。

## Slide 5

### 标题

Prompt Engineering 主结果

### 页面要点

- `baseline -> system_prompt -> cot -> fewshot -> postprocess`
- GPT-5.4 从 `0.2745` 提升到 `0.6062`
- PE 是当前最强单项优化

### 建议挂图

- `img/final_delivery/02_pe_progression_20260328.png`

### 我口播时说

PE 不是一个单点技巧，而是一组逐步叠加的系统优化。在正式 54-case 上，它是提升幅度最大的单项方法。

## Slide 6

### 标题

为什么要补 strict 指标

### 页面要点

- 主指标：`union F1`
- strict 增补：`active-layer macro F1`
- strict 增补：`mislayer rate`

### 核心句

很多方法只是“把 FQN 找到了”，但没有“把层级放对”。

### 我口播时说

如果只看 union，容易高估方法效果。所以我补加了 strict 指标，用来识别那些命中了 FQN 但层级错位的情况。

## Slide 7

### 标题

strict PE 搜索：什么有效，什么无效

### 页面要点

- 无效：`layer_guard`
- 无效：`assistant few-shot`
- 有效：`targeted few-shot`
- 最优：`targeted few-shot + postprocess`

### 建议放对比表

| Variant | Union | Macro | MisLayer |
|---|---:|---:|---:|
| fewshot_layer_guard | `0.5910` | `0.3408` | `0.3889` |
| fewshot_assistant | `0.5696` | `0.2581` | `0.4938` |
| fewshot_targeted | `0.6061` | `0.4373` | `0.1873` |
| postprocess_targeted | `0.6338` | `0.4757` | `0.1620` |

### 我口播时说

这个结果很关键。真正有效的不是把 prompt 写得更狠，而是对 failure mode 做针对性 few-shot 选例，再用不破坏层级的 postprocess 做收口。

## Slide 8

### 标题

当前最优 GPT PE 方案

### 页面要点

- 最优方案：`postprocess_targeted`
- `union 0.6338`
- `macro 0.4757`
- `mislayer 0.1620`

### 建议对比

旧 strict-best：

- `0.6136 / 0.4372 / 0.2336`

新 strict-best：

- `0.6338 / 0.4757 / 0.1620`

### 我口播时说

这个方案几乎不损失 union，还明显提高 strict macro，并且把 mislayer 降下来了，所以它不是单纯“找得更多”，而是真正“放得更对”。

## Slide 9

### 标题

RAG 与 Fine-tune 的适用边界

### 页面要点

- RAG 更适合 hard / dynamic case
- FT 单独不够，`PE + FT` 才是关键
- 开源模型 strict-clean 最强完整路线：`PE + RAG + FT`
- 开源模型 strict-clean 低复杂度路线：`PE + FT`

### 建议放三组数字

- GPT：`No-RAG 0.2783 -> With-RAG 0.2940`
- Qwen：strict-clean `FT only 0.0932`
- Qwen：strict-clean `PE + FT 0.3865`
- Qwen：strict-clean `PE + RAG + FT 0.5018`

### 我口播时说

RAG 不是默认全开加分器，它更像 hard case 定向修复器。对开源模型来说，FT 负责领域适配，PE 负责把模式转成稳定输出，RAG 只有和 PE/FT 结合才真正有价值。这里我会主动补一句：Qwen 当前最强的完整 strict-clean 路线已经是 `PE + RAG + FT = 0.5018`，而 `PE + FT = 0.3865` 也已经形成完整的低复杂度 strict-clean 路线。

## Slide 10

### 标题

最终结论与推荐策略

### 页面要点

- 商业模型：`GPT-5.4 + postprocess_targeted`
- 开源模型 strict-clean 最强完整路线：`Qwen PE + RAG + FT`
- 开源模型 strict-clean 低复杂度路线：`Qwen PE + FT`
- 历史正式 `Qwen PE + FT = 0.4315` 只作为归档参考

### 结束句

这个项目最终证明的不是“Prompt 越复杂越好”，而是：

> failure mode 定义 + targeted few-shot + 不破坏层级的后处理，才是代码分析任务里最有效的优化路径。

## 附页建议

- 附页 1：Failure Type A-E 代表案例
- 附页 2：strict PE 搜索全矩阵
- 附页 3：GLM thinking 为什么不纳入正式主实验
- 附页 4：strict 指标定义
