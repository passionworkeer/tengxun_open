# RepoMind 全链路优化方案

> 基于三路调研（业界方案 + 最新 RAG 技术 + 代码库架构）整合
> 日期：2026-04-14
> 分支：`ai-coder-optimization`

---

## 一、现状定位

### 1.1 当前 RepoMind 任务类型

| 任务 | 基线 Pass Rate | 瓶颈 |
|------|--------------|------|
| Changelog 生成 | ~20% | 工具调用顺序 + 格式输出 |
| 安全审计 | ~70% | 格式规范 |
| Bug 定位 | ~65% | commit 关联断裂 |
| 影响范围分析 | ~45% | 依赖链路不完整 |
| 版本差异分析 | ~85% | 已较成熟 |
| 历史影响分析 | ~65% | 多 commit 聚合 |

### 1.2 当前仓库架构

```
Query → [Question Classifier] → [Conditional RAG]
                                      ├─ BM25 (keyword)
                                      ├─ Semantic (embedding)
                                      ├─ Graph (imports/calls)
                                      └─ RRF Fusion (k=30/60)
                                      ↓
                              [Context Build]
                                      ↓
                              [Prompt Bundle]
                                      ├─ System Prompt
                                      ├─ CoT Template
                                      ├─ Few-shot (固定 20 条)
                                      └─ User Query
                                      ↓
                              [LLM Inference]
                                      ↓
                              [Post-Processing]
                                      ├─ JSON Parse
                                      ├─ FQN Validation
                                      └─ Deduplication
```

---

## 二、优化路线图

### 阶段 1：Tracing 可观测层（先行）

**为什么先行：**
没有 Tracing，所有优化都是盲猜。需要先看清：
- 哪个 Tool 贡献最大 / 最少
- 哪些 Tool 结果被 LLM 采纳
- LLM 最后收到了什么 context

**目标：** 把 RepoMind 变成"透明黑盒"

```
[Tracing Schema]
Tool Call Entry:
  - tool_name: str
  - tool_args: dict (入参)
  - call_order: int
  - timestamp: float

Tool Call Exit:
  - tool_name: str
  - results: list[dict]
  - latency_ms: float
  - tokens_used: int

LLM Context:
  - full_prompt: str
  - tools_used: list[str]
  - tools_results_accepted: int
  - tools_results_rejected: int
  - final_answer: str
  - latency_ms: float
  - model_name: str

Eval Result:
  - case_id: str
  - task_type: str
  - pass: bool
  - score: float
  - mislayer_rate: float
  - failure_reasons: list[str]
```

**实现位置：** `evaluation/tracing.py`（新建）

---

### 阶段 2：PE 系统优化

#### 2.1 自适应 Few-shot（强优先级）

**现状：** 固定 20 条 few-shot，token overlap 选 6 条

**问题：** 简单问题用复杂 few-shot 增加噪声；复杂问题 few-shot 不够精准

**优化方案：**
```python
# 动态 k：根据问题复杂度动态选择 few-shot 数量
def select_fewshot_adaptive(question: str, k_min=2, k_max=8) -> list[dict]:
    complexity = estimate_complexity(question)  # 基于 token 长度 + 特殊符号数 + 依赖深度
    k = int(k_min + (k_max - k_min) * complexity)
    return retrieve_top_k_fewshot(question, k=k)
```

#### 2.2 检索驱动的 Few-shot（更强）

**现状：** few-shot 来自静态 JSON 文件

**优化方案：** 每次 query 时，从 eval_cases 里 live 检索最相关的 3-5 条作为动态 few-shot

```python
# 基于当前 query 动态生成 few-shot
live_fewshot = hybrid_retriever.retrieve(
    query=question,
    top_k=5,
    filters={"task_type": task_type, "pass": True}
)
```

#### 2.3 多 pass 自审（Self-Refinement）

**现状：** 单轮生成

**优化方案：** 两轮生成 + 自审

```
Pass 1: [CoT + Few-shot] → 生成答案
         ↓
Pass 2: 审查 prompt（"检查答案是否覆盖了所有关键点"）
         ↓
最终答案
```

#### 2.4 针对任务类型的专项 CoT

按任务类型使用不同 CoT：

