# 答辩风险台账（2026-03-29）

## P0 风险

### 风险 1：被质疑“为什么不用 strict 做唯一主指标”

风险描述：

- 导师可能会质疑 union F1 会高估方法效果

标准回答：

- 早期正式口径沿用 union F1，是为了和原始主实验保持一致
- 但我已经补做了 strict 增补，用 `macro F1 + mislayer rate` 识别“找到了 FQN 但放错层”的问题
- 最终最优 PE 方案是按 strict 指标选出来的，不是只看 union

防守文件：

- [strict_scoring_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_scoring_audit_20260329.md)
- [strict_pe_search_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_pe_search_20260329.md)

### 风险 2：被质疑 few-shot / 微调数据污染

风险描述：

- 导师可能问评测集和训练/示例集是否重合

标准回答：

- 我后来专门补做了 strict 数据审计
- strict 资产用于去污染复验和答辩防守
- 当前展示的 strict PE 最优路线基于 strict few-shot 资产
- Qwen FT 家族我会明确标成“历史正式结果”，strict-clean 重训入口已经补齐但结果待外部 GPU 落盘

防守文件：

- [strict_data_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_data_audit_20260329.md)

### 风险 3：被质疑“是不是后处理在作弊”

风险描述：

- 导师可能担心 postprocess 通过规则“补答案”

标准回答：

- postprocess 只做解析、canonicalization、分层保留
- 不会凭空添加 ground truth 符号
- 如果原始输出没有有效 JSON / FQN，postprocess 也不会生成正确答案

防守文件：

- [post_processor.py](/Users/jiajingqiu/tengxun/pe/post_processor.py)
- [strict_pe_search_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_pe_search_20260329.md)

## P1 风险

### 风险 4：被质疑“为什么强规则 prompt 反而掉分”

风险描述：

- 导师可能觉得规则更强应该更好

标准回答：

- 实验结果证明不是规则越多越好
- `layer_guard` 会让模型更模式化，导致 strict 层级归位更差
- 这个任务里真正有效的是 failure mode 级别的示例选择，而不是语言层面的更强约束

### 风险 5：被质疑“assistant few-shot 为什么不如普通 few-shot”

标准回答：

- 这里的关键不是消息角色，而是 few-shot 内容分布
- assistant 形式提升了结构化跟随，但没有改善层级判断
- strict 结果已经证明它会让 mislayer 变高

### 风险 6：被质疑“为什么 GLM thinking 不纳入正式结果”

标准回答：

- 我做了官方 endpoint 的 smoke
- `thinking + stream` 和 `thinking + non-stream` 都在首题阻塞，无法形成稳定可复验结果
- 所以我把它保留为探索路径，而不是拿不稳定数据混进正式结论

## P2 风险

### 风险 7：被质疑“RAG 整体提升为什么不大”

标准回答：

- 因为这个任务里很多 easy case 本来不需要额外上下文
- RAG 的价值主要体现在 long-chain / dynamic / hard case
- 所以它更像定向修复器，而不是默认全开加分器

### 风险 8：被质疑“FT only 为什么不够”

标准回答：

- FT 更像在学习领域模式
- 但真正把模式转成稳定输出的是 PE
- 所以开源模型里最关键的提升路线是 `PE + FT`

## 现场操作建议

### 如果导师追着问方法学

优先讲：

1. 为什么要补 strict 指标
2. 为什么最终最优是 targeted few-shot
3. 为什么强规则 prompt 不是最优

### 如果导师追着问工程落地

优先讲：

1. 商业模型：`GPT-5.4 + postprocess_targeted`
2. 开源模型默认路线：历史正式 `Qwen PE + FT`
3. Hard case 再按需开 RAG

### 如果导师追着问风险

优先讲：

1. 数据审计已经补做
2. strict 评分已经补做
3. GLM thinking 已做 smoke 但因稳定性问题不纳入正式结果
4. Qwen strict-clean FT 执行包已准备，当前只差外部 CUDA 环境落盘
