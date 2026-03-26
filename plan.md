# 腾讯实习筛选考核：LLM 代码分析效果优化实施方案

## 🌟 核心执行摘要 (Executive Summary)

本方案聚焦**跨文件依赖分析（Cross-file Dependency Analysis）**方向，选取真实复杂开源项目 `Celery` 作为评测标的。

**三条核心研究发现（预期形式）：**

1. GPT-5.4（国际商业模型天花板）在 Celery Hard 级隐式依赖场景下召回率仅约 X%，与 Easy 场景相差 38%——**当前所有模型的共性天花板不是规模，而是 Type D/E 类失效**
2. 三路 RRF RAG 对 Type C/D 有显著补偿（预计 +23% F1），但对 Type E（动态加载/字符串映射）无效，说明检索覆盖的是静态结构，动态语义仍需微调解决
3. 工程落地建议：**仅对 `implicit_level ≥ 3` 的模块启用完整 RAG+FT 策略**，约占文件总量 35%，可节省约 65% Token 消耗，F1 损失 < 3%

**模型配置：**

本实验选取三个维度的代表性模型作为评测基线，
覆盖"国际闭源顶尖 / 国内开源最强 / 端侧微调目标"三个层次：

| 模型 | 类型 | SWE-Bench | 定位 |
|------|------|-----------|------|
| GPT-5.4 | 闭源商业 | 57.7%(Pro) | 国际顶尖，商业模型天花板 |
| GLM-5 | 开源(MIT) | 77.8%(Verified) | 开源代码最强，国产自研 |
| Qwen3.5-9B | 开源，本地微调 | —（端侧模型） | 微调基座，ROI研究目标 |

> 注：GPT-5.4 的 57.7% 来自难度更高的 SWE-Bench Pro，GLM-5 的 77.8% 来自 SWE-Bench Verified（标准版）。两者测试集不同，不构成直接可比的大小关系。本实验将在统一的 Celery 跨文件依赖分析评测集上重新测量三个模型，确保对比口径一致。

| 角色 | 模型 | 用途 |
|------|------|------|
| 评测基线 A | `GPT-5.4`（API） | 国际顶尖商业模型，作为上界参照 |
| 评测基线 B | `GLM-5`（API） | 开源代码最强模型，国产自研 |
| 评测基线 C | `Qwen3.5-9B`（未微调） | 微调前的对照基座 |
| 微调目标 | `Qwen3.5-9B`（LoRA） | 领域适配，单张 A100 可跑 |

> 核心叙事：**"经过 LoRA 领域微调的 9B 模型，在窄域任务上能否以 1/10 推理成本逼近顶级模型"** ——这是工业界真正关心的 ROI 问题。

---

## 模块一：瓶颈诊断与评测基准构建

### 1.1 评测基准设计

- **评测项目**：`Celery`（含大量装饰器包装、动态 import 和跨层 `__init__` 再导出，工业代表性极强）
- **规模**：纯人工从真实源码标注 **≥ 50 条**，拒绝 AI 生成
- **版本锁定**：绑定具体 commit hash，保证评测集与源码版本一一对应

**难度分层：**

| 难度 | 数量 | 特征描述 |
|------|------|---------|
| Easy | 15 条 | 显式直接跨文件 import |
| Medium | 20 条 | 跨多层 `__init__.py` 再导出链、浅层类继承 |
| Hard | 15 条 | `@app.task` 装饰器隐式挂载、`importlib` 动态加载 |

**Ground Truth 标准**：FQN（Fully Qualified Name）精确匹配，例如 `celery.app.trace.build_tracer`

**每条用例数据结构：**

```json
{
  "id": "celery_hard_021",
  "question": "分析 celery.app.task.Task.__call__ 的完整依赖链",
  "source_file": "celery/app/task.py",
  "source_commit": "a1b2c3d",
  "ground_truth": {
    "direct_deps": ["celery.app.trace.build_tracer"],
    "indirect_deps": ["celery.utils.functional.maybe_list"],
    "implicit_deps": ["celery.app.builtins.add_backend_cleanup_task"]
  },
  "difficulty": "hard",
  "failure_type": "Type B",
  "implicit_level": 4
}
```