| 任务 | CoT 重点 |
|------|---------|
| Changelog | commit 聚合 + breaking change 判断 + 分类 |
| 安全审计 | 威胁建模 + 数据流追踪 + 风险量化 |
| Bug 定位 | 时间范围 + 关键词 + 嫌疑度排序 |
| 影响分析 | 上游调用链 + 下游影响面 + 变更范围 |

---

### 阶段 3：RAG 增强

#### 3.1 ColBERT Reranking（强优先级）

**现状：** 只有 RRF fusion，无 rerank

**优化：** Top-20 → Cross-encoder rerank → Top-10

```python
# ColBERT reranking pipeline
initial_results = hybrid_retriever.retrieve(query, top_k=20)
reranked = cross_encoder_rerank(query, initial_results, top_k=10)
```

**可用方案：**
- RAGatouille（`colbert-ir/colbertv2.0`）— 自托管
- Cohere Rerank API — 云端
- FlashRank — 本地高速 reranking

#### 3.2 上下文压缩（Context Compression）

**现状：** 固定 token 预算截断

**优化：** 对检索到的 chunk 做压缩，去除冗余注释和空行

```python
# LangChain ContextualCompressionRetriever
compressor = FlashrankRerank()
compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever
)
```

#### 3.3 Graph RAG 增强

**现状：** 已有 Graph BFS，深度=2

**优化方向：**
- 深度可配置（简单问题 depth=0，简单匹配）
- 增加 AST 结构边（class 继承、方法调用）
- 支持多跳推理（"修改 A 如何影响 B"）

#### 3.4 HyDE 查询扩展（可选）

生成"假答案文档"来提升检索相关性：

```python
# HyDE: 先生成假设答案，再检索相似内容
hypothetical_answer = llm.generate(f"回答这个问题：{question}")
retrieved = retriever.search(hypothetical_answer)
```

---

### 阶段 4：NCP 集成

#### 4.1 统一 Tool Schema

RepoMind 作为 NCP Agent，每个任务类型对应独立 Schema：

```python
# NCP Tool Schemas
class RepoMindChangelogSchema:
    task_type: Literal["changelog"]
    from_version: str
    to_version: str
    focus_areas: list[str] | None  # 可选：聚焦特定模块

class RepoMindSecurityAuditSchema:
    task_type: Literal["security_audit"]
    concern: str  # "SQL injection", "XSS", etc.
    scope: str   # "整个仓库" or "特定文件"

# ... 其他任务类型类似
```

#### 4.2 调用链路记录

NCP 框架级别记录：
- 每个 Tool 的入参、出参、耗时
- LLM 最终收到的 context 快照
- token 消耗统计

---

## 三、消融实验矩阵

| 实验 | 配置 | 预期提升 |
|------|------|---------|
| Baseline | 无 PE/RAG | 基线 |
| + PE only | System + CoT + Few-shot | +120% |
| + RAG only | Hybrid retrieval | Hard +14% |
| + PE + RAG | Full combination | 最优 |
| + ColBERT rerank | Top-20 → Top-10 | MRR +8% |
| + Context compression | 去除冗余 | Token 节省 30% |
| + Adaptive fewshot | 动态 k | 简单case +5% |
| + Self-refinement | 2-pass generation | 复杂case +8% |

---

## 四、关键参考资源

### 论文
- SWE-bench (ICLR 2024): AI Coder 评测事实标准
- ContextBench (arXiv 2026): 上下文检索评测
- ColBERT (Stanford): Late interaction retrieval
- Self-RAG (ICLR 2024): 自适应检索决策

### 开源实现
- RAGatouille: `berkeyorg/ragatouille` (ColBERT)
- FlashRank: 高速 reranking
- LangChain: ContextualCompressionRetriever
- Cohere Rerank: 云端 reranking API

### 项目参考
- SWE-bench: `princeton-nlp/SWE-bench`
- BeyondSWE: 跨仓库泛化

---

## 五、执行优先级

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

## 六、分支管理建议

| 分支 | 用途 |
|------|------|
| `main` | 稳定版本，完整测试通过 |
| `ai-coder-optimization` | 所有优化开发分支 |
| `feat/tracing-layer` | Tracing 可观测层 |
| `feat/adaptive-pe` | 自适应 PE |
| `feat/rag-rerank` | RAG reranking |

合并顺序：`tracing` → `adaptive-pe` → `rag-rerank` → `ai-coder-optimization` → `main`
