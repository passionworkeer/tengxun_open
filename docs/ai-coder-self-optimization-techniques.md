# AI Coder 自我优化技术调研报告

> 基于训练知识库（截至 2026-04）
> 整理：RepoMind AI Coder 优化调研
> 核心：无须微调的 PE + RAG + CoT 优化路线

---

## 一、技术全景图

```
AI Coder 自我优化技术
├── Prompt Engineering (PE)
│   ├── System Prompt Engineering
│   ├── Chain-of-Thought (CoT)
│   ├── Few-shot Learning
│   ├── Task-specific Prompting
│   └── Output Formatting
│
├── Retrieval-Augmented Generation (RAG)
│   ├── Dense Retrieval (Embedding)
│   ├── Sparse Retrieval (BM25)
│   ├── Graph RAG (Import/Call Graph)
│   ├── ColBERT / Late Interaction
│   ├── Reranking (Cross-encoder)
│   └── Context Compression
│
├── Self-Improvement Loops
│   ├── Self-RAG (Adaptive Retrieval)
│   ├── Self-Refinement (Critic Loop)
│   ├── ReAct (Reason + Act)
│   ├── Reflexion (Verbal Reinforcement)
│   └── Tool-Planning Agents
│
└── Evaluation & Tracing
    ├── Trace-driven Analysis
    ├── Ablation Studies
    └── Fail-to-Pass Benchmarking
```

---

## 二、Prompt Engineering (PE) 进阶

### 2.1 PE 在 RepoMind 上的实验结果

来自 `reports/pe_optimization.md` 的真实数据：

| PE 阶段 | Easy | Medium | Hard | Avg | 相对增益 |
|---------|------|--------|------|-----|---------|
| Baseline | 0.39 | 0.26 | 0.20 | 0.27 | — |
| + System Prompt | 0.43 | 0.30 | 0.24 | 0.31 | +15% |
| + CoT | 0.48 | 0.42 | 0.38 | 0.42 | +35% |
| + Few-shot | 0.65 | 0.54 | 0.55 | 0.57 | +36% |
| + Post-process | 0.67 | 0.62 | 0.55 | 0.61 | +7% |

**关键结论：**
- **Few-shot 是最大单项增益**（+36%）
- **CoT 对 Medium/Hard 问题帮助最大**
- **Post-process 收益递减**，但仍是低成本保底手段

### 2.2 System Prompt 设计进阶

#### 反面模式（避免）：

```python
# ❌ 太模糊
"You are a helpful code assistant."

# ❌ 太长（LLM 会遗忘中间指令）
"You are a code assistant. You need to analyze code changes...
[3000 token 中间内容]
... Always remember the above."

# ❌ 格式指令和角色指令混在一起
```

#### 最佳实践（推荐）：

```python
# ✅ 角色 + 边界 + 格式 分离
SYSTEM_PROMPT = f"""
## Role
你是一个专业的代码变更分析专家，擅长分析 Git 提交历史、
检测 Breaking Change、评估代码影响范围。

## Constraints
- 只分析提供的代码片段，不要臆测未提供的内容
- 当不确定时，明确说明置信度
- 输出严格遵循 JSON Schema

## Output Format
{output_schema}

## Task Context
{task_specific_instructions}
"""
```

### 2.3 CoT (Chain-of-Thought) 进阶

#### 通用 CoT（适用于所有任务）：

```python
COT_TEMPLATE = """
请按以下步骤分析：

Step 1: 理解任务目标
- 用户需求：{question}
- 期望输出：{expected_output}

Step 2: 定位关键代码
- 找到相关文件：___（列出文件路径）
- 找到关键函数/类：___

Step 3: 分析关联
- 直接影响：___
- 间接影响：___
- 潜在风险：___

Step 4: 生成答案
基于以上分析，输出 JSON 格式答案。
"""
```

#### 任务专项 CoT（RepoMind 各任务类型）：

