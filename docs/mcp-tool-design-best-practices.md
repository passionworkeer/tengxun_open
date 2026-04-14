# MCP/NCP 工具设计最佳实践

> 整理自 MCP 官方规范 + RepoMind NCP 实践经验
> 注：本 repo 将 MCP 和 NCP 并列参考，RepoMind 当前使用 NCP

---

## 一、协议概述

### 1.1 MCP vs NCP

| 维度 | MCP (Model Context Protocol) | NCP (Node Context Protocol) |
|------|------------------------------|------------------------------|
| **发起方** | LLM 主动调用工具 | Host 主动调度工具 |
| **上下文** | 按需注入 | 批量预注入 |
| **适用场景** | 通用 AI 应用 | RepoMind 代码分析 |
| **生态** | Anthropic 主导，生态成熟 | 腾讯内部定制 |
| **规范** | JSON-RPC 2.0 over stdio/SSE/HTTP | JSON-RPC 2.0，类 MCP |
| **工具发现** | `tools/list` 动态发现 | 固定工具集 |

### 1.2 MCP 核心架构

```
┌─────────────────────────────────────────────────┐
│                   LLM (Client)                   │
│  ┌──────────────────────────────────────────┐   │
│  │  Thinking: 根据 user query 决定调用哪个 tool │   │
│  └──────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────┘
                       │ JSON-RPC 2.0
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌───────────┐   ┌───────────┐   ┌───────────┐
│  MCP      │   │  MCP      │   │  MCP      │
│  Server A │   │  Server B │   │  Server C │
│ (RepoMind)│   │ (Search)  │   │ (Git)     │
└───────────┘   └───────────┘   └───────────┘
```

---

## 二、Tool Schema 设计规范

### 2.1 JSON Schema 基础结构

**MCP 官方推荐的 Tool Schema（`modelcontextprotocol/spec`）：**

```json
{
  "name": "tool_name",
  "description": "工具的完整描述。LLM 靠这个决定何时调用。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "arg_name": {
        "type": "string",
        "description": "参数描述，要说清楚用途和格式要求"
      }
    },
    "required": ["arg_name"]
  }
}
```

### 2.2 RepoMind NCP Tool Schema 规范

RepoMind 作为 NCP 工具，每个 task_type 对应独立 handler：

```python
# === Changelog 工具 ===
class RepoMindChangelogTool:
    name = "repomind_changelog"
    description = """
生成两个版本之间的 Changelog，包含：
- 新特性（feat）
- 修复（fix）
- Breaking Change（使用 ! 标记）
- 文档变更（docs）
- 重构（refactor）

适用于版本发布前的变更总结，或 Code Review 时的变更说明。
    """.strip()

    input_schema = {
        "type": "object",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "仓库地址，如 https://github.com/celery/celery"
            },
            "from_version": {
                "type": "string",
                "description": "起始版本 tag，如 v4.0"
            },
            "to_version": {
                "type": "string",
                "description": "目标版本 tag，如 v4.1"
            },
            "focus_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "可选：聚焦特定模块，如 ['tasks', 'worker']",
            }
        },
        "required": ["repo_url", "from_version", "to_version"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "changelog": {
                "type": "object",
                "properties": {
                    "breaking_changes": {"type": "array"},
                    "features": {"type": "array"},
                    "bug_fixes": {"type": "array"},
                    "other_changes": {"type": "array"},
                }
            },
            "confidence": {"type": "number"},
            "cited_commits": {"type": "array"},
        }
    }


# === Bug 定位工具 ===
class RepoMindBugLocatorTool:
    name = "repomind_bug_locator"
    description = """
给定错误描述或错误信息，定位最可能导致该 Bug 的代码位置和 commit。

分析策略：
1. 关键词提取 + 代码搜索
2. 时间范围定位（最近修改的相关文件）
3. 嫌疑度排序（按修改频率 + 相关性）
4. commit 详情验证

输出包含：文件路径、行号、commit hash、修改者、时间、修改原因。
    """.strip()

    input_schema = {
        "type": "object",
        "properties": {
            "repo_url": {"type": "string"},
            "error_message": {
                "type": "string",
                "description": "错误信息，如 'TypeError: Cannot read property x of undefined'"
            },
            "file_path": {
                "type": "string",
                "description": "可选：已知出错的文件路径"
            },
            "time_range": {
                "type": "string",
                "description": "可选：时间范围，如 'last 30 days'"
            }
        },
        "required": ["repo_url", "error_message"]
    }


# === 影响范围分析工具 ===
class RepoMindImpactAnalyzerTool:
    name = "repomind_impact_analyzer"
    description = """
分析代码变更的影响范围。

输出三层依赖：
1. direct_deps（直接依赖层）
2. indirect_deps（间接依赖层）
3. implicit_deps（隐式依赖层，如字符串引用、反射调用）

适用于：
- 修改公共 API 前的风险评估
- 重构前的影响分析
- 安全审计中的受影响范围评估
    """.strip()

    input_schema = {
        "type": "object",
        "properties": {
            "repo_url": {"type": "string"},
            "source_file": {"type": "string"},
            "symbol_name": {"type": "string"},
            "depth": {
                "type": "integer",
                "description": "分析深度，默认 2",
                "default": 2
            }
        },
        "required": ["repo_url", "source_file", "symbol_name"]
    }
```

