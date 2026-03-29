# 导师追问 Q&A（2026-03-29）

## Q1. 你为什么不用公开 benchmark，而是自己做 Celery 数据集？

因为题目要求是“在真实开源项目上构建评测集并诊断瓶颈”。  
公开 benchmark 可以做参考，但不能替代真实项目里的动态依赖、再导出链和字符串解析场景。

Celery 这个项目的价值在于：

- 有大量跨文件依赖
- 有动态符号解析
- 有 finalize / shared_task / Proxy / loader 这类隐式依赖

所以它比 toy task 更能检验模型在真实代码分析场景里的能力。

## Q2. 你的 54 条评测集真的是手工标注的吗？

是。  
当前正式口径下，`54-case` 的 `difficulty / failure_type / ground_truth` 都按源码阅读手工标注，仓库里也已经统一写成这个口径。

## Q3. 你主评分为什么不是 strict 分层评分？

因为项目最早的正式主口径是 union F1，这和原任务里的“依赖识别正确率”是一致的。  
但我后来发现只看 union 不够，所以补加了 strict 指标：

- `active-layer macro F1`
- `mislayer rate`

这个补充的作用是把“找到了 FQN，但放错层”的问题单独暴露出来。  
最终我没有只停留在 union，而是把 strict 结果也做成正式增补，并用它来选出真正最优的 PE 方案。

## Q4. 你的 Prompt Engineering 到底优化了什么？

不是单纯把 prompt 写长。  
我系统试了四类手段：

- System Prompt
- CoT
- Few-shot
- Post-process

然后又继续试了 strict 增补版本：

- 更强 layer guard
- assistant few-shot
- targeted few-shot

最后证明最有效的是：

- `targeted few-shot selection + layer-preserving postprocess`

## Q5. 为什么 targeted few-shot 比更强规则 prompt 更有效？

因为这个任务的主要难点不是“不知道要分层”，而是“在什么 failure mode 下会放错层”。

比如：

- Type B：finalize / decorator / proxy
- Type E：symbol_by_name / string import / loader
- Type D：冲突和歧义路由

targeted few-shot 是把这些最容易错层的模式直接示范给模型。  
而更强规则 prompt 只是在语言层面强调约束，不能替代具体 failure mode 的示范。

## Q6. 为什么 assistant few-shot 反而掉分？

因为在这个任务上，few-shot 的关键不是消息角色，而是内容分布。  
assistant 形式让输出更像“会写 JSON”，但不会自动提升“层级放对”的能力。

实验结果恰恰说明：

- 它可能改善结构化跟随
- 但会让 strict 层级归位更差

## Q7. 你怎么证明 postprocess 没有在“作弊”？

我的 postprocess 只做三类事：

1. 解析模型原始 JSON
2. 做符号 canonicalization
3. 保留 direct / indirect / implicit 三层

它不做事实修正，不会凭空添加 ground truth 里的符号。  
如果原始输出里没有有效依赖，postprocess 不会“猜答案”。

## Q8. 你为什么说 GLM thinking 不纳入正式对比？

因为我做了 smoke：

- 官方 `thinking + stream` 在首题阻塞
- 官方 `thinking + non-stream` 也在首题阻塞

也就是说它不是“效果差”，而是“当前 endpoint 稳定性不足，无法形成正式可复验结果”。  
所以正式报告里保留稳定 baseline，把 thinking 作为探索路径说明。

## Q9. 你的 RAG 为什么整体提升不大？

因为这个任务里很多 easy case 不需要额外上下文。  
RAG 的价值主要在：

- 长链调用
- 动态解析
- 跨文件 alias / registration

所以它更像定向修复器，而不是全量默认加分器。

## Q10. 你的微调有没有数据污染风险？

这是我后来重点补强的地方。  
我做了 strict 数据审计，把 exact GT overlap 和 hard question overlap 清到 0，再用 strict 数据做后续对比口径。

也就是说，后面我展示的 strict PE 路线，不建立在“训练集见过评测答案”这个前提上。  
但如果导师继续追问 Qwen 的 FT 家族，我会明确补充：

- 当前 `FT only / PE + FT / PE + RAG + FT` 仍是历史正式 FT 结果
- strict-clean 数据、配置和一键执行脚本已经准备好
- 这条线还需要外部 CUDA 环境重训后，才能把 FT 最终数字彻底切到 strict-clean 口径

## Q11. 为什么你说开源模型不是 FT 单独最有效，而是 PE+FT？

因为从结果看：

- `FT only` 有提升
- 但 `PE + FT` 提升更大

这说明微调更多是在学习领域模式，而不是自动学会稳定输出评测需要的结构化 FQN。  
真正把模式变成可评分输出的，还是 PE。

## Q12. 你最后最推荐的策略是什么？

如果是商业模型：

- `GPT-5.4 + postprocess_targeted`

如果是开源模型：

- 历史正式最高分：`Qwen PE + RAG + FT`
- 历史正式默认路线：`Qwen PE + FT`
- 最严格口径下要补一句：strict-clean FT rerun pending，但执行包已经准备好

## Q13. 你的项目最有说服力的地方是什么？

不是单一最高分，而是：

1. 数据是基于真实项目手工构建的
2. 实验是成体系的，不是只晒一个最优数字
3. 有正例，也有反例，能解释为什么某些套路没用
4. strict 指标补出了“找到了 FQN 但放错层”的真实问题

## Q14. 如果继续做下一步，你会优先做什么？

我会优先做两件事：

1. 把 strict 最优 PE 路线迁移到 Qwen 线上，看 `targeted few-shot` 是否也能提升开源模型
2. 继续优化 Type C，也就是再导出链和 alias chain，因为这仍是当前最优策略的相对薄弱点