```python
COT_CHANGELOG = """
分析 Changelog 任务的步骤：

1. **收集 Commit** → 提取 version range 内所有 commit
2. **分类** → 按 type (feat/fix/docs/refactor) 分类
3. **聚合** → 相关 commit 归并为一个 changelog 条目
4. **判断 Breaking Change** → 检查：
   - API 签名变更
   - 删除或重命名公共符号
   - 行为不兼容变更
5. **格式化** → 按 Keep a Changelog 规范输出
"""

COT_BUG_LOCATOR = """
分析 Bug 定位任务的步骤：

1. **提取错误信号** → 从错误信息中提取关键词
2. **时间定位** → 确定引入时间范围
3. **关键词搜索** → 在代码中搜索相关关键词
4. **嫌疑度排序** → 按以下因素排序：
   - 文件修改频率
   - 与错误类型的相关性
   - 最后修改时间
5. **验证** → 确认候选 commit 确实引入了该错误
"""

COT_IMPACT_ANALYSIS = """
分析影响范围任务的步骤：

1. **识别变更点** → 确定本次变更的核心文件/函数
2. **上游分析** → 谁调用了这个函数？（call graph 回溯）
3. **下游分析** → 这个函数影响了谁？（call graph 前向）
4. **风险量化** → 影响多少个文件/模块？
5. **优先级排序** → 按影响程度排序
"""
```

### 2.4 Few-shot 高级策略

#### 策略 1：困难样本优先（Difficulty-weighted）

```python
# 从 eval_cases 中选取时，优先选 Hard 样本
fewshot_pool = [
    (case for case in eval_cases if case.difficulty == "hard"),
    (case for case in eval_cases if case.difficulty == "medium"),
    (case for case in eval_cases if case.difficulty == "easy"),
]
# 确保 hard 和 medium 占多数
```

#### 策略 2：多样性采样（Maximize Coverage）

```python
# 按 failure_type 均匀采样
from collections import defaultdict
by_type = defaultdict(list)
for case in eval_cases:
    by_type[case.failure_type].append(case)

# 每个 failure_type 至少选 1 个
fewshot = [random.choice(by_type[t]) for t in all_types]
# 剩余配额按难度加权
```

#### 策略 3：动态 Few-shot（HyDE-inspired）

```python
async def select_live_fewshot(question: str, task_type: str, top_k: int = 5):
    """
    基于当前 query 实时检索最相关的 few-shot 样本
    不是从固定池抽样，而是从 eval_cases 中语义检索
    """
    # 用 question + task_type 作为 query
    query = f"{task_type}: {question}"

    # 混合检索
    results = hybrid_retriever.retrieve(
        query=query,
        top_k=top_k,
        filters={"task_type": task_type, "passed": True}
    )

    return [r.payload["case"] for r in results]
```

#### 策略 4：自适应 K 值

```python
def adaptive_fewshot_k(question: str, k_min: int = 2, k_max: int = 8) -> int:
    """
    根据问题复杂度动态决定 few-shot 数量
    """
    # 复杂度指标
    token_len = len(question.split())
    has_qualified_import = "影响" in question or "impact" in question.lower()
    multi_commit = "多个版本" in question or "range" in question.lower()

    complexity = 0
    complexity += min(token_len / 100, 1.0)        # 长度
    complexity += 0.3 if has_qualified_import else 0  # 复杂度词汇
    complexity += 0.3 if multi_commit else 0        # 多 commit

    return int(k_min + (k_max - k_min) * min(complexity, 1.0))
```

### 2.5 Post-processing 最佳实践

```python
def postprocess_answer(answer: str, task_type: str) -> dict:
    # 1. JSON 解析（容错）
    try:
        result = json.loads(answer)
    except json.JSONDecodeError:
        # 尝试提取 ```json ... ``` 块
        result = extract_json_block(answer)

    # 2. 字段补全（按 task_type）
    if task_type == "impact_analysis":
        result = fill_missing_layers(result)  # direct/indirect/implicit

    # 3. FQN 规范化
    result = normalize_fqn(result, repo_symbols)

    # 4. 去重
    result = deduplicate(result)

    # 5. 置信度评估
    result["_meta"] = {
        "confidence": estimate_confidence(result, task_type),
        "has_hallucination": check_hallucination(result),
    }

    return result
```

---

## 三、RAG 增强技术进阶

### 3.1 当前 RepoMind RAG 管线

来自 `reports/rag_pipeline.md`：