---

## 三、工具描述（description）写作规范

### 3.1 description 是 LLM 决策的核心依据

description 的三个层次：

```python
# 层次 1：WHAT - 工具做什么
what = """
搜索 Git 仓库中的提交历史。
"""

# 层次 2：WHEN - 何时使用
when = """
在以下情况使用此工具：
- 用户询问某个功能的历史变更
- 需要找出特定 bug 的引入 commit
- 版本间的变更分析
"""

# 层次 3：HOW - 如何使用（简要）
how = """
输入版本范围或关键词，返回匹配的 commit 列表。
每个 commit 包含：hash、author、date、message、files_changed。
"""

# 完整 description
full_description = what + "\n" + when + "\n" + how
```

### 3.2 常见反模式

```python
# ❌ 反模式 1：太简短，LLM 无法判断何时调用
name = "search_code"
description = "Search code"

# ❌ 反模式 2：description 描述的是输出，不是功能
description = "Returns a list of matching commits with hashes"

# ❌ 反模式 3：与系统提示冲突
# System: "You are a helpful assistant"
# Tool: "You are a code analysis expert"  ← 角色冲突！

# ❌ 反模式 4：参数描述不清晰
description = "Filter commits by author or file pattern"
properties = {
    "filter": {"type": "string"}  # filter 是什么？格式？可选值？
}

# ✅ 正例
description = """
Search Git repository commits.

When to use:
- Finding commits related to a specific file or function
- Identifying when a bug was introduced
- Retrieving commit history for changelog generation

Returns: List of commits, each with hash, author, date, message, and changed files.
"""
properties = {
    "repo_url": {"type": "string", "description": "..."},
    "query": {"type": "string", "description": "Search query, supports git log syntax"},
    "max_results": {"type": "integer", "description": "Max results, default 50"}
}
```

### 3.3 description 写作 Checklist

- [ ] 说明工具能做什么（1-2 句话）
- [ ] 说明何时应该调用（2-3 个场景）
- [ ] 说明输出格式和数据结构
- [ ] 说明任何限制或注意事项
- [ ] 参数 description 说明类型 + 含义 + 格式要求 + 默认值

---

## 四、参数设计规范

### 4.1 参数类型约束

```json
{
  "properties": {
    "version": {
      "type": "string",
      "description": "版本号，格式：v1.0 或 1.0.0"
    },
    "depth": {
      "type": "integer",
      "description": "递归深度，范围 1-5，默认 2"
    },
    "include_tests": {
      "type": "boolean",
      "description": "是否包含测试文件，默认 false"
    },
    "focus_modules": {
      "type": "array",
      "items": {"type": "string"},
      "description": "聚焦的模块列表，如 ['worker', 'tasks']"
    }
  },
  "required": ["version"]
}
```

### 4.2 参数数量控制

**推荐：** 最多 5-7 个参数

```python
# ❌ 参数过多（8+）
input_schema = {
    "properties": {
        "repo_url": {...},
        "from_version": {...},
        "to_version": {...},
        "focus_areas": {...},
        "depth": {...},
        "include_tests": {...},
        "include_docs": {...},
        "max_results": {...},
        "timeout": {...},
    },
    "required": ["repo_url", "from_version", "to_version"]
}

# ✅ 合理拆分
# 用 focus_areas 代替多个布尔开关
# 超大参数用 dict/object 包裹
```

### 4.3 required 字段策略