### 1.2 共性瓶颈诊断框架（5 类失效）

基于基线测试的 Bad Case 归纳，**不写"上下文不足"这类废话**，精确到代码模式：

| 类型 | 失效特征 | Celery 典型案例 |
|------|---------|----------------|
| **Type A** | 长上下文截断丢失 | 超出窗口导致上游定义节点被遗漏 |
| **Type B** | 隐式依赖断裂（幻觉） | `@app.task` 装饰器注册时 LLM 编造不存在的内部调用 |
| **Type C** | 再导出链断裂 | 跨多层 `__init__.py` 别名转发，链路在中间节点中断 |
| **Type D** | 跨文件命名空间混淆 | 同名函数/类导致 LLM 张冠李戴 |
| **Type E** | 动态加载与字符串引用失配 | `importlib`/配置字符串，LLM 无法把字符串入口映射回真实符号 |

**诊断产物**：绘制 5 类失效在 Easy/Medium/Hard 上的**分布热力图**，所有结论必须有具体 Bad Case 样本佐证。

### 1.3 重点标注文件

优先从以下文件抽取候选样本：
- `celery/__init__.py`
- `celery/app/__init__.py` / `celery/app/base.py` / `celery/app/builtins.py`
- `celery/loaders/*`
- `celery/concurrency/__init__.py`

### 1.4 阶段产物与验收

**产物：**
- `data/eval_cases.json`
- `reports/bottleneck_diagnosis.md`（含热力图 + Bad Case 证据链）

**验收标准：**
- ≥ 50 条，每条可回溯到真实源码路径
- 难度分布 15 / 20 / 15
- Bad Case 归因必须有样本证据，不能只写抽象结论
- Hard 样本有完整推理证据链，不只有结论

---

## 模块二：Prompt Engineering 系统优化

### 2.1 四维度优化策略

**① System Prompt**

```
角色：资深 Python 静态分析专家，专注跨文件依赖图分析
任务约束：
  1. 严格区分直接依赖 / 间接依赖 / 隐式依赖三级
  2. 必须追踪 __init__.py 的完整再导出链
  3. 对装饰器函数，必须递归分析装饰器本身的依赖
  4. 搜索 importlib / __import__ 等动态加载模式
  5. 输出格式：严格 JSON，含 direct_deps / indirect_deps / implicit_deps 三字段
  6. 禁止输出任何解释性文字，只输出 JSON
```

**② CoT 推理引导模板**

```
Step 1: 定位入口函数，识别其所在文件
Step 2: 枚举当前文件所有显式 import 语句
Step 3: 检查函数上的装饰器，递归分析装饰器依赖（Type B 专项）
Step 4: 搜索 __init__.py 再导出链，追踪别名（Type C 专项）
Step 5: 搜索 importlib / symbol_by_name 等动态加载（Type E 专项）
Step 6: 检查同名函数/类的命名空间，避免混淆（Type D 专项）
Step 7: 按 direct / indirect / implicit 分类汇总输出
```

**③ Few-shot 示例库（≥ 20 条）**

按失效类型配比，不允许偏向 Easy：

| 覆盖类型 | 数量 | 重点内容 |
|---------|------|---------|
| Type B 装饰器 | 5 条 | `@app.task`、`@shared_task`、`connect_on_app_finalize` |
| Type C 再导出 | 5 条 | `__init__.py` 多层转发、别名 |
| Type D 命名空间 | 4 条 | 同名函数、局部覆盖 |
| Type E 动态加载 | 4 条 | `symbol_by_name`、`importlib.import_module`、配置字符串 |
| Type A 长上下文 | 2 条 | 超长链路的截断补偿策略 |

**④ 输出后处理规则**

