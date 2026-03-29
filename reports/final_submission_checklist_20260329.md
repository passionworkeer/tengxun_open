# 提交前检查清单（2026-03-29）

## 1. 口径统一

- [ ] 对外统一说法：正式评测集是 `54` 条，全手工标注
- [ ] 对外统一说法：GPT strict PE 最优方案是 `postprocess_targeted`
- [ ] 对外统一说法：GLM `thinking` 是探索路径，不是正式主实验
- [ ] 不再引用旧的 `50-case` 草稿结论

## 2. 必带结果

- [ ] GPT baseline 正式结果
- [ ] GPT PE progressive 正式结果
- [ ] GPT strict PE 最优结果
- [ ] GPT RAG 正式结果
- [ ] Qwen baseline / FT / PE / PE+FT / PE+RAG / PE+RAG+FT

## 3. 必带文档

- [ ] [README.md](/Users/jiajingqiu/tengxun/README.md)
- [ ] [DELIVERY_REPORT.md](/Users/jiajingqiu/tengxun/reports/DELIVERY_REPORT.md)
- [ ] [strict_pe_search_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_pe_search_20260329.md)
- [ ] [defense_script_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_script_20260329.md)
- [ ] [defense_qa_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_qa_20260329.md)
- [ ] [executive_summary_20260329.md](/Users/jiajingqiu/tengxun/reports/executive_summary_20260329.md)
- [ ] [defense_slides_outline_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_slides_outline_20260329.md)

## 4. 必带结果文件

- [ ] [pe_postprocess_targeted_strict.json](/Users/jiajingqiu/tengxun/results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json)
- [ ] [pe_fewshot_targeted_strict.json](/Users/jiajingqiu/tengxun/results/pe_targeted_full_20260329/pe_fewshot_targeted_strict.json)
- [ ] [strict_scoring_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_scoring_audit_20260329.md)
- [ ] [strict_data_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_data_audit_20260329.md)

## 5. 答辩时必须讲清楚的三点

- [ ] 为什么不能只看 union F1
- [ ] 为什么更强规则 prompt 反而掉分
- [ ] 为什么最终最优是 targeted few-shot + postprocess

## 6. 导师高概率追问

- [ ] 评测集是否全手工标注
- [ ] 是否存在数据污染
- [ ] strict 指标和主指标的关系
- [ ] RAG 为什么整体增益不大
- [ ] 为什么 FT 单独不够
- [ ] GLM thinking 为什么不纳入正式主实验

## 7. 提交前最后核对

- [ ] 工作区里没有把非正式中间结果混进正式报告
- [ ] 不引用已删除或未提交的路径
- [ ] 口播数字和文档数字一致
- [ ] 图表标题和正文口径一致
- [ ] 所有正式文件都能在仓库中直接打开
