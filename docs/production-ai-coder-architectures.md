# 生产级 AI Coder 系统架构调研报告

> 基于训练知识库（截至 2026-04）
> 整理：RepoMind AI Coder 优化调研

---

## 一、架构总览

### 1.1 主流 AI Coder 系统分类

| 系统 | 机构 | 形态 | 核心架构 |
|------|------|------|---------|
| **Devin** | Cognition AI | 云服务 | Sandbox + Planning Agent + Tool Pool |
| **GitHub Copilot** | Microsoft | IDE 插件 | Fill-in-the-middle + Codex 模型 |
| **Cursor** | Cursor AI | IDE | Composer + Context Pooling + Rules |
| **Claude Code** | Anthropic | CLI | 状态机 + 工具集 + 安全确认 |
| **OpenHands** | All-Hands-AI | 开源 | 多 Agent 协作 + Sandbox |
| **SWE-agent** | Princeton NLP | 学术 | Retriever + Critic + Editor |

### 1.2 通用 AI Coder 架构模板

```
┌─────────────────────────────────────────────┐
│              User Request                    │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│          Context Engineering                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐   │
│  │ Project │ │ Session │ │ Task        │   │
│  │ Summary │ │ Memory  │ │ Specific   │   │
│  └─────────┘ └─────────┘ └─────────────┘   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│              Task Routing                    │
│         (intent classification)              │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│          Retrieval (RAG/Graph)              │
│  ┌───────┐ ┌───────┐ ┌────────┐ ┌──────┐  │
│  │ BM25  │ │Vector │ │ Import │ │ AST  │  │
│  │       │ │Search │ │ Graph  │ │ Parse│  │
│  └───────┘ └───────┘ └────────┘ └──────┘  │
│           ↓ RRF / Cross-encoder             │
│         Top-K Context Chunks                │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│          Prompt Engineering                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐   │
│  │ System   │ │ CoT      │ │ Few-shot  │   │
│  │ Prompt   │ │ Template  │ │ Examples  │   │
│  └──────────┘ └──────────┘ └───────────┘   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│           LLM Inference                     │
│  ┌─────────────────────────────────────┐   │
│  │  Tool Use Loop (if multi-tool)      │   │
│  │  Self-Refinement (if enabled)       │   │
│  └─────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│          Post-Processing                    │
│  JSON Parse → Validation → Deduplication    │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│          Evaluation / Logging               │
│  Tracing → Metrics → Feedback Loop          │
└─────────────────────────────────────────────┘
```

---

## 二、Devin 架构深度解析

### 2.1 核心设计理念

Devin 是第一个商业化的端到端 SWE Agent，其架构对行业影响最深。

```
Devin Pipeline:
Issue → [Planner] → [Browser/Git/Terminal Tools] → [Sandbox] → [Self-Verify] → PR
         ↑
    Sub-agent decomposition
```

**关键创新：**
1. **Sandbox 环境隔离**：每次修改在独立沙箱中验证，不污染主分支
2. **长期记忆**：跨会话保留项目上下文
3. **透明可审计**：每个操作步骤可追溯，用户可随时接管

### 2.2 Devin 的工具池设计

```python
# Devin 核心工具集
class DevinToolPool:
    - WebSearch: 搜索文档/解决方案
    - Browser: 网页交互（读取文档、提交 PR）
    - Bash: 终端命令执行
    - Editor: 细粒度代码修改
    - Git: 版本控制操作
    - CodeSearch: 代码库检索
```

**工具调用策略：**
- 每轮 LLM 输出一个 action + args
- 执行后 observation 反馈给 LLM
- 最大步数限制防止无限循环

### 2.3 Devin 的 Sandbox 设计

```
┌──────────────────────────────────────┐
│         Devin Cloud Sandbox          │
│  ┌────────────────────────────────┐  │
│  │  Ubuntu + 预装开发工具链        │  │
│  │  - git, python, node, etc.     │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  Ephemeral Filesystem          │  │
│  │  (每次任务新建，不污染主代码)    │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  Test Execution Engine         │  │
│  │  (支持 pytest, unittest 等)     │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

---

## 三、GitHub Copilot 架构

### 3.1 Fill-in-the-Middle (FIM)

Copilot 的核心补全基于 FIM 策略，不是纯 Autocomplete：

```
Prefix + [FIM Insert] + Suffix → LLM → Predicted Code
```

**优势：**
- 知道上下文的"中间"需要填什么
- 比纯 left-to-right 生成更准确

### 3.2 Copilot Chat 的多模态架构

```
User Query (in IDE)
  → Context Extraction (当前文件、选中代码、项目结构)
  → LLM (Codex/GPT-4)
  → Inline Response / Fix Suggestion