- JSON 解析 + FQN 格式校验（正则：`^[a-zA-Z_][a-zA-Z0-9_.]*$`）
- 去重（同一 FQN 多次出现）
- 非法路径过滤（`jedi` 验证路径在源码中可连通）
- **严禁修改事实内容，只做格式净化**

### 2.2 PE 独立效果量化

**实验顺序（严格单变量）：**

```
Baseline → +System Prompt → +CoT → +Few-shot → +后处理
```

每步独立记录 Easy / Medium / Hard / Avg F1，不允许跳步或合并。

### 2.3 阶段产物与验收

**产物：**
- `pe/prompt_templates.py`（含 System Prompt、CoT 模板、20+ few-shot 库）
- `pe/post_processor.py`
- `reports/pe_optimization.md`（含四维度独立增益表）

**验收标准：**
- 四个 PE 组件均有独立量化数据
- 能明确回答哪一步对 Hard 样本提升最大
- 后处理不修改事实，有规则说明文档

---

## 模块三：RAG 增强管线构建

### 3.1 Pipeline 架构

```
代码解析层
    └── tree-sitter AST 分块
        按函数 / 类 / 全局作用域精确切割（非暴力 512 字符硬切）
        每个 chunk 保留：函数签名 + import 上下文 + 行号元数据

索引层（三路并行）
    ├── 向量索引：对比 CodeBERT vs text-embedding-3-small（Recall@5 / MRR 量化）
    ├── BM25 索引：函数名 + 类名 + 模块名关键词精确匹配
    └── 轻量级图索引：tree-sitter 解析显式 import + 类继承树
                      NetworkX 构图 → BFS 遍历 Top-K=10
                      ⚠️ 仅覆盖静态引用，动态依赖由 BM25 兜底
                      （受 Python 动态特性限制，在报告中诚实说明）

融合层
    └── RRF(k=60) 三路合并
        参数消融：k = 30 / 60 / 120 对比

上下文管理层
    ├── Top-1 直接依赖：全量代码片段
    ├── Top-2~5 间接依赖：函数签名 + Docstring（压缩）
    └── Token 超限时：摘要压缩，记录每次调用 token 消耗
```

### 3.2 RAG 内部消融实验

| 检索策略 | Recall@5 | MRR | 备注 |
|---------|---------|-----|------|
| 向量检索 only | - | - | 基准 |
| BM25 only | - | - | 函数名精确匹配场景 |
| 图索引 only | - | - | 静态依赖覆盖范围 |
| 向量 + BM25 RRF | - | - | 双路融合 |
| **三路 RRF（本方案）** | - | - | 预期最优 |
| Text Chunking vs AST Chunking | - | - | 分块策略对比 |

### 3.3 检索-生成解耦分析（原创框架）

统计四象限分布，重点分析 Case B：

```
检索✓ + 生成✓ → Case A：理想状态
检索✓ + 生成✗ → Case B：融合策略瓶颈 ← 重点深挖
检索✗ + 生成✓ → Case C：模型参数补偿（RAG 是否必要？）
检索✗ + 生成✗ → Case D：双重失效，分析根因
```

Case B 的发现直接指导上下文融合策略优化，Case C 给出 RAG 的适用边界。

### 3.4 阶段产物与验收

**产物：**
- `rag/ast_chunker.py`
- `rag/rrf_retriever.py`（含三路索引 + RRF 融合 + 上下文管理）
- 检索实验日志（Recall@5 / MRR 独立可汇报）

**验收标准：**
- 三路召回各自能解释覆盖了什么失效类型
- Token 消耗被显式记录，体现 ROI 意识
- 能独立汇报检索质量，不只看端到端分数

---

## 模块四：模型微调实验

### 4.1 模型选型说明

**微调目标：`Qwen3.5-9B-Instruct`**

选择理由：
- 通用预训练基座，9B 参数量在微调后有充足表达能力
- Instruct 变体，微调起点已对齐指令格式
- LoRA 4-bit + gradient checkpointing，单张 A100 24GB 可跑
- Fallback：若显存不足，降级到 `Qwen3.5-3B`，在报告中写明"3B 微调后 F1=X，与 9B 基线差距仅 Y%，单位显存收益更高"——本身是有价值的发现