**原则：** 必填参数应该是"完成任务所必需的最小集"

```python
# 对于 changelog，版本范围是必需的，但 focus_areas 是可选的
required = ["repo_url", "from_version", "to_version"]

# 如果有太多必填项，考虑：
# 1. 拆分工具（拆成多个小工具）
# 2. 使用嵌套 object 减少顶层字段
properties = {
    "options": {
        "type": "object",
        "properties": {
            "focus_areas": {...},
            "include_tests": {...},
            "depth": {...}
        }
    }
}
```

---

## 五、返回结构设计

### 5.1 统一返回格式

```python
@dataclass
class ToolResult:
    """所有工具的返回格式规范"""
    success: bool                    # 是否成功
    data: Any                       # 业务数据（失败时为 null）
    error: str | None               # 错误信息（成功时为 null）
    meta: ToolResultMeta             # 元信息

@dataclass
class ToolResultMeta:
    tool_name: str
    latency_ms: float
    tokens_used: int | None
    citations: list[Citation] | None  # 引用的文件/commit

# citations 用于答案可溯源
@dataclass
class Citation:
    type: Literal["file", "commit", "symbol"]
    path: str
    line_range: tuple[int, int] | None
    description: str
```

### 5.2 任务专项返回

```python
# Changelog 返回
@dataclass
class ChangelogResult(ToolResult):
    data: ChangelogData | None

@dataclass
class ChangelogData:
    breaking_changes: list[ChangeItem]
    features: list[ChangeItem]
    bug_fixes: list[ChangeItem]
    other_changes: list[ChangeItem]

@dataclass
class ChangeItem:
    summary: str                     # 简短描述
    detail: str                      # 详细描述
    commits: list[str]               # 涉及的 commit hash
    impact_scope: str                # 影响范围
    breaking_severity: str | None    # "high"/"medium"/"low"，仅 breaking_change 有


# Bug 定位返回
@dataclass
class BugLocationResult(ToolResult):
    data: list[BugCandidate]

@dataclass
class BugCandidate:
    file_path: str
    line_range: tuple[int, int]
    commit_hash: str
    author: str
    date: str
    confidence: float                # 0-1，可信度
    reasoning: str                   # 为什么认为是这个


# 影响分析返回
@dataclass
class ImpactAnalysisResult(ToolResult):
    data: ImpactGraph

@dataclass
class ImpactGraph:
    direct_deps: list[DepNode]       # 直接依赖
    indirect_deps: list[DepNode]     # 间接依赖
    implicit_deps: list[DepNode]     # 隐式依赖
    total_affected_files: int
    risk_level: Literal["high", "medium", "low"]

@dataclass
class DepNode:
    fqn: str                         # 完全限定名
    file_path: str
    dep_type: str                    # "import"/"call"/"string_ref"
    is_public_api: bool
```

---

## 六、NCP 特有设计考量

### 6.1 task_type 路由

NCP 的核心差异是"Host 主动调度"，因此 task_type 字段至关重要：

```python
# NCP 请求格式
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "repomind",
        "arguments": {
            "task_type": "changelog",  # 路由键
            "repo_url": "...",
            "from_version": "v2.1",
            "to_version": "v2.2"
        }
    }
}
```

**task_type 枚举（当前）：**
- `changelog`：版本变更日志生成
- `security_audit`：安全漏洞审计
- `bug_location`：Bug 定位
- `impact_analysis`：影响范围分析
- `version_diff`：版本差异对比
- `history_analysis`：历史影响分析

### 6.2 批量预注入上下文

NCP 的"批量预注入"模式适合 RepoMind：

```python
# Host 在调用前预先注入上下文
class NCPContextBuilder:
    def build_context(self, task_type: str, repo_url: str, query: str) -> dict:
        # 1. 拉取仓库元信息
        meta = self.git_client.get_repo_meta(repo_url)

        # 2. 预填充项目摘要（不依赖 LLM 调用）
        project_summary = self.summarizer.summarize(meta)

        # 3. 按 task_type 预填充相关上下文
        if task_type == "changelog":
            # 预填充历史 changelog 作为格式参考
            context = {
                "project_summary": project_summary,
                "historical_changelogs": meta.changelogs,
                "version_tags": meta.tags,
            }
        elif task_type == "impact_analysis":
            # 预填充 call graph
            context = {
                "project_summary": project_summary,
                "call_graph": self.graph_index.get_full_graph(),
                "public_apis": meta.public_symbols,
            }

        return context

        # LLM 调用时，直接传入预填充的 context
        # 节省了 LLM 主动调用工具的时间
```