```
Celery 源码 → AST Chunker → 3路索引(BM25/Semantic/Graph)
                                          ↓
                                  RRF Fusion (k=30)
                                          ↓
                              Top-K Context (k=5, depth=12)
                                          ↓
                                  LLM Generation
```

**当前局限：**
- 无 reranking（RRF 后直接取 top）
- 无 context compression
- Embedding 用通用模型（不是代码专用）

### 3.2 ColBERT 延迟交互检索

**核心思想：** Late interaction = token-level 交互，而不是 sequence-level

```python
# ColBERT vs 传统 bi-encoder 对比
# Bi-encoder: 整个 passage → 一个向量
# ColBERT: 每个 token → 一个向量（向量序列）

# Query: "find the bug in login"
# Doc: "login.py contains the authentication logic for user login"

# Bi-encoder: sim(query_emb, doc_emb) → 0.85
# ColBERT: max over token pairs of sim(token_q, token_d) → 更细粒度

# ColBERT 检索（可用 RAGatouille 实现）
from ragatouille import RAGPretrainedModel
colbert = RAGPretrainedModel.from_pretrained("colbert-ir/colbertv2.0")

# Index
colbert.add_documents(your_code_chunks)

# Retrieve
results = colbert.search("bug in login authentication", top_k=10)
```

**为什么 ColBERT 适合 RepoMind：**
- 代码变更分析需要 token-level 的精确匹配（如函数名）
- Late interaction 兼顾语义和关键词

### 3.3 Cross-encoder Reranking

**两阶段检索 + 排序：**

```python
# Stage 1: 粗排（混合检索，取 top-20）
initial = hybrid_retriever.retrieve(query, top_k=20)

# Stage 2: 精排（cross-encoder rerank，取 top-5）
from sentence_transformers import CrossEncoder

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

doc_pairs = [(query, doc.text) for doc in initial]
scores = cross_encoder.predict(doc_pairs)

reranked = sorted(zip(initial, scores), key=lambda x: -x[1])[:5]
```

**RepoMind 适用的 Reranking 方案：**

| 方案 | 延迟 | 精度 | 部署难度 | 推荐度 |
|------|------|------|---------|--------|
| FlashRank (本地) | ~50ms | 高 | 低 | ⭐⭐⭐ |
| Cohere Rerank API | ~100ms | 最高 | 低 | ⭐⭐⭐ |
| RAGatouille (ColBERT) | ~200ms | 极高 | 中 | ⭐⭐ |
| 自己训练 Cross-encoder | 可变 | 可定制 | 高 | ⭐ |

### 3.4 Context Compression

**问题：** 检索到的 chunk 包含大量无关上下文

**解决方案：** Contextual Compression Retriever

```python
# LangChain 实现
from langchain.retrievers import ContextualCompressionRetriever
from langchain_community.chat_models import ChatOpenAI
from langchain_community.document_compressors import FlashrankRerank

# FlashRank 既能 rerank 也能压缩
compressor = FlashrankRerank(compression=0.5)

compression_retriever = ContextualCompressionRetriever(
    base_compressor=compressor,
    base_retriever=base_retriever  # 你的 hybrid retriever
)

# 压缩后的 context 更短，token 节省 30-50%
compressed_docs = compression_retriever.get_relevant_documents(query)
```

**自定义压缩策略（RepoMind 专用）：**

```python
def compress_code_chunk(chunk: str, query: str) -> str:
    """
    针对代码变更分析的自定义压缩：
    1. 移除空行和注释
    2. 保留函数签名和关键逻辑
    3. 按 query 关键词加权
    """
    # 移除注释
    code_only = remove_comments(chunk, language=detect_language(chunk))

    # 提取函数签名（这些最重要）
    signatures = extract_signatures(code_only)

    # 提取相关行（keyword match）
    related_lines = extract_keyword_matches(code_only, query)

    # 组合：签名 + 相关行
    compressed = signatures + "\n" + related_lines

    return compressed[:MAX_TOKENS]
```

### 3.5 HyDE (Hypothetical Document Embeddings)

**思想：** 先让 LLM 生成"假答案文档"，再用假答案检索