```

**Context 构建策略：**
1. **最近文件**：LSP 提供的邻近文件
2. **显式选择**：用户高亮的代码
3. **隐式项目**：基于 imports/resolves 的项目图

---

## 四、Cursor 架构

### 4.1 Composer（多文件编辑器）

Cursor 的 Composer 是业界最复杂的多文件编辑实现：

```
User Intent: "Refactor the auth module"
     ↓
[Composer Agent]
  ├─ 读取 auth/__init__.py
  ├─ 读取 auth/user.py
  ├─ 读取 auth/permissions.py
  ├─ 分析依赖关系
  └─ 生成 N 个文件变更
     (按 dependency order 排序)
```

**关键特性：**
- **Dependency ordering**：按 import 顺序依次修改，避免中间状态冲突
- **Context chunks**：将项目结构化为固定大小的 context 单位
- **Non-destructive**：优先 edit 而非 replace，减少噪声

### 4.2 Cursor Rules (`.cursorrules`)

```json
// .cursorrules 示例
{
  "rules": [
    {
      "match": "**/*.py",
      "prompt": "You are a Django expert. Follow Django best practices."
    }
  ]
}
```

**对 RepoMind 的启发：**
RepoMind 可以引入类似的仓库级 `repomind_rules.json`：
```json
{
  "rules": [
    {
      "task_type": "changelog",
      "prompt_addon": "聚焦 breaking change 和新特性"
    },
    {
      "task_type": "impact_analysis",
      "prompt_addon": "优先分析直接调用方"
    }
  ]
}
```

---

## 五、Claude Code 架构

### 5.1 安全优先的状态机

Claude Code 的 agent loop 是目前最严谨的：

```
States: pending → executing → pending_confirmation → completed

每次 LLM 调用返回：
{
  "action": "Bash" | "Read" | "Edit" | "Notebook" | "WebSearch",
  "args": {...},
  "confirmation_reason": "This will run `rm -rf node_modules`"
}

如果危险操作 → pause + user confirmation
```

### 5.2 项目配置注入

Claude Code 读取项目根目录的配置文件：
- `.claude/`：默认项目配置
- `CLAUDE.md`：项目说明文档（自动注入上下文）
- `.cursorrules`（兼容）：项目级提示规则

**对 RepoMind 的启发：**
```
RepoMind 可自动读取仓库根目录的：
- `.repomind/config.json`：仓库级任务配置
- `CHANGELOG.md`：已有的 changelog 格式参考
- `docs/`：项目文档作为背景知识
```

---

## 六、OpenHands 多 Agent 协作架构

### 6.1 Agent 分工

```python
class OpenHandsArchitecture:
    PlannerAgent:
        - 将用户请求分解为步骤
        - 输出 action plan

    ActionAgent:
        - 执行具体操作
        - 调用工具

    CriticAgent:
        - 审查 plan / action 的合理性
        - 防止 hallucination

    MemoryAgent:
        - 跨会话存储项目状态
        - 维护项目知识图谱
```

### 6.2 协作流程

```
User: Fix the login bug

[Planner] → "需要：1) 复现 bug  2) 定位代码  3) 修复  4) 测试验证"
     ↓
[Action: Browser] → 打开登录页面复现
     ↓
[Critic] → "复现成功，错误在 password validation"
     ↓
[Action: Editor] → 修改 validation 代码
     ↓
[Action: Bash] → 运行测试
     ↓
[Critic] → "测试通过，方案合理"
     ↓
PR created
```

---

## 七、SWE-agent 检索增强架构

### 7.1 双路检索

SWE-agent 使用两路检索而非单一向量检索：

```python
class SWEagentRetriever:
    BM25:
        - keyword exact match
        - 处理 API 重命名/移动

    Dense Passage Retrieval (DPR):
        - 语义相似性
        - 处理逻辑重构

    fusion:
        - RRF (Reciprocal Rank Fusion)
        - k=60 平衡两种信号
```

### 7.2 Critic Loop

```python
class CriticLoop:
    def generate(self, context, query):
        # Step 1: LLM 生成答案
        answer = llm.generate(context, query)

        # Step 2: Critic 审查
        criticism = llm.criticize(answer, query)

        # Step 3: 如果有批评，重新生成
        if criticism.has_issues:
            answer = llm.refine(answer, criticism)

        return answer
