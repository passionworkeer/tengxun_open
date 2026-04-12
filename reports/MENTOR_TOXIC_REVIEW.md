# 腾讯AI大模型面试官毒舌评审报告

**评审日期**: 2026-04-12
**评审人**: Senior Interviewer, Tencent AI
**被评审人**: 实习生
**项目**: Celery 跨文件依赖符号解析系统
**背景**: 从评级C提升到B+，测试从68条增加到275条，评测集从54条扩充到81条

---

## 总评：B- (及格边缘)

**理由**: 代码量看起来很多，测试看起来很多，评测集看起来很丰富。但核心问题一个都没解决——Hard 场景还是烂得一批，优化策略基本是自欺欺人。

---

## 一、架构设计：拆了文件，但没解决根本问题

### 1.1 模块拆分看起来很努力，实际上是形式主义

```
rag/
  ast_chunker.py      # 512行
  fusion.py           # 205行
  rrf_retriever.py    # 494行 (核心混合检索)
  conditional_retriever.py  # 449行
  graph.py            # 198行
  normalize_utils.py   # 68行
  indexes/
    bm25.py           # 114行
    embedding.py      # 343行
```

**问题 1**: `_tokenize` 函数在 `fusion.py`、`bm25.py`、`embedding.py` 三个地方各写了一遍。这叫 DRY 原则被扔到垃圾桶。任何一个正常人都会把它提取到 `normalize_utils.py` 复用。

**问题 2**: `rrf_retriever.py` 494行，`HybridRetriever` 塞了太多职责。BM25索引、语义索引、图索引全在一个类里初始化(Build Graph、Build Index全在 `__init__` 里)。你说这叫"模块化"？我看着像一个500行的 God Class。

**问题 3**: `conditional_retriever.py` 449行，里面有大量正则 pattern 硬编码：

```python
_TYPE_E_PATTERNS = [
    re.compile(r"symbol_by_name|by_name\(|import_object|config_from_object", re.I),
    re.compile(r"LOADER_ALIASES|BACKEND_ALIASES|ALIASES\[", re.I),
    # ...
]
```

这些 pattern 和评测数据里的 case 是强耦合的。你在训练集上拟合这些 pattern，测试的时候还是这些 pattern——这不叫 RAG，这叫背答案。

### 1.2 模块边界不清晰，依赖关系混乱

```python
# rag/rrf_retriever.py
from .fusion import (  # fusion 模块
    _kind_bonus,
    _looks_like_fqn,
    _tokenize,
    _extract_string_literals,
    _extract_symbol_like_strings,
)
from .graph import _entry_file_to_module, graph_search
from .indexes import _BM25Index, _EmbeddingIndex
```

`fusion.py` 导出了大量 `_` 开头的私有函数。这种 `from .fusion import _xxx` 的写法，意味着这些函数本来就不应该被外部使用，现在被强行暴露了。如果 `fusion.py` 改了，这些 import 全得改。

### 1.3 真实问题：索引构建时 O(n^2) 级别的图构建

```python
# rrf_retriever.py _build_graph()
def _build_graph(self) -> None:
    self._graph: dict[str, list[str]] = {c.chunk_id: [] for c in self.chunks}
    for chunk in self.chunks:
        # module siblings - O(n^2) 如果每个chunk都遍历同模块其他chunk
        for sibling_id in self.module_to_ids.get(chunk.module, []):
            if sibling_id != chunk.chunk_id:
                self._graph[chunk.chunk_id].append(sibling_id)
```

这是实习生写的代码，Celery 有几千个 chunk，每次构建索引都要两两比较。在本地测试没问题，放到真实项目上等着超时。

---

## 二、技术选型：看起来丰富，实际上处处有坑

### 2.1 PyYAML 根本没用

`finetune/train_lora.py` 里：

```python
try:
    import yaml as _yaml
except ImportError:
    _yaml = None
```

然后呢？整个项目里没有任何地方真正用到了 yaml 模块。这段代码是给谁看的？写了个 `import yaml` 然后 `except ImportError`，根本没有任何 fallback，逻辑是悬空的。

项目根目录有 `configs/*.yaml` 文件，但 `train_lora.py` 根本没用到它们——配置全是硬编码的。**这就是典型的"为了看起来专业而写专业代码"**。

### 2.2 Embedding 选型：用旧不用新

```python
# embedding_provider.py
DEFAULT_GOOGLE_MODEL = "models/gemini-embedding-001"
DEFAULT_GOOGLE_DIM = 3072
```