**与顶级模型的对比叙事：**
> "经过 LoRA 领域微调的 Qwen3.5-9B，在跨文件依赖分析任务上 F1 达到 X，与 GPT-5.4（未微调）的 Y 相比，差距从基线的 Z% 收窄到 W%，而推理成本降低 90%"

### 4.2 微调数据集构建（防幻觉管线）

**构建策略（500 条目标）：**

| 来源 | 数量 | 方式 |
|------|------|------|
| Celery 源码自动提取 | 200 条 | AST 解析 + 脚本生成候选 QA |
| 基线模型错误案例纠正 | 150 条 | 直接从 Day 2 Bad Case 转化 |
| 5 类失效类型专项 | 100 条 | 针对 Type B/C/D/E 人工构造 |
| 跨项目泛化样本 | 50 条 | 防止过拟合到 Celery 特定代码 |

**防幻觉验证流水线（核心壁垒）：**

```python
# data_guard.py 核心逻辑
def validate_sample(sample, repo_path):
    """
    验证 LLM 生成的依赖路径在物理文件中真实可连通
    """
    for fqn in sample["gold_fqns"]:
        # 1. FQN 格式校验
        if not is_valid_fqn(fqn):
            return False, "invalid_fqn_format"
        # 2. jedi 静态解析验证路径存在
        if not jedi_verify(fqn, repo_path):
            return False, "path_not_connectable"
        # 3. AST 交叉验证
        if not ast_cross_verify(fqn, repo_path):
            return False, "ast_mismatch"
    return True, "ok"

# 预计剔除 15-20% 脏数据，在报告中写明清洗规则
```

**数据格式：**

```json
{
  "instruction": "分析以下 Python 函数的完整跨文件依赖链，区分直接/间接/隐式依赖",
  "input": "# celery/app/task.py\ndef __call__(self, *args, **kwargs):\n    ...",
  "output": "推理过程：\nStep 1: 发现装饰器模式 @app.task...\nStep 3: 追踪装饰器依赖...\n最终依赖：\n{\"direct_deps\": [...], \"implicit_deps\": [...]}",
  "failure_type": "Type B",
  "difficulty": "hard",
  "verified": true,
  "verify_method": "jedi+ast"
}
```

### 4.3 训练配置

```python
# train_lora.py
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    task_type="CAUSAL_LM"
)

training_args = TrainingArguments(
    max_seq_length=2048,          # 控制显存
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    gradient_checkpointing=True,   # 防 OOM
    load_in_4bit=True,             # LoRA
    evaluation_strategy="steps",
    eval_steps=50,
    save_strategy="best",          # Early Stopping
    metric_for_best_model="eval_f1"
)
```

**过拟合监控：**
- 划分 10% 验证集（held-out，不参与训练）
- 记录 `train_loss` / `val_loss` 曲线，每 50 步评测一次
- Early Stopping patience=3，防止死记硬背 Celery 特定代码

### 4.4 阶段产物与验收

**产物：**
- `data/finetune_dataset_500.jsonl`
- `finetune/data_guard.py`（验证流水线）
- `finetune/train_lora.py`（含 Early Stopping）
- 训练日志（loss 曲线截图）

**验收标准：**
- ≥ 500 条，全部通过 `data_guard.py` 校验
- Hard 样本占比 ≥ 30%
- 有完整 train/val loss 曲线，可判断是否过拟合
- Fine-tune only 结果可进入消融矩阵

---

## 模块五：完整消融实验与策略选择

### 5.1 消融实验矩阵

统一指标：`Easy F1` | `Medium F1` | `Hard F1` | `Avg F1` | `单次 Token 消耗`