```

---

## 八、上下文管理策略

### 8.1 分层上下文

```
┌─────────────────────────────────────────┐
│ Layer 1: System Prompt (固定, ~500 tokens) │
├─────────────────────────────────────────┤
│ Layer 2: Project Summary (中等, ~2000)     │
├─────────────────────────────────────────┤
│ Layer 3: Session Memory (动态, ~4000)      │
├─────────────────────────────────────────┤
│ Layer 4: Task Context + RAG (~8000)      │
├─────────────────────────────────────────┤
│ Layer 5: scratchpad (工作区, ~2000)       │
└─────────────────────────────────────────┘
```

### 8.2 项目摘要压缩

将项目结构压缩为固定 token 的摘要：

```python
# 项目摘要模板
project_summary = f"""
Repository: {repo_name}
Language: {language}
Key Modules:
{module_tree}
Public APIs:
{exported_symbols}
Recent Changes:
{recent_commits_summary}
"""
```

### 8.3 动态 Context Window 分配

| 任务类型 | System | Summary | RAG | scratchpad |
|---------|--------|---------|-----|-----------|
| Bug 定位 | 500 | 1500 | 6000 | 2000 |
| Changelog | 500 | 2000 | 5000 | 3000 |
| 影响分析 | 500 | 2500 | 7000 | 1500 |

---

## 九、对 RepoMind 架构演进的建议

### 9.1 当前 RepoMind 痛点

根据 `docs/repomind-optimization-plan.md` 分析：

| 任务 | 基线 | 主要瓶颈 |
|------|------|---------|
| Changelog | ~20% | 工具调用顺序 + 格式 |
| 安全审计 | ~70% | 格式规范 |
| Bug 定位 | ~65% | commit 关联断裂 |
| 影响分析 | ~45% | 依赖链路不完整 |

### 9.2 借鉴各系统优势的整合方案

**参考 Devin → 引入 Sandbox/验证反馈：**
- Changelog 生成后，自动运行 `git log` 验证
- Bug 定位后，提示用户运行测试确认

**参考 OpenHands → Planner/Critic 分离：**
- Planner：决定调用哪个工具、调用顺序
- Critic：审查输出的完整性和格式

**参考 SWE-agent → 双路检索强化：**
- 当前 RepoMind 有 BM25 + Semantic + Graph
- 补充代码专用 DPR（CodeBERT/GraphCodeBERT 编码）

**参考 Claude Code → 安全确认机制：**
- 对破坏性分析（涉及删除、breakage）增加确认步骤
- 提供 confidence 分数，让用户判断是否可信

**参考 Cursor Rules → 仓库级配置：**
- `.repomind/config.json`：仓库专属任务提示
- 自动读取项目 CHANGELOG.md 格式作为参考

### 9.3 RepoMind Target 架构

```
                    Query
                      │
              ┌───────┴───────┐
              │  Task Router  │
              │ (task_type)   │
              └───────┬───────┘
                      │
     ┌────────────────┼────────────────┐
     ▼                ▼                ▼
┌─────────┐    ┌────────────┐   ┌───────────┐
│Changelog│    │Bug Locator │   │ Impact    │
│ Handler │    │ Handler    │   │ Analyzer  │
└────┬────┘    └─────┬──────┘   └─────┬─────┘
     │               │                 │
     ▼               ▼                 ▼
┌─────────────────────────────────────────┐
│        Hybrid Retriever (NCP-specific)   │
│  BM25 + Semantic + Graph + AST         │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│          PE Engine (per task type)      │
│  System Prompt + CoT + Task Few-shot    │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│         NCP LLM Inference               │
│         (Claude/GPT-4)                  │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│     Post-Processor + Confidence Score   │
│     + RepoMind Rules Validator          │
└──────────────────┬──────────────────────┘
                   ▼
              Final Answer
```

---

## 十、2026 最新架构创新（来自深度调研）

### 10.1 并行工具调用（SWE-grep, 2025-10）

**核心突破：** 每轮最多 8 个并行工具调用，最多 4 轮串行（3 轮探索 + 1 轮答案）

```python
# 传统：串行调用（10-20 轮）
for call in sequential_calls:
    result = execute(call)
    context += result