`gemini-embedding-001` 是 2023 年的模型。Google 在 2024 年推出了 `text-embedding-004`（1536 维，更强），2025 年推出了 `gemini-embedding-exp`（最新最强）。你选了一个三年前的旧模型，还把它写死成默认值。

更离谱的是，这个 embedding cache 326MB，**不进 git**。README 里专门写了一段解释"为什么不能直接 git pull"。这意味着：
1. 换了机器，embedding 得重新算
2. embedding 计算依赖 Google API，API 有 rate limit
3. 你根本不知道下次跑的时候 API 还有没有 quota

**这不是工程化，这是给自己埋雷。**

### 2.3 embedding search 用的是简单 dot product，没有归一化

```python
# embedding.py
dot = sum(a * b for a, b in zip(q_emb, emb))
embed_scores[cid] = (dot + 1.0) / 2.0
```

两个 embedding 做点积，然后除以 2 加 1 做归一化。这不是 cosine similarity，这是拍脑袋归一化。如果 embedding 没做 L2 归一化（gemini-embedding-001 没有保证），这个分数没有任何可比性。

### 2.4 urllib.request 替代了 Google 官方 SDK

```python
# embedding_provider.py
def _google_request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), ...)
```

不用 `google-generativeai` SDK，用原始 HTTP 请求。好处是看起来轻量，坏处是：
1. 错误处理全靠字符串匹配 `"429" in str(exc)`
2. 没有官方 SDK 提供的重试、backoff、batch 处理
3. API 版本变化了你根本不知道

---

## 三、代码质量：测试数量上去了，质量没上去

### 3.1 276个测试，大量是"assert X is not None"级别

看 `test_conditional_retriever.py`：

```python
def test_should_use_rag_easy_false(self, retriever: ConditionalRetriever) -> None:
    result = retriever.should_use_rag(
        question="Which real class does `celery.Celery` resolve to in the top-level lazy API?"
    )
    assert isinstance(result, bool)  # ← 这测了个寂寞
```

`isinstance(result, bool)` —— 任何布尔表达式都返回布尔，这测了个寂寞。这不是单元测试，这是凑数。

再比如 `test_prompt_templates_v2.py` 37个测试函数，逐一读过去全是这种水平：
- `assert template is not None`
- `assert "ground_truth" in template`
- `assert isinstance(prompts, list)`

**这种测试覆盖了代码行，但没覆盖代码行为。**

### 3.2 fixture 大量重复

每个测试文件都有一套 `make_chunk` fixture。`test_conditional_retriever.py`、`test_rrf_retriever.py`、`test_ast_chunker.py` 各自写了一遍。这说明项目没有统一的测试 fixture 库，代码复用意识为零。

### 3.3 测试数据是硬编码的，没有参数化

`test_conditional_retriever.py` 里的 pattern 测试：

```python
def test_type_e_symbol_by_name(self) -> None:
    result = classify_question_type(
        question="In celery.utils.imports, what does symbol_by_name('celery.app.base:Celery') resolve to?"
    )
    assert result.difficulty == "hard"
    assert result.failure_type == "Type E"
```

你把真实评测数据里的问题直接写进测试代码。如果评测数据改了，这些测试全部失效。如果评测数据和测试代码不一致，你根本不知道信哪个。

---

## 四、性能与扩展性：优化脚本一堆，实际效果等于零

### 4.1 RRF k值调优：10个参数，网格搜索

```python
# tune_rrf_k.py
K_VALUES = [10, 20, 30, 50, 60]
```

在 5 个 k 值上跑完整评测流程。问题是：
1. **没有优化方向**——网格搜索是穷举，不是优化
2. **没有 early stopping**——跑完全部才出结果
3. **k=30 是魔法数字**——没有任何理论依据

更关键的是，`tune_rrf_k.py` 只在 54 条评测数据上跑，k=30 和 k=60 的差异在统计上有意义吗？你做过显著性检验吗？

### 4.2 RRF 权重调优：10种组合，手动枚举

```python
# tune_rag_weights.py
DEFAULT_WEIGHT_COMBINATIONS = [
    {"bm25": 0.33, "semantic": 0.33, "graph": 0.34},
    {"bm25": 0.25, "semantic": 0.05, "graph": 0.70},
    {"bm25": 0.40, "semantic": 0.10, "graph": 0.50},
    # ... 共10种
]
```

手动枚举 10 种权重组合。这叫"调参"，不叫"优化"。你甚至没有写一个简单的 scipy.optimize。这 10 个组合是怎么选出来的？拍脑袋。

