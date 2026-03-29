# 数字速查表（2026-03-29）

## 1. 项目最重要的 10 个数字

1. 正式评测集：`54` 条，全手工标注
2. strict few-shot：`20` 条
3. 微调数据：`500` 条
4. GPT-5.4 baseline：`0.2745`
5. GPT-5.4 正式 PE：`0.6062`
6. GPT strict PE 最优 `postprocess_targeted`：`union 0.6338 / macro 0.4757 / mislayer 0.1620`
7. GPT RAG 端到端：`0.2940`
8. Qwen strict baseline：`0.0370`
9. Qwen strict-clean `PE + RAG + FT`：`0.5018`
10. Qwen strict-clean `PE + FT`：`0.3865`；历史正式 `PE + FT = 0.4315` 只作归档参考

## 2. 商业模型口径

### 基线

- GPT-5.4：`easy 0.4348 / medium 0.2188 / hard 0.2261 / avg 0.2815`
- GLM-5：`easy 0.1048 / medium 0.0681 / hard 0.0367 / avg 0.0666`

### GPT 正式 PE progressive

- baseline：`0.2745`
- system_prompt：`0.3138`
- cot：`0.4218`
- fewshot：`0.5733`
- postprocess：`0.6062`

### GPT strict PE 最优

- `postprocess_targeted`
- union：`0.6338`
- macro：`0.4757`
- mislayer：`0.1620`
- exact layer：`0.1296`

与旧 strict-best 对比：

- old `postprocess_layered`：`0.6136 / 0.4372 / 0.2336`
- new `postprocess_targeted`：`0.6338 / 0.4757 / 0.1620`

## 3. 开源模型口径（strict-clean + 历史正式参考）

### Qwen 基线与单项

- baseline：`0.0370`
- strict-clean FT only：`0.0932`
- PE only：`0.2246`
- RAG only：`0.0185`

### Qwen 组合

- strict-clean PE + RAG + FT：`0.5018`
- strict-clean PE + FT：`0.3865`
- 历史正式 PE + FT：`0.4315`
- PE + RAG：`0.1534`
- 历史正式 PE + RAG + FT：`0.4435`

## 4. RAG 关键数字

### 检索

- fused chunk_symbols Recall@5：`0.4305`
- fused chunk_symbols MRR：`0.5292`
- fused expanded_fqns Recall@5：`0.4502`
- fused expanded_fqns MRR：`0.5596`

### 端到端

- No-RAG：`0.2783`
- With-RAG：`0.2940`
- Hard：`0.1980 -> 0.3372`

## 5. 最容易说错的数字

- GPT 正式 PE `0.6062` 是原始正式 54-case union 结果，不是 strict 最优
- strict GPT PE 最优是 `postprocess_targeted 0.6338 / 0.4757 / 0.1620`
- Qwen 当前最强的完整 strict-clean 路线是 `PE + RAG + FT = 0.5018`
- Qwen strict-clean 低复杂度路线是 `PE + FT = 0.3865`
- 历史正式 `PE + FT = 0.4315` 只作归档参考，不再是主汇报默认值
- GLM `thinking` 没有进入正式主实验矩阵

## 6. 一句话口播版

> 我在 Celery 真实项目上构建了 54 条手工评测集，系统比较了 PE、RAG、FT 和组合策略；最终商业模型 strict 最优是 `GPT-5.4 + postprocess_targeted = 0.6338 / 0.4757 / 0.1620`，开源模型当前最强的完整 strict-clean 路线是 `Qwen PE + RAG + FT = 0.5018`，而最关键的方法论结论是：真正有效的不是更强规则 prompt，而是 targeted few-shot 和不破坏层级信息的后处理。