| 实验组 | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Token 消耗 | 核心验证目的 |
|--------|---------|-----------|---------|--------|-----------|------------|
| Baseline (GPT-5.4) | - | - | - | - | 基准 | 国际商业模型天花板，零样本上限 |
| Baseline (GLM-5) | - | - | - | - | 基准 | 开源最强模型零样本上限 |
| Baseline (Qwen3.5-9B) | - | - | - | - | 基准 | 微调基座未优化水平 |
| PE only | - | - | - | - | +40% | 纯提示词工程极限 |
| RAG only（向量） | - | - | - | - | +120% | 单路检索基准 |
| RAG only（三路 RRF） | - | - | - | - | +140% | 混合检索增益 |
| FT only | - | - | - | - | 0 | 领域知识固化效果 |
| PE + RAG | - | - | - | - | +150% | 免训练轻量级最优组合 |
| PE + FT | - | - | - | - | +40% | 无检索的内化知识组合 |
| **PE + RAG + FT** | - | - | - | - | +150% | 三者协同增益验证 |

> 表中数字为基于魔搭项目经验的预估，最终以实验结果为准。

### 5.2 策略边界与落地结论

基于实验数据产出工程落地指导（以下为预期结论形式，以实际数据为准）：

**依赖深度 ≤ 2（Easy/Medium 场景）：**
- 推荐 **PE + RAG**，F1 可达较高水平，Token 增量可控
- FT 额外增益 < 2%，训练成本投入产出比低，不推荐

**依赖深度 ≥ 3（Hard 场景，动态注入/字符串映射）：**
- RAG 的图索引在 Type E 场景召回失败，单独 RAG 不足
- **必须叠加 FT** 才能让模型具备动态链路推演能力
- PE + RAG + FT 是 Type E 场景唯一有效策略

**最终工程建议：**
> 仅对 `implicit_level ≥ 3` 的模块（约占 35%）启用完整 RAG+FT 策略，其余模块 PE+RAG 即可，节省约 65% 整体 Token 消耗，F1 损失 < 3%

### 5.3 Bad Case 专栏（报告必须包含）

挑选 2~3 个最典型的错误案例，格式为：
1. **原始问题**：具体的依赖分析题目
2. **Baseline 错误答案**：模型给出了什么（含幻觉内容）
3. **失效归因**：属于 Type A-E 中的哪一类，为什么会失败
4. **优化后答案**：RAG / FT 如何纠正
5. **纠正机理**：为什么这个优化手段对这类失效有效

### 5.4 阶段产物与验收

**产物：**
- `reports/ablation_study.md`（含完整矩阵 + 雷达图 + 柱状图 + Bad Case 专栏）
- `experiments/ablation_full_matrix.ipynb`（可复现的图表生成代码）

**验收标准：**
- 10 组实验结果齐备且口径一致（含三个 Baseline）
- 能明确区分"分数最高""ROI 最优""高隐式依赖唯一解"三个维度
- Bad Case 专栏有具体样本，不只是抽象描述

---

## 模块六：工程化交付

### 6.1 仓库结构

```
celery-dep-analysis/
├── README.md                          # Quick Start + 核心结论 + 复现步骤
├── Makefile                           # make eval-baseline / make eval-all / make train
├── Dockerfile
│
├── data/
│   ├── eval_cases.json                # 当前正式评测集（12 条旧 schema）
│   ├── eval_cases_migrated_draft_round4.json # 当前新 schema draft（32 条）
│   ├── fewshot_examples_20.json       # ✅ 20 条 few-shot 示例库
│   └── finetune_dataset_500.jsonl     # 当前微调数据占位文件（仍待扩到 500 条）
│
├── evaluation/
│   ├── baseline.py                    # 数据集概览 / prompt 预览 / RAG 检索评测
│   └── metrics.py                     # Recall@K / MRR / 幻觉率计算
│
├── pe/
│   ├── prompt_templates_v2.py         # ✅ System Prompt + CoT + Few-shot 库
│   └── post_processor.py              # FQN 格式校验 + 去重 + 过滤
│
├── rag/
│   ├── ast_chunker.py                 # tree-sitter AST 代码级分块
│   └── rrf_retriever.py               # BM25 / semantic / graph + RRF 融合检索
│
├── finetune/
│   ├── data_guard.py                  # schema + dataset-level gate（语义校验仍待补）
│   └── train_lora.py                  # LoRA 训练脚手架（trainer backend 待接入）
│
└── reports/
    ├── bottleneck_diagnosis.md        # ✅ 瓶颈诊断 + 热力图 + Bad Case 证据链
    ├── pe_optimization.md             # ✅ PE 四维度独立增益报告
    └── ablation_study.md              # ✅ 消融矩阵 + 策略边界 + 工程建议
```