而且这 10 个组合里，最优的那个 `{"bm25": 0.33, "semantic": 0.33, "graph": 0.34}` —— bm25 0.33、semantic 0.33、graph 0.34，这不就是等权重吗？调了一圈最后发现等权重最好，这说明你根本不知道这三个来源的相对重要性。

### 4.3 ConditionalRetriever 策略：没经过端到端验证

```python
# conditional_retriever.py
def should_use_rag(self, question: str, ...) -> bool:
    classification = classify_question_type(question, ...)
    return classification.rag_recommended
```

这个"conditional RAG"策略从来没在端到端实验里验证过。`smart_retrieve` 方法存在，但没有任何实验结果显示它比"总是用 RAG"或"从不用 RAG"更好。

**你设计了一个优化，写了 449 行代码，从来没验证过它有没有用。**

---

## 五、工程化：数量上去了，质量没跟上

### 5.1 评测集从54条扩充到81条，但 case_id 全是 None

```python
# eval_cases.json
for c in d:
    print(f'Case {c.get("case_id")}...')  # Case None...
```

81 条 case，**每一条的 case_id 都是 None**。这意味着：
1. 你没法按 case_id 追踪单个 case 的表现
2. 你没法写回归测试针对特定 case
3. 对比不同实验结果时，你只能靠问题文本匹配，容易出错

### 5.2 评测数据质量问题：Type C 没有 Hard 难度

```python
Failure type counts: {'Type C': 12, 'Type E': 27, 'Type D': 18, 'Type B': 12, 'Type A': 12}
```

Type C 在 81 条评测集里有 12 条，但**没有一条是 Hard 难度**——全部是 easy (9条) + medium (3条)。Type E 有 27 条，其中 14 条是 Hard。

这意味着 **Type C 这个失效类型被系统性地忽略了**。如果你的 pipeline 在 Type C 上有盲点，这个评测集发现不了。

### 5.3 Hard 评测集质量存疑

43 条 Hard 难度，分布在 Type A (12)、Type B (9)、Type D (8)、Type E (14)。问题来了：
- 什么是"真正的 Hard"？还是说评测数据里的"Hard"只是"加了 `difficulty='hard'` 标签"？
- 你对比过不同时间点的评测集吗？扩充的 27 条是从哪来的？是真正新挖的难 case，还是从其他分类里挪过来的？

### 5.4 配置管理混乱

```
configs/
  config_defaults.yaml
  strict_clean_20260329.yaml
  train_config_20260327_143745.yaml
  train_config_strict_20260329.yaml
  train_config_strict_replay_20260329.yaml
```

5 个配置文件，时间戳全不一样。`train_lora.py` 实际用的是哪个？读代码你根本不知道，因为：

```python
# train_lora.py
DEFAULT_CONFIG = Path("configs/strict_clean_20260329.yaml")
# 但是...
if not default_cfg.exists():
    default_cfg = DEFAULTS_CONFIG
```

有 fallback 逻辑，但你不知道最终用的是哪个。更要命的是，README 里推荐的命令是 `make train-strict`，Makefile 里的配置又是什么？

---

## 六、策略有效性：核心数字禁不起推敲

### 6.1 0.5018 的水分

```
Qwen PE + RAG + FT = 0.5018 (strict-clean 54-case)
```

0.5018 是一个 **union F1**。让我拆开看：

```
Easy: 0.6168
Medium: 0.5196
Hard: 0.3986
```

**Hard 还是 0.40 不到。** 你的 PE+FT+RAG 全家桶，在最需要解决的 Hard 场景上，只比随机好一点。

### 6.2 PE 是真正的功臣，RAG 和 FT 在添乱

```
GPT-5.4 PE only: 0.6062 (union F1)
Qwen PE + RAG + FT: 0.5018 (union F1)
```

你用 Qwen 这个小模型加了一堆优化 (RAG + FT)，还是比不过 GPT-5.4 纯靠 PE。

更说明问题的是：

```
GPT-5.4 RAG only: 0.2940 (union F1)
GPT-5.4 Baseline: 0.2815 (union F1)
```

RAG 只给 GPT 带来了 0.015 的提升。但你看总体数字的时候，被 PE 的 0.33 提升掩盖了。

**RAG 的真实价值被过度宣传了。** 它的唯一亮点是 Hard 场景从 0.2261 到 0.3372，提升 0.11。但这个提升在 Qwen 上根本看不到（Qwen RAG only = 0.0185，基本等于零）。