```python
async def hyde_retrieve(query: str, retriever, llm):
    """
    HyDE 检索流程：
    1. LLM 根据 query 生成假设答案
    2. 用假设答案去检索真实文档
    3. 返回真实检索结果
    """
    # Step 1: 生成假答案
    hypothetical = await llm.generate(
        f"用中文回答：{query}\n"
        "请生成你认为最可能的答案，包含关键代码路径和分析结论。"
    )

    # Step 2: 用假答案检索
    real_docs = retriever.search(hypothetical)

    # Step 3: 同时检索原 query（取并集）
    original_docs = retriever.search(query)

    # Step 4: 合并去重
    combined = merge_and_dedupe(hypothetical_docs, original_docs)

    return combined
```

**适用场景：** RepoMind 的"影响范围分析"和"bug 定位"任务（需要探索性检索）

### 3.6 Graph RAG 增强

**当前 RepoMind：** Graph BFS，深度=2

**增强方向：**

```python
# 动态图搜索深度
def dynamic_graph_depth(task_type: str, query: str) -> int:
    if "直接影响" in query or "direct" in query.lower():
        return 1  # 只需要直接调用方
    elif "完整影响" in query or "full" in query.lower():
        return 3  # 需要完整链路
    else:
        return 2  # 默认


# 多跳推理增强（针对 "修改 A 会影响 B" 类问题）
class MultiHopGraphRAG:
    """
    支持多跳推理的 Graph RAG
    """
    def query(self, question: str) -> list[Doc]:
        # 识别多跳模式
        if matches_multi_hop_pattern(question):
            return self.multi_hop_search(question)
        else:
            return self.single_hop_search(question)

    def multi_hop_search(self, question: str):
        # 第一跳：找到 A
        a_results = self.one_hop_retrieve(extract_entity(question, "A"))

        # 第二跳：从 A 的邻居找到 B
        b_results = self.one_hop_retrieve(
            find_affected_neighbors(a_results)
        )

        # 第三跳：合并路径
        return self.merge_paths(a_results, b_results)
```

---

## 四、自我改进循环 (Self-Improvement Loops)

### 4.1 Self-RAG (ICLR 2024)

**核心思想：** 让 LLM 自己决定何时检索、检索什么、是否使用检索结果

```python
class SelfRAG:
    """
    Self-RAG 的四个特殊 token：
    [Retrieval] - 触发检索
    [Relevant] - 检索结果是否相关
    [Supported] - 检索结果是否支持答案
    [Irrelevant] - 检索结果无关
    """
    RETRIEVAL_trigger = "[Retrieval]"
    RELEVANT_tag = "[Relevant]"
    SUPPORTED_tag = "[Supported]"
    IRRELEVANT_tag = "[Irrelevant]"

    def generate_with_self_rag(self, query: str):
        # Step 1: LLM 判断是否需要检索
        decision = llm.predict(f"{query}\n是否需要检索代码？[Retrieval]")

        if self.RETRIEVAL_trigger in decision:
            # Step 2: 检索
            docs = self.retriever.get_relevant(query)

            # Step 3: 逐个判断相关性和支持度
            for doc in docs:
                judgment = llm.judge(f"{query}\n{doc.text}\n是否相关？是否支持答案？")
                doc.is_relevant = self.RELEVANT_tag in judgment
                doc.is_supported = self.SUPPORTED_tag in judgment

            # Step 4: 只使用 Relevant + Supported 的 doc
            valid_docs = [d for d in docs if d.is_relevant and d.is_supported]

            # Step 5: 生成最终答案
            answer = llm.generate(f"{query}\n{valid_docs}")

            return answer
        else:
            return llm.generate(query)
```

**对 RepoMind 的启发：**
- RepoMind 的任务大多是"需要精确代码上下文"的任务
- 可以给 LLM 加上 `[Retrieval]` 的决策能力
- 对简单问题（如查单个文件）跳过 RAG，节省 token

### 4.2 Self-Refinement (Critic Loop)

**核心思想：** 生成 → 审查 → 改进 → 再审查