### 6.3 NCP vs MCP 互操作建议

**目标：** RepoMind NCP Schema 与 MCP 生态对齐，降低未来迁移成本

```python
# 策略：NCP Schema 兼容 MCP 格式
class NCPCompatibleSchema:
    """
    RepoMind NCP Schema 设计时兼容 MCP 规范：
    1. name 字段用下划线（mcp standard）
    2. description 遵循 MCP 写作规范
    3. inputSchema 用 JSON Schema draft-07
    4. 返回结构兼容 MCP resource 格式
    """

    # MCP 的 tool schema
    MCP_STYLE = {
        "name": "repomind_changelog",
        "description": "...",
        "inputSchema": {
            "type": "object",
            "properties": {...}
        }
    }

    # NCP 特有扩展
    NCP_EXTENSIONS = {
        "task_type": "changelog",
        "batch_preload": True,  # NCP 特有的预加载标记
    }
```

---

## 七、工具调用 Loop 设计

### 7.1 单轮 vs 多轮

```python
# 单轮（简单任务）
# LLM → tool → answer
# 适用：单一查找、格式化输出

# 多轮（复杂任务）
# LLM → tool → observation → LLM → tool → observation → ... → answer
# 适用：多步分析、探索性检索

class RepoMindToolLoop:
    MAX_ITERS = 5  # 防止无限循环

    def run(self, question: str, task_type: str):
        messages = [
            SystemMessage(content=self.get_system_prompt(task_type)),
            UserMessage(content=question),
        ]

        for i in range(self.MAX_ITERS):
            # LLM 判断下一步
            response = self.llm.chat(messages)

            if response.tool_calls:
                # 执行工具
                for call in response.tool_calls:
                    result = self.execute_tool(call.name, call.arguments)
                    messages.append(ToolMessage(content=result, call_id=call.id))
            else:
                # 没有工具调用，检查是否应该结束
                if self.is_final_answer(response):
                    return response.content
                else:
                    # LLM 说不清楚，继续追问
                    messages.append(UserMessage(content="请继续分析"))

        return self.fallback_format(messages)
```

### 7.2 工具调用安全

```python
# 安全审查
class ToolSafetyChecker:
    DANGEROUS_OPERATIONS = ["git push --force", "rm -rf", "DROP TABLE"]

    def check(self, tool_name: str, arguments: dict) -> SafetyResult:
        # 1. 工具白名单检查
        if tool_name not in self.allowed_tools:
            return SafetyResult(allowed=False, reason="tool not in whitelist")

        # 2. 参数格式检查
        if not self.validate_schema(tool_name, arguments):
            return SafetyResult(allowed=False, reason="invalid arguments")

        # 3. 危险操作检查
        for dangerous_op in self.DANGEROUS_OPERATIONS:
            if dangerous_op in str(arguments):
                return SafetyResult(
                    allowed=False,
                    reason=f"dangerous operation: {dangerous_op}"
                )

        return SafetyResult(allowed=True)

    def on_blocked(self, tool_name: str, reason: str):
        # 记录 + 通知 + 用户确认
        logger.warning(f"Blocked tool call: {tool_name}, reason: {reason}")
        return f"[Blocked: {reason}]"
```

---

## 八、最佳实践 Checklist

### Tool Schema
- [ ] 每个工具 name 唯一，用下划线命名
- [ ] description ≥ 200 字，涵盖 WHAT/WHEN/HOW
- [ ] 参数 ≤ 7 个，必填参数为最小集
- [ ] 参数 description 说明类型 + 含义 + 格式
- [ ] inputSchema 使用 JSON Schema draft-07

### 返回格式
- [ ] 统一 `success/data/error/meta` 结构
- [ ] 包含 `confidence` 字段
- [ ] 包含 `citations` 用于答案溯源
- [ ] 错误信息对用户友好，不泄露内部细节

### NCP 特有
- [ ] task_type 作为路由键，必填
- [ ] 批量预注入上下文，减少 LLM 工具调用次数
- [ ] 考虑与 MCP Schema 格式对齐

### 安全
- [ ] 危险操作有白名单检查
- [ ] 参数格式有 schema 验证
- [ ] 敏感信息（token、key）不记录日志
