# 提交前检查清单（2026-03-29）

## 1. 口径统一

- [x] 对外统一说法：正式评测集是 `54` 条，全手工标注
- [x] 对外统一说法：GPT strict PE 最优方案是 `postprocess_targeted`
- [x] 对外统一说法：GLM `thinking` 是探索路径，不是正式主实验
- [x] 不再引用旧的 `50-case` 草稿结论

## 2. 必带结果

- [x] GPT baseline 正式结果
- [x] GPT PE progressive 正式结果
- [x] GPT strict PE 最优结果
- [x] GPT RAG 正式结果
- [x] Qwen baseline / FT / PE / PE+FT / PE+RAG / PE+RAG+FT

## 3. 必带文档

- [x] [README.md](/Users/jiajingqiu/tengxun/README.md)
- [x] [DELIVERY_REPORT.md](/Users/jiajingqiu/tengxun/reports/DELIVERY_REPORT.md)
- [x] [strict_pe_search_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_pe_search_20260329.md)
- [x] [defense_script_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_script_20260329.md)
- [x] [defense_qa_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_qa_20260329.md)
- [x] [executive_summary_20260329.md](/Users/jiajingqiu/tengxun/reports/executive_summary_20260329.md)
- [x] [defense_slides_outline_20260329.md](/Users/jiajingqiu/tengxun/reports/defense_slides_outline_20260329.md)

## 4. 必带结果文件

- [x] [pe_postprocess_targeted_strict.json](/Users/jiajingqiu/tengxun/results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json)
- [x] [pe_fewshot_targeted_strict.json](/Users/jiajingqiu/tengxun/results/pe_targeted_full_20260329/pe_fewshot_targeted_strict.json)
- [x] [strict_scoring_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_scoring_audit_20260329.md)
- [x] [strict_data_audit_20260329.md](/Users/jiajingqiu/tengxun/reports/strict_data_audit_20260329.md)

## 5. 答辩时必须讲清楚的三点

- [x] 为什么不能只看 union F1
- [x] 为什么更强规则 prompt 反而掉分
- [x] 为什么最终最优是 targeted few-shot + postprocess

## 6. 导师高概率追问

- [x] 评测集是否全手工标注
- [x] 是否存在数据污染
- [x] strict 指标和主指标的关系
- [x] RAG 为什么整体增益不大
- [x] 为什么 FT 单独不够
- [x] GLM thinking 为什么不纳入正式主实验

## 7. 提交前最后核对

- [x] 工作区里没有把非正式中间结果混进正式报告
- [x] 不引用已删除或未提交的路径
- [x] 口播数字和文档数字一致
- [x] 图表标题和正文口径一致
- [x] 所有正式文件都能在仓库中直接打开