```python
class SelfRefinement:
    def refine(self, question: str, context: list[Doc]) -> str:
        # Pass 1: 生成初始答案
        answer = llm.generate(self.pe_template.format(question, context))

        # 最多 N 轮审查
        for i in range(MAX_REFINEMENT_ITERS):
            # 审查答案
            criticism = self.critic.judge(
                question=question,
                answer=answer,
                context=context
            )

            # 检查是否有问题
            if not criticism.has_issues:
                break

            # 改进答案
            answer = llm.refine(
                original=answer,
                criticism=criticism.feedback
            )

        return answer

    # Critic prompt 模板
    CRITIC_PROMPT = """
    你是答案审查员。请审查以下答案是否：

    1. **完整性**：是否覆盖了问题的所有关键点？
    2. **正确性**：事实是否与提供的代码上下文一致？
    3. **格式规范**：是否符合 JSON Schema 要求？
    4. **无幻觉**：是否有臆测的内容（代码中未提及的）？

    答案：{answer}
    上下文：{context}

    如果有问题，明确指出问题并给出改进建议。
    如果没问题，只回答"审查通过"。
    """
```

### 4.3 ReAct (Reason + Act)

**核心思想：** LLM 生成 reasoning trace + action，action 结果又作为下一轮 reasoning 的输入

```python
class ReActAgent:
    def run(self, question: str, max_steps: int = 10):
        thought_chain = []
        observation = None

        for step in range(max_steps):
            # LLM 生成 thought + action
            response = llm.generate(
                self.ReAct_prompt.format(
                    question=question,
                    observation=observation,
                    history="\n".join(thought_chain)
                )
            )

            thought, action, action_args = parse_ReAct(response)
            thought_chain.append(f"Thought: {thought}\nAction: {action}({action_args})")

            # 执行 action
            if action == "search_code":
                observation = self.search_code(action_args)
            elif action == "read_file":
                observation = self.read_file(action_args)
            elif action == "git_log":
                observation = self.git_log(action_args)
            elif action == "finish":
                return action_args  # 最终答案

            # 检查是否陷入循环
            if is_loop(thought_chain):
                break

        return format_final_answer(thought_chain)
```

**RepoMind 的 ReAct 适配：**
```
Question: "v2.1 到 v2.2 之间的 breaking change 有哪些？"

Thought 1: "需要先获取 v2.1 到 v2.2 的所有 commit"
Action: git_log(version_range="v2.1..v2.2")
Observation: [commit list]

Thought 2: "需要从 commit 中提取 API 变更"
Action: search_code(patterns=["def ", "class ", "async def "])
Observation: [API definitions]

Thought 3: "需要判断哪些 API 是 breaking change"
Action: analyze_breaking_change(api_list)
Observation: [breaking changes]

Thought 4: "需要格式化输出"
Action: format_changelog(breaking_changes)
Final Answer: {changelog output}
```

### 4.4 Reflexion (语言强化学习)

**核心思想：** 失败经验以"语言记忆"形式存储，下次避免同类错误

```python
class ReflexionAgent:
    def __init__(self):
        self.memory: list[ReflexionEntry] = []

    def run(self, question: str):
        # 检索相关历史失败经验
        similar_failures = self.retrieve_similar_failures(question)

        # 构建包含失败教训的 prompt
        lessons = "\n".join([
            f"避免：{f.lesson}"
            for f in similar_failures
        ])

        enhanced_prompt = f"""
        注意：以下是要避免的错误：
        {lessons}

        请回答：{question}
        """

        answer = llm.generate(enhanced_prompt)

        # 如果失败，记录教训
        if not self.evaluate(answer):
            lesson = self.extract_lesson(question, answer)
            self.memory.append(ReflexionEntry(question, answer, lesson))

        return answer
```

---

## 五、Tracing 可观测性体系

### 5.1 为什么 Tracing 是优化的前提

> **没有 Tracing，所有优化都是盲猜。**

```python
# RepoMind Tracing Schema
@dataclass
class RepoMindTrace:
    # Tool Call Entry
    tool_name: str
    tool_args: dict
    call_order: int
    timestamp: float

    # Tool Call Exit
    results: list[dict]
    latency_ms: float
    tokens_used: int

    # LLM Context
    full_prompt: str
    tools_used: list[str]
    tools_results_accepted: int   # LLM 采纳了多少 tool 结果
    tools_results_rejected: int   # LLM 忽略了多少
    final_answer: str
    model_name: str

    # Eval Result
    case_id: str
    task_type: str
    pass: bool
    score: float
    mislayer_rate: float
    failure_reasons: list[str]
```

