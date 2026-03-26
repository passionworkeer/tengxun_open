# Celery 跨文件依赖分析项目

## 项目概述

本项目聚焦**跨文件依赖分析（Cross-file Dependency Analysis）**方向，选取真实复杂开源项目 `Celery` 作为评测标的，研究如何通过 **提示词工程（PE）**、**检索增强生成（RAG）** 和 **模型微调（FT）** 三种手段提升大模型在代码依赖分析任务上的表现。

### 核心研究问题

> 经过 LoRA 领域微调的 9B 模型，在窄域任务上能否以 1/10 推理成本逼近顶级模型？

---

## 模型基线（最终配置）

| 角色 | 模型 | Benchmark | 来源 |
|------|------|-----------|------|
| Baseline A | GPT-5.4 | SWE-Bench Pro 57.7% | 闭源商业 |
| Baseline B | GLM-5 | SWE-Bench Verified 77.8% | 开源 MIT，ModelScope API |
| Baseline C | Qwen3.5-9B | —（待测） | 开源本地，未微调 |
| FT 目标 | Qwen3.5-9B + LoRA | —（待测） | 端侧微调 |

> 注：SWE-Bench Pro 与 Verified 是不同测试集，不可直接对比大小。

---

## 当前完成进度

| 模块 | 状态 | 关键产物 |
|------|------|---------|
| 评测集（50条） | ✅ | `data/eval_cases_migrated_draft_round4.json` |
| Few-shot（20条） | ✅ | `pe/prompt_templates_v2.py`, `data/fewshot_examples_20.json` |
| GPT-5.4 Baseline | ✅ | `reports/gpt5_results_archived/` |
| GLM-5 Baseline | ⬜ 待跑 | `evaluation/run_glm_eval.py` |
| Qwen3.5-9B Baseline | ⬜ 待跑 | — |
| RAG v2 | ✅ | Graph 单路 R@5=0.331，RRF k=30 |
| Qwen3 Embedding | ⚠️ 配额用尽 | 缓存 5825/8086 (72%) |
| LoRA 微调 | ⬜ 待跑 | `finetune/train_lora.py` |

---

## 技术架构

```
代码解析层
    └── tree-sitter AST 分块
        按函数 / 类 / 全局作用域精确切割

索引层（三路并行）
    ├── BM25：函数名 + 类名 + 关键词精确匹配
    ├── Semantic：Qwen3-Embedding-8B（ModelScope API）
    │               回退：TF-IDF + char 3-5 n-gram
    └── Graph：dict 邻接 BFS
                import (+0.3) / string_target (+0.25) / reference (+0.15)

融合层
    └── RRF(k=30) 三路合并  ← k=30 最优（已验证 k=30 > k=60 > k=120）

上下文管理（分层渲染）
    ├── Top-1：全量代码片段
    └── Top-2~5：函数签名 + Docstring（压缩）

Embedding 缓存
    └── artifacts/rag/embeddings_cache.json（475MB，5825/8086 已缓存）
```

---

## 项目结构

