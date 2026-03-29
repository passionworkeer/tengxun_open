# 答辩页提纲（2026-03-29）

## Slide 1. 题目与目标

标题建议：

- `基于 PE / RAG / FT 的代码分析效果优化`

这一页只讲三句话：

1. 任务是做真实开源项目上的代码分析优化，不是只跑公开 benchmark。
2. 我选的是 Celery 跨文件依赖分析，重点覆盖动态符号解析、再导出链和隐式依赖。
3. 目标是比较 `PE / RAG / FT` 三类方法的独立与组合收益。

## Slide 2. 数据与评测设计

必须放的点：

- `54` 条正式评测集，全手工标注
- `20` 条 strict few-shot
- `500` 条微调数据
- Difficulty 和 Failure Type 分布

建议一句话：

> 这个评测集最大的价值是基于真实 Celery 源码构建，而不是合成样本。

## Slide 3. 为什么这个任务难

建议画三类难点：

- 长调用链
- 再导出 / alias
- finalize / Proxy / symbol_by_name 这种隐式依赖

核心句：

> 难点不是“找不到符号”，而是“跨文件走到最终真实符号，并把层级放对”。

## Slide 4. 基线模型表现

放三行：

- GPT-5.4
- GLM-5
- Qwen3.5-9B

只讲结论：

- GPT 是商业模型上界
- GLM 主要受结构化输出适配影响
- Qwen strict baseline 很低，说明开源模型在这个任务上需要系统增强

建议配图：

- `img/final_delivery/01_model_baselines_20260328.png`

## Slide 5. Prompt Engineering 主结果

放正式 54-case progressive 结果：

- baseline
- system_prompt
- cot
- fewshot
- postprocess

讲清楚：

- PE 是当前最强单项优化
- 但 union F1 不足以反映层级是否放对

建议配图：

- `img/final_delivery/02_pe_progression_20260328.png`

## Slide 6. strict 增补：为什么要看 macro 和 mislayer

这一页只解释两个指标：

- `active-layer macro F1`
- `mislayer rate`

核心句：

> 很多方法只是把 FQN 找到了，但放错层；如果只看 union，会高估效果。

建议配图：

- `img/final_delivery/03_bottleneck_heatmap_20260328.png`

## Slide 7. strict PE 搜索：什么有效，什么无效

建议做一个四象限表：

- 有效：`fewshot_targeted`
- 最优：`postprocess_targeted`
- 失败：`fewshot_layer_guard`
- 失败：`fewshot_assistant`

要讲清楚：

- 更强规则 prompt 没用
- assistant few-shot 也没用
- 真正有效的是 targeted few-shot selection

## Slide 8. 当前最优 GPT PE 方案

直接放最终结果：

- `postprocess_targeted = union 0.6338 / macro 0.4757 / mislayer 0.1620`

然后和旧 strict-best 对比：

- `0.6136 / 0.4372 / 0.2336`

结论句：

> 新方案几乎不损失 union，但明显提高 strict macro，并显著降低 mislayer。

## Slide 9. RAG 与 FT 的边界

这一页讲两个结论：

1. RAG 不是默认全开，更适合 hard / dynamic case
2. FT 单独不够，真正有效的是 `PE + FT`

放 Qwen 的三组关键结果：

- `FT only`
- `PE + FT`
- `PE + RAG + FT`

建议配图：

- RAG：`img/final_delivery/05_rag_end_to_end_20260328.png`
- Qwen 策略：`img/final_delivery/06_qwen_strategies_20260328.png`

## Slide 10. 最终策略建议

建议分两类：

### 商业模型

- `GPT-5.4 + postprocess_targeted`

### 开源模型

- 历史正式最高分：`Qwen PE + RAG + FT`
- 历史正式默认路线：`Qwen PE + FT`
- 最严格口径下补一句：strict-clean FT rerun pending

最后一句：

> 这个项目最终证明的不是“Prompt 越复杂越好”，而是“failure mode 定义 + targeted few-shot + 不破坏层级的后处理”才是最有效的优化路径。

## 备选附页

如果导师追问，再补这三页：

- 附页 1：Failure Type A-E 示例
- 附页 2：strict PE 搜索矩阵
- 附页 3：GLM thinking 为什么不纳入正式主实验