# SWE-grep：每轮最多 8 并行
parallel_calls = await gather(*[execute(call) for call in batch])
# 延迟从分钟级 → 秒级（Cerebras 推理 2800 tok/s）
```

**RepoMind 启发：** 将 RAG 检索 + BM25 查询 + AST 解析并行化

### 10.2 CursorBench — 真实工程会话评测（2026-03）

**为什么重要：** 公开 Benchmark（SWW-bench/HumanEval）任务过于明确，真实开发场景更模糊：

- **SWE-bench**：任务预先指定，解决方案窄
- **CursorBench**：真实 Cursor 工程团队的 coding sessions，prompt 简短模糊，解决方案需要数百行跨多文件

**CursorBench 数据：**
- Composer 2 得分 61.3（2026-03）
- 相比 Composer 1.5 提升 37%
- 准确率 vs 成本达到帕累托最优

**RepoMind 启发：** 构建类似 CursorBench 的真实评测集，D30-D32 状态机测试集正是这个方向

### 10.3 Model UX — SWE-1.6（2026-04）

**核心概念：** 传统 Benchmark 不测量以下维度：

- Overthinking（简单问题想太多）
- Looping（重复尝试同一路径）
- 工具偏好错误（应该用 native tool 却用 terminal）
- 串行 vs 并行工具调用

**SWE-1.6 解决方案：** RL 训练中加入 length penalty，降低不必要的长轨迹

**RepoMind 启发：** RepoMind 的 PE + Postprocess 正是减少 overthinking 的手段

### 10.4 GitHub Agentic Workflows 安全架构（2026-03）

**四大安全原则：**
1. **Defense in depth**（多层防御）
2. **Don't trust agents with secrets**（零密钥架构）
3. **Stage and vet all writes**（分期写入审批）
4. **Log everything**（全量日志）

**零密钥 Agent 架构：**
```
Agent Container
  ↕ firewalled internet + MCP gateway
  ↕ Auth tokens in isolated API proxy
  ↕ chroot jail at /host with read-only filesystem
```

**RepoMind 启发：** RepoMind 分析代码仓库时，不应将写入能力暴露给 LLM

### 10.5 Bugbot 自我改进规则（2026-04）

**创新：** 从成功修复中提取模式，存储为规则，下次主动应用

```python
# 规则存储格式
class LearnedRule:
    pattern: str          # "空指针检查缺失"
    context: str          # "在 if 语句后立即检查"
    fix_template: str     # "添加 if (ptr == nullptr) 检查"

# Bugbot 在提交前主动检查
for rule in learned_rules:
    if rule.matches(code_change):
        code_change = rule.apply(code_change)
```

**RepoMind 启发：** 失败案例的经验存储化（Reflexion 思路）

### 10.6 三工程模式（GitHub, 2026-02）

**多 Agent 可靠性设计模式：**

1. **Typed schemas at every boundary**：机器可检查的数据契约
2. **Action schemas define explicit allowed actions**：`request-more-info` / `assign` / `close-as-duplicate` / `no-action`
3. **MCP enforces both**：执行前验证，防止坏状态传播

**RepoMind 启发：** NCP 的 task_type 路由 + Schema 验证正是此模式

### 10.7 Vercel Agentic Infrastructure（2026-04）

**核心数据：**
- 30% 周部署由 AI Agent 发起（6 个月增长 1000%）
- Agent 部署的项目 20x 更可能调用 AI 推理提供商
- Claude Code 占 Vercel 平台 75% Agent 驱动部署

**三层演进：**
```
Layer 1: Agent 部署基础设施（不可变部署 + Preview URL）
Layer 2: Agent 构建和运行基础设施（AI SDK + AI Gateway + Sandbox）
Layer 3: Agentic 平台自身（自动调查异常 + 根因分析 + 修复建议）
```

---

## 十一、关键参考论文

| 论文 | 年份 | 机构 | 核心贡献 |
|------|------|------|---------|
| SWE-bench | 2024 | Princeton | AI Coder 评测标准 |
| Toolformer | 2023 | Meta | 工具调用 LLM 训练 |
| RESTGPT | 2023 | UIUC | 接地气的 LLM 规划 |
| ChatGPT-Plugins | 2023 | OpenAI | Tool use in GPT |
| HuggingGPT | 2023 | Microsoft | LLM as controller |
| AutoGPT/PAL | 2023 | 社区 | 自主 agent 范式 |
| ReAct | 2023 | Princeton | Synergizing reasoning + acting |
| Reflexion | 2023 | NEU | 语言强化学习 agent |
| Self-RAG | 2024 | Carnegie Mellon | 自适应检索增强 |
| SWE-grep | 2025 | Cognition | 并行工具调用 + RL 训练 |
| CursorBench | 2026 | Cursor AI | 真实工程会话评测 |
| SWE-1.6 | 2026 | Cognition | Model UX 训练目标 |