```
celery-dep-analysis/
│
├── README_中文.md                    # 本文档
├── plan.md                           # 完整实施方案
├── task.md                           # 考核任务要求
├── Makefile                          # 快捷命令入口
│
├── data/                             # 数据目录
│   ├── eval_cases_migrated_draft_round4.json  # 正式评测集（50条，schema_v2）
│   ├── fewshot_examples_20.json      # 20条 Few-shot 示例
│   ├── finetune_dataset_500.jsonl    # 微调数据集（500条）
│   └── archive/                       # 已归档的旧版本数据
│
├── evaluation/                       # 评测模块
│   ├── baseline.py                   # RAG 检索评测（Recall@K, MRR）
│   ├── metrics.py                    # 指标计算
│   ├── run_glm_eval.py              # GLM-5 评测
│   └── run_qwen_eval.py             # Qwen 评测
│
├── rag/                              # 检索增强模块
│   ├── ast_chunker.py                # AST 代码级分块
│   └── rrf_retriever.py              # BM25 / Semantic / Graph + RRF 融合
│
├── pe/                               # 提示词工程模块
│   ├── prompt_templates_v2.py         # System Prompt + CoT + Few-shot
│   └── post_processor.py             # FQN 格式校验 + 去重
│
├── finetune/                         # 微调模块
│   ├── data_guard.py                 # 数据验证流水线（防幻觉）
│   └── train_lora.py                 # LoRA 训练脚手架
│
├── scripts/                           # 脚本
│   ├── precompute_embeddings.py       # 预计算 Embedding 缓存
│   ├── generate_finetune_data.py     # 从评测结果生成微调数据
│   ├── run_finetuned_eval.py        # 微调后评测
│   ├── compare_results.py            # 基线 vs 微调对比报告
│   ├── train_lora.sh                 # LoRA 训练 shell
│   └── archive/                      # 已归档的旧脚本
│
├── configs/                          # 配置文件
│   └── lora_9b.toml                 # Qwen3.5-9B LoRA 配置
│
├── reports/                          # 分析报告
│   ├── rag_retrieval_eval_round4.md # RAG 检索评测报告（最新）
│   ├── bottleneck_diagnosis.md        # 瓶颈诊断报告
│   ├── pe_optimization.md            # PE 优化报告
│   ├── ablation_study.md             # 消融实验报告
│   └── gpt5_results_archived/        # GPT-5 归档结果
│
├── docs/                              # 项目文档
│   ├── remaining_work_checklist.md   # 当前工作清单
│   ├── execution_roadmap.md           # 执行路线图
│   ├── detailed_stage_playbook.md     # 逐阶段执行手册
│   ├── dataset_schema.md              # 数据集字段定义
│   └── drafts_archived_20260326/     # 已归档的历史草稿
│
└── external/celery/                # Celery 源码快照
                                      # commit: b8f85213
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 查看评测集摘要

```bash
python -m evaluation.baseline --eval-cases data/eval_cases_migrated_draft_round4.json
```

### 3. 运行 RAG 检索评测

```bash
python -m evaluation.baseline --mode rag \
  --eval-cases data/eval_cases_migrated_draft_round4.json \
  --repo-root external/celery --top-k 5 \
  --report-path artifacts/rag/eval_v2_50cases.json
```

### 4. 补全 Embedding 缓存（ModelScope 配额刷新后）

```bash
python3 scripts/precompute_embeddings.py
```

### 5. 预训练 LoRA

```bash
bash scripts/train_lora.sh
```

---

## 失效类型分类

| 类型 | 失效特征 | 典型案例 |
|------|---------|---------|
| **Type A** | 长上下文截断丢失 | 超出窗口导致上游定义节点被遗漏 |
| **Type B** | 隐式依赖幻觉 | `@app.task` 装饰器注册时模型编造不存在的内部调用 |
| **Type C** | 再导出链断裂 | 跨多层 `__init__.py` 别名转发，链路在中间节点中断 |
| **Type D** | 跨文件命名空间混淆 | 同名函数/类导致张冠李戴 |
| **Type E** | 动态加载与字符串引用失配 | `importlib`/配置字符串，模型无法把字符串入口映射回真实符号 |

---

## 评测指标

| 指标 | 说明 |
|------|------|
| Recall@K | 在前 K 个检索结果中命中的 gold 标准比例 |
| MRR | 平均倒数排名 |
| F1 | 精确率与召回率的调和平均 |

---

## 当前 RAG 评测结果（50-case，question_plus_entry，k=30）

| Source | Recall@5 | MRR | Notes |
|:-------|:---------:|:----:|:------|
| BM25 | 0.183 | 0.316 | 关键词匹配 |
| Semantic（TF-IDF fallback） | 0.063 | 0.147 | 弱，预期 Qwen3 Embedding 可大幅提升 |
| **Graph** | **0.331** | **0.480** | **最强单源** |
| **Fused (k=30)** | **0.294** | **0.449** | BM25+Semantic+Graph 融合 |

---

## 文档索引

- [plan.md](plan.md) - 完整实施方案
- [task.md](task.md) - 考核任务要求
- [docs/remaining_work_checklist.md](docs/remaining_work_checklist.md) - 当前工作清单
- [docs/dataset_schema.md](docs/dataset_schema.md) - 数据集字段定义
- [docs/execution_roadmap.md](docs/execution_roadmap.md) - 执行路线图