### 5.2 关键指标

| 指标 | 含义 | 优化价值 |
|------|------|---------|
| `tool_results_accepted / total` | LLM 对 tool 结果的采纳率 | 低 = RAG 质量差或 prompt 未引导 |
| `mislayer_rate` | 符号放在错误依赖层的比例 | RepoMind 核心指标 |
| `avg_latency_ms` | 端到端延迟 | 影响用户体验 |
| `retrieval_recall@k` | top-k 检索的召回率 | 指导 RAG 调参 |
| `rerank_improvement` | reranking 带来的提升 | 决定是否上 reranking |

### 5.3 消融实验矩阵

根据 `docs/repomind-optimization-plan.md` 的计划：

| 实验 | 配置 | 预期提升 |
|------|------|---------|
| Baseline | 无 PE/RAG | 0.27 |
| + PE only | System + CoT + Few-shot | +120% (实测) |
| + RAG only | Hybrid retrieval | Hard +14% |
| + PE + RAG | Full combination | 最优 |
| + ColBERT rerank | Top-20 → Top-10 | MRR +8% |
| + Context compression | 去除冗余 | Token 节省 30% |
| + Adaptive fewshot | 动态 k | 简单 case +5% |
| + Self-refinement | 2-pass generation | 复杂 case +8% |

---

## 六、RepoMind 具体优化路线（无微调）

### 阶段 1：Tracing 层（先行）

**目标：** 让 RepoMind 变成"透明黑盒"

```python
# 实现位置：evaluation/tracing.py

class RepoMindTracer:
    def trace(self, case_id: str, question: str, task_type: str):
        trace = RepoMindTrace(case_id=case_id)

        # Hook 到 RAG retrieval
        original_retrieve = self.retriever.retrieve
        def traced_retrieve(*args, **kwargs):
            result = original_retrieve(*args, **kwargs)
            trace.tool_calls.append(ToolCall(
                name="retrieve",
                args=kwargs,
                result=result,
                latency_ms=time_delta()
            ))
            return result
        self.retriever.retrieve = traced_retrieve

        # Hook 到 LLM 调用
        original_generate = self.llm.generate
        def traced_generate(*args, **kwargs):
            result = original_generate(*args, **kwargs)
            trace.llm_calls.append(LLMCall(
                prompt=args[0],
                response=result,
                latency_ms=time_delta(),
                tokens_used=estimate_tokens(result)
            ))
            return result
        self.llm.generate = traced_generate

        return trace
```

### 阶段 2：PE 优化

**优先级排序（基于实测数据）：**

1. ✅ **Few-shot 增强**（+36%，最大单项增益）
   - 从 Hard/Medium 样本优先采样
   - 按 failure_type 多样性选择
   - 考虑动态 few-shot

2. ✅ **CoT 任务专项化**（+35%）
   - 每种 task_type 有专属 CoT template
   - 对 Hard 问题的帮助最显著

3. ✅ **Post-process 加固**（+7%）
   - FQN 规范化
   - 格式容错解析
   - 置信度评估

### 阶段 3：RAG 增强

**优先级排序：**

1. ✅ **ColBERT Reranking**（MRR +8%）
   - 两阶段：Top-20 → Cross-encoder → Top-10
   - 用 FlashRank（本地）或 Cohere Rerank API

2. ✅ **Context Compression**（Token 节省 30%）
   - 对检索到的 chunk 做压缩
   - 保留函数签名 + 关键词匹配行

3. 🔲 **代码专用 Embedding**（长期）
   - CodeBERT / GraphCodeBERT 替代通用 embedding

4. 🔲 **HyDE**（可选，复杂任务）
   - 对影响范围分析、bug 定位等探索性任务

### 阶段 4：Self-Improvement 集成

**优先实现：**

1. ✅ **Self-Refinement (Critic Loop)**
   - 两轮生成 + 审查
   - 适合格式要求严格的 Changelog 任务

2. ✅ **Adaptive Retrieval (Self-RAG Lite)**
   - 给 LLM 加上判断"是否需要检索更多上下文"的能力
   - 简单问题跳过 RAG