### 6.3 FT 微调的 hard ratio oversampling 是个伪命题

```python
# train_lora.py
DEFAULT_SAMPLING_WEIGHTS = {"easy": 0.2, "medium": 0.3, "hard": 0.5}
```

你说要"对 Hard 样本加权采样"，把 hard ratio 提升到 50%。但：

1. 微调后 Hard 场景还是 0.40 以下——加权采样没解决问题
2. 500 条微调数据，`hard: 0.5` 意味着 250 条 hard 数据。81 条评测集里只有 43 条 hard。**你的微调数据里的 hard 和评测集里的 hard 是同一个分布吗？**

### 6.4 评分口径混乱，历史数据 vs strict-clean 数据混用

README 里写了"历史正式 PE+FT=0.4315 仍保留为归档参考"，然后又写了"不再作为 strict-clean 主结论"。你同时维护两条数据口径，评审人根本不知道该信哪个。

---

## 七、致命问题清单

| # | 问题 | 严重程度 | 影响 |
|---|------|----------|------|
| 1 | Hard 场景 0.40 以下未解决 | **致命** | 核心任务失败 |
| 2 | case_id 全为 None | **高** | 无法追踪单个 case |
| 3 | embedding cache 326MB 不进 git | **高** | 不可复现 |
| 4 | `_tokenize` 重复定义 3 次 | **中** | 代码腐烂 |
| 5 | 测试大量 `assert isinstance(x, bool)` | **中** | 假测试 |
| 6 | RRF 调参是网格穷举非优化 | **中** | 无效优化 |
| 7 | ConditionalRetriever 从未端到端验证 | **中** | 优化方向存疑 |
| 8 | Type C 无 Hard case，评测盲区 | **中** | 覆盖不足 |
| 9 | gemini-embedding-001 是旧模型 | **低** | 性能天花板低 |
| 10 | yaml 导入是悬空代码 | **低** | 维护混乱 |

---

## 最终冷酷评分：B-

**给分理由**：

- 代码量合格（rag/pe/finetune/evaluation 4个模块，276个测试）
- 评测体系完整（54条标准评测 + strict 数据审计 + PE/RAG/FT 三条线）
- 但 **Hard 场景 0.40 以下的瓶颈完全没有突破**
- **RAG 优化是个半成品**（conditional retriever 没验证过）
- **测试质量堪忧**（大量 assert isinstance 凑数）
- **数据管理混乱**（历史数据/strict数据混用，case_id 缺失）

**如果你来腾讯面试，我会问你这三个问题**：

1. "你测了 ConditionalRetriever 的端到端效果吗？smart_retrieve 比总是 RAG 好多少？"
2. "Type C 为什么没有 Hard case？你们在 Type C 上有盲区你知道吗？"
3. "tune_rrf_k.py 跑出了什么结论？k=30 和 k=60 差异统计显著吗？"

答不上来，B- 就是 B-。

---

## 真正能解决问题的建议

### 第一优先级：解决 Hard 场景（0.40 → 0.60+）

Hard 场景的根本问题是**多层间接依赖 + 动态符号解析**。当前的 RRF 检索在"从 A 经过 B 到达 C"这种两步跳转上效果差。

**真正有效的方向**：
1. **依赖路径索引**：不是检索单个 chunk，而是建立 (source, target, via) 三元组索引，直接索引 A→B→C 路径
2. **Type E 专项处理**：Type E (symbol_by_name) 只有 0.23 的 RRF recall。应该用正则规则直接匹配 symbol_by_name 调用，专门检索目标符号
3. **把 PE 里的 CoT 逻辑下沉到 RAG**：PE 靠 CoT 引导模型推理，RAG 应该检索"推理路径"而不是"孤立代码块"

### 第二优先级：修复评测数据

1. 给所有 81 条 case 补上 `case_id`（用 `hash(question + entry_file)` 生成）
2. 为 Type C 增加 Hard 难度 case
3. 分离"历史正式数据"和"strict-clean 数据"，不要混用

### 第三优先级：精简并验证优化

1. **删掉 `conditional_retriever.py`**：这个策略没验证过，留着是技术债
2. **删掉 `tune_rrf_k.py` 和 `tune_rag_weights.py`**：网格穷举不是优化，如果要做优化，用 Bayesian Optimization 或简单的梯度下降
3. 聚焦在 **Type E 场景** 的端到端提升，这 14 条 Hard case 是当前最大的可提升空间

---

*面试官签字：本评审仅指出问题，不提供安慰奖。*
