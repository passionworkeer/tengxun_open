# 导师一页式摘要（2026-03-29）

## 项目目标

围绕真实开源项目 Celery，验证 `Prompt Engineering / RAG / Fine-tune` 三类方法在代码分析任务中的真实收益，并识别各自的适用边界。

本项目聚焦的代码分析方向是：

- 跨文件依赖分析
- 动态符号解析
- 再导出链追踪

## 数据与评测

- 正式评测集：`54` 条，全部手工标注
- Few-shot：`20` 条 strict 资产
- 微调数据：`500` 条
- 真实项目：`external/celery`

评测集覆盖：

- Difficulty：`easy 15 / medium 19 / hard 20`
- Failure Type：`Type A 7 / Type B 9 / Type C 11 / Type D 11 / Type E 16`

主指标：

- `union F1`

strict 增补指标：

- `active-layer macro F1`
- `mislayer rate`

## 关键结果

### 1. GPT-5.4：PE 是最强单项优化

正式 54-case 结果：

- baseline：`0.2745`
- PE postprocess：`0.6062`

strict 增补后，GPT PE 最优路线进一步更新为：

- `postprocess_targeted`
- 结果：`union 0.6338 / macro 0.4757 / mislayer 0.1620`

这说明：

- 仅看 union 不够
- 真正有效的不是“更强规则 prompt”
- 真正有效的是 `targeted few-shot selection + layer-preserving postprocess`

### 2. RAG：不是默认全开，而是 Hard case 定向修复器

GPT 端到端：

- `No-RAG 0.2783 -> With-RAG 0.2940`

整体提升有限，但 hard 提升明显：

- `0.1980 -> 0.3372`

结论：

- RAG 更适合长链调用、动态解析、跨文件隐式依赖
- 不适合默认对所有 case 全量启用

### 3. Qwen：FT 单独不够，真正有效的是 PE + FT，但 FT 家族当前仍是历史正式线

Qwen strict baseline：

- `0.0370`

关键组合：

- 历史正式 `FT only = 0.0932`
- 历史正式 `PE + FT = 0.4315`
- 历史正式 `PE + RAG + FT = 0.4435`

结论：

- PE 是开源模型的核心增益源
- FT 负责领域适配
- RAG 只有在和 PE / FT 组合时才真正发挥价值
- strict-clean 数据、配置和一键重跑脚本已经就绪，但这条线还需要外部 CUDA 环境重训后才能更新最终数字

## 最终推荐策略

### 商业模型

- `GPT-5.4 + postprocess_targeted`

原因：

- 当前 strict 指标最优
- 机制最可解释
- 对 failure mode 的针对性最强

### 开源模型

- 历史正式最高分：`Qwen PE + RAG + FT`
- 历史正式默认路线：`Qwen PE + FT`
- 最严格口径下，应补充一句：strict-clean FT rerun 已准备，结果待外部 GPU 落盘

## 方法论上的核心结论

这个项目最重要的发现不是“prompt 写得越复杂越好”，而是：

> 在真实代码分析任务里，最有效的优化来自 failure mode 识别、针对性 few-shot 选例，以及不破坏层级信息的后处理。

## 可复验资产

- 最优 GPT strict PE 结果：
  `results/pe_targeted_full_20260329/pe_postprocess_targeted_strict.json`
- strict PE 搜索说明：
  `reports/strict_pe_search_20260329.md`
- strict FT 执行状态：
  `reports/strict_ft_execution_status_20260329.md`
- 训练证据审计：
  `reports/training_evidence_audit_20260329.md`
- 总交付报告：
  `reports/DELIVERY_REPORT.md`