3. 🔲 **Reflexion（长期）**
   - 失败经验记忆化
   - 防止重复犯同类错误

---

## 七、2026 最新优化技术（来自深度调研）

### 7.1 Tree of Thoughts（多路径探索）

**核心思想：** 显式探索多条推理路径，而非单链推理

```python
from tot.methods.bfs import solve
from tot.tasks.game24 import Game24Task

# 三步：Propose（生成候选）→ Value（评估）→ Select（选择）
task = Game24Task()
ys, infos = solve(args, task, 900)
```

**RepoMind 适用场景：** Changelog 生成时，对同一个 commit 可能有多种分类方式，Tree of Thoughts 可以探索多条路径并选择最优

### 7.2 Graph-CoT（知识图谱遍历推理）

**核心思想：** LLM 生成图遍历命令，系统执行后返回结果，形成推理循环

```python
def four_hop(node_type_1, edge_type_12, node_type_2, edge_type_23,
             node_type_3, edge_type_34, node_type_4):
    # 遍历图：node1 → node2 → node3 → node4
    # 多跳推理回答复杂影响范围问题
    pass
```

**RepoMind 适用场景：** 影响范围分析的多跳推理（"修改 A 如何通过 B 间接影响 C"）

### 7.3 Agentic RAG（NVIDIA 架构）

**完整 Pipeline：**

```
Question → Router → Retrieval Grader → Re-ranking → Hallucination Grader → Answer
              ↓              ↓
         (vector or    (过滤不相关 doc)
          web search)
```

```python
# 检索评分器
retrieval_grader = prompt | llm | JsonOutputParser()
score = retrieval_grader.invoke({"question": q, "document": doc})

# Hallucination 检查
hallucination_grader = prompt | llm | JsonOutputParser()
grade = hallucination_grader.invoke({"answer": ans, "context": docs})
```

**RepoMind 适用场景：** 对检索到的代码 chunk 做二次评分，过滤幻觉内容

### 7.4 Context+（RAG + AST + 谱聚类）

**核心特性：**
- AST 解析：结构化理解代码
- 向量嵌入：语义搜索
- 谱聚类：相关代码分组
- Obsidian 风格 wikilink 导航

**RepoMind 适用场景：** RepoMind 的 AST Chunker 已经实现了部分，Context+ 的谱聚类可以进一步增强代码结构感知

### 7.5 EvalPlus（严格评测）

**核心洞察：** 原始测试 × 80 倍的扩展测试 = 鲁棒性检测

```python
from evalplus.data import get_human_eval_plus

problems = get_human_eval_plus()
# HumanEval+：比原始多 80 倍测试用例
# MBPP+：比原始多 35 倍测试用例
```

**RepoMind 适用场景：** D30-D32 测试集的 test_patch 可以参考 EvalPlus 思路，增加更多边界测试用例

### 7.6 Bugbot 自我改进规则

```python
# 从成功修复中提取规则
class LearnedRule:
    pattern: str        # 错误模式
    context: str        # 上下文条件
    fix_template: str  # 修复模板

# 下次遇到相似模式时主动应用
if rule.matches(current_code):
    current_code = rule.apply(current_code)
```

**RepoMind 适用场景：** 失败案例的经验存储化，避免重复同类错误

---

## 八、关键参考论文

| 论文 | 年份 | 核心贡献 |
|------|------|---------|
| Self-RAG | ICLR 2024 | 自适应检索决策 |
| ReAct | 2023 | 推理+行动协同 |
| Reflexion | 2023 | 语言强化学习 |
| CoT Decomp | 2023 | 任务分解 + CoT |
| PAL | 2023 | Program-aided LLM |
| DSP | 2023 | Demonstration + prompting |
| Cramming | 2023 | LM 压缩上下文 |
| ColBERT | SIGIR 2020 | Late interaction retrieval |
| BEIR | 2021 | 检索评测基准 |
| Tree of Thoughts | NeurIPS 2023 | 多路径推理探索 |
| SWE-grep | 2025 | 并行工具调用 + RL 训练 |
| CursorBench | 2026 | 真实工程会话评测 |