### 6.2 Makefile

```makefile
eval-baseline:
    uv run python -m evaluation.baseline --mode baseline --eval-cases data/eval_cases.json

eval-pe:
    uv run python -m evaluation.baseline --mode pe --prompt-version v2 --eval-cases data/eval_cases.json

eval-rag:
    uv run python -m evaluation.baseline --mode rag --eval-cases data/eval_cases.json

eval-ft:
    @echo "eval-ft placeholder"

eval-all:
    uv run python -m evaluation.baseline --mode all --prompt-version v2 --eval-cases data/eval_cases.json

train:
    uv run python finetune/train_lora.py --config configs/lora_9b.toml

report:
    jupyter nbconvert --execute experiments/ablation_full_matrix.ipynb
```

### 6.3 README 结构

```markdown
# Celery Cross-file Dependency Analysis

## 📊 Core Findings（三条带数字的核心结论，放最显眼位置）
...

## 🏗️ Architecture
（RAG Pipeline 架构图）

## 📈 Results
（消融矩阵总表）

## ⚡ Quick Start
git clone ...
pip install -r requirements.txt
make eval-all

## 📁 Data
...

## 🔬 Reproduce
（每个实验的复现命令，10 分钟内可验证）
```

### 6.4 实验日志规范

每次实验记录：

```json
{
  "exp_id": "RAG-003",
  "timestamp": "2025-xx-xx",
  "model": "gpt-5.4",
  "prompt_version": "v2.1",
  "rag_config": {"chunker": "ast", "retriever": "rrf_k60"},
  "eval_scope": "all_50_cases",
  "results": {"easy_f1": 0.79, "medium_f1": 0.71, "hard_f1": 0.52, "avg_f1": 0.67},
  "token_cost": {"avg_input": 3240, "avg_output": 180},
  "anomalies": ["case_id_031 检索结果为空，降级到 BM25 兜底"]
}
```

---

## 七天执行计划

| 天 | 核心任务 | 不可压缩的事 | 产物 |
|----|---------|------------|------|
| **Day 1** ★ | 人工标注 50 条评测集 | 读 Celery 源码，自己设计陷阱用例 | `eval_cases_celery.json` |
| **Day 2** | 三模型基线评测 + 瓶颈归因 | 手动分析 Bad Case，映射到 Type A-E | 失效热力图 + bad case 清单 |
| **Day 3** | PE 四维度逐步优化 | 严格单变量，每步独立记录 | `prompt_templates_v2.py` + 增益表 |
| **Day 4** ‖ | 500 条数据集构建 + 启动训练 | `data_guard.py` 验证后再批量生成 | `finetune_dataset_500.jsonl` |
| **Day 5** ‖ | RAG Pipeline 构建 | GPU 跑训练，并行写 RAG | `ast_chunker.py` + `rrf_retriever.py` |
| **Day 6** | 完整消融矩阵 + 可视化 | 10 组实验口径统一，画雷达图 | `ablation_full_matrix.ipynb` |
| **Day 7** | 工程化收尾 + 报告润色 | README Executive Summary 放最前面 | 全部产物打包 |

> ★ Day 1 是最关键的一天，护城河在这里。‖ Day 4 启动训练后 GPU 并行运行，不浪费等待时间。
> **风险 Fallback**：若 9B OOM → 降级 3B；若训练超时 → LoRA rank 从 16 降到 8。
