# 报告文档说明

## 📊 交付报告

| 报告 | 内容 |
|------|------|
| `DELIVERY_REPORT.md` | 完整交付报告（导师版） |
| `bottleneck_diagnosis.md` | 瓶颈诊断报告（5类失效分析） |
| `pe_optimization.md` | PE优化报告（四维度独立增益） |
| `ablation_study.md` | 消融实验报告（10组实验矩阵） |
| `rag_retrieval_eval_round4.md` | RAG检索评估报告 |

---

## 📈 核心结论速览

### 1. 基线成绩
- GPT-5.4: Avg F1 = 0.3122 (Easy: 0.4475, Hard: 0.2373)
- PE优化后: Avg F1 = 0.6230 (+99% 提升)

### 2. RAG效果
- Graph索引最强 (Recall@5: 0.3234)
- RRF k=30 为推荐配置

### 3. 工程建议
- 依赖深度≥3的场景需要 FT
- 仅 35% 模块需完整 RAG+FT，可节省 65% Token

---

## 🔬 消融实验状态

| 实验组 | 状态 |
|--------|------|
| Baseline GPT-5.4 | ✅ |
| Baseline GLM-5 | ⏳ |
| Baseline Qwen | 🔄进行中 |
| PE only | ✅ |
| RAG only | ⏳ |
| FT only | ⏳ |
| PE+RAG | ⏳ |
| PE+FT | ⏳ |
| PE+RAG+FT | ⏳ |

---

## 📞 快速导航

- 想看整体结论 → `DELIVERY_REPORT.md`
- 想看失败模式 → `bottleneck_diagnosis.md`  
- 想看提示工程效果 → `pe_optimization.md`
- 想看完整实验数据 → `ablation_study.md`
- 想看检索细节 → `rag_retrieval_eval_round4.md`