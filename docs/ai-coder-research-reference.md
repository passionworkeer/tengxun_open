# RepoMind AI Coder 调研参考总览

> 整合四路调研成果：GitHub 生态 + 生产架构 + 自我优化技术 + MCP 工具设计
> 日期：2026-04-14
> 分支：`ai-coder-optimization`

---

## 一、文档索引

| 文档 | 内容概要 |
|------|---------|
| **`github-ai-coder-repos.md`** | Top 15 GitHub AI Code Agent 项目全景（OpenHands / SWE-agent / Claude Code / Cursor / Cline 等），含架构亮点、Stars、参考价值 |
| **`production-ai-coder-architectures.md`** | Devin / Copilot / Cursor / Claude Code / OpenHands / SWE-agent 深度架构解析，含对 RepoMind 的整合建议 |
| **`ai-coder-self-optimization-techniques.md`** | PE / RAG / Self-Refinement / Self-RAG / ReAct / Reflexion 完整技术栈，含 RepoMind 具体实现方案 |
| **`mcp-tool-design-best-practices.md`** | MCP/NCP 工具设计规范，Schema 模板、反模式、最佳实践 checklist |
| **`repomind-optimization-plan.md`** | RepoMind 优化路线图（已有点） |

---

## 二、核心参考来源

### GitHub Top Repos
- `All-Hands-AI/OpenHands` — 最完整开源 SWE Agent，~50k Stars
- `princeton-nlp/SWE-agent` — 代码检索 + Critic Loop，Princeton NLP
- `anthropics/claude-code` — 状态机 + 安全确认 CLI
- `cursor-ai/cursor` — Composer + Rules + Context Pooling
- `cline/cline` — MCP 集成最佳实践，~30k Stars
- `modelcontextprotocol/spec` — MCP 官方规范
- `princeton-nlp/SWE-bench` — AI Coder 评测事实标准

### 关键论文
| 论文 | 贡献 |
|------|------|
| SWE-bench (ICLR 2024) | AI Coder 评测标准 |
| Self-RAG (ICLR 2024) | 自适应检索决策 |
| ReAct (2023) | 推理+行动协同 |
| Reflexion (2023) | 语言强化学习 |
| ColBERT (SIGIR 2020) | Late interaction retrieval |
| ContextBench (arXiv 2026) | 上下文检索评测 |

---

## 三、RepoMind 优化决策矩阵

### PE 优化优先级（基于实测数据）

| 优化项 | 相对增益 | 实现难度 | 优先级 |
|--------|---------|---------|--------|
| Few-shot 增强（困难样本优先） | +36% | 低 | 🔴 最高 |
| CoT 任务专项化 | +35% | 中 | 🔴 最高 |
| 动态 Few-shot（HyDE 思路） | Hard +5-8% | 中 | 🟡 次高 |
| Post-process 加固 | +7% | 低 | 🟡 次高 |
| System Prompt 细化 | +15% | 低 | 🟢 常规 |

### RAG 优化优先级

| 优化项 | 预期提升 | 实现难度 | 优先级 |
|--------|---------|---------|--------|
| ColBERT Reranking | MRR +8% | 中 | 🔴 最高 |
| Context Compression | Token -30% | 低 | 🔴 最高 |
| 代码专用 Embedding | Hard +10% | 高 | 🟡 次高 |
| HyDE（探索性任务） | 复杂任务显著 | 中 | 🟢 常规 |
| Graph RAG 动态深度 | 按任务自适应 | 中 | 🟢 常规 |

### Self-Improvement 优先级

| 优化项 | 适用任务 | 实现难度 | 优先级 |
|--------|---------|---------|--------|
| Self-Refinement (Critic Loop) | Changelog、格式严格任务 | 中 | 🔴 最高 |
| Adaptive Retrieval (Self-RAG Lite) | 所有任务 | 低 | 🔴 最高 |
| Reflexion（失败记忆） | 长期优化 | 高 | 🟢 长期 |

---

## 四、执行路线（参考 `repomind-optimization-plan.md`）

```
第 1 步（现在）：Tracing 层
  ↓ 建立可观测性，看清瓶颈再动手
第 2 步：PE 优化（自适应 few-shot + 多 pass 自审）
  ↓ PE 是最强杠杆
第 3 步：RAG 增强（ColBERT reranking + Context compression）
  ↓ 针对 Hard case
第 4 步：NCP 集成
  ↓ 最终落地形态
```

---

## 五、快速参考

### RepoMind 当前基线（来自 README.md）

| 策略 | Union | Easy | Medium | Hard |
|------|-------|------|--------|------|
| GPT-5.4 Baseline | 0.27 | 0.39 | 0.26 | 0.20 |
| GPT-5.4 PE only | 0.61 | 0.67 | 0.62 | 0.55 |
| GPT-5.4 PE + RAG | ~0.63 | 0.62 | 0.52 | 0.40 |
| Qwen PE + RAG + FT | 0.50 | 0.62 | 0.52 | 0.40 |

### RepoMind 当前任务瓶颈

| 任务 | 基线 | 主要瓶颈 |
|------|------|---------|
| Changelog 生成 | ~20% | 工具调用顺序 + 格式输出 |
| 安全审计 | ~70% | 格式规范 |
| Bug 定位 | ~65% | commit 关联断裂 |
| 影响范围分析 | ~45% | 依赖链路不完整 |
| 版本差异分析 | ~85% | 已较成熟 |
| 历史影响分析 | ~65% | 多 commit 聚合 |

---

## 六、关键文件位置

```
docs/
  github-ai-coder-repos.md              ← 业界生态全景
  production-ai-coder-architectures.md ← 生产架构解析
  ai-coder-self-optimization-techniques.md ← 自我优化技术
  mcp-tool-design-best-practices.md     ← 工具设计规范
  repomind-optimization-plan.md         ← 优化路线图
  ai-coder-research-reference.md        ← 本文件（总览）
  README.md                             ← 文档索引
```
