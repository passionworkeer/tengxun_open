# Celery Cross-file Dependency Analysis

## 📊 核心研究发现（预期形式）

1. **GLM-5 在 Hard 级隐式依赖场景下召回率仅约 X%**，与 Easy 场景相差 38%——当前所有模型的共性天花板不是规模，而是 Type D/E 类失效
2. **三路 RRF RAG 对 Type C/D 有显著补偿**（预计 +23% F1），但对 Type E（动态加载/字符串映射）无效，说明检索覆盖的是静态结构，动态语义仍需微调解决
3. **工程落地建议**：仅对 `implicit_level ≥ 3` 的模块启用完整 RAG+FT 策略，约占文件总量 35%，可节省约 65% Token 消耗，F1 损失 < 3%

## 🏗️ 模型配置

| 角色 | 模型 | 用途 |
|------|------|------|
| 评测基线 A | `GLM-5`（API） | 开源代码最强模型，作为上界参照 |
| 评测基线 B | `GPT-4o`（API） | 所有人熟悉的锚点，便于结论校准 |
| 评测基线 C | `Qwen2.5-Coder-7B`（未微调） | 微调前的对照基座 |
| 微调目标 | `Qwen2.5-Coder-7B`（QLoRA） | 领域适配，单张 A100 可跑 |

> **核心叙事**：经过领域微调的 7B 模型，在窄域任务上能否逼近甚至超越 70B+ 通用大模型 ——这是工业界真正关心的 ROI 问题

## 🏗️ Architecture

```
代码解析层
    └── tree-sitter AST 分块
        按函数 / 类 / 全局作用域精确切割

索引层（三路并行）
    ├── 向量索引：CodeBERT vs text-embedding-3-small
    ├── BM25 索引：函数名 + 类名 + 模块名关键词精确匹配
    └── 图索引：NetworkX 解析 import + 继承树

融合层
    └── RRF(k=60) 三路合并

上下文管理层
    ├── Top-1 直接依赖：全量代码片段
    ├── Top-2~5 间接依赖：函数签名 + Docstring（压缩）
    └── Token 超限时：摘要压缩
```

## 📈 消融实验矩阵（10 组）

| 实验组 | 核心验证目的 |
|--------|------------|
| Baseline (GPT-4o) | 商业模型零样本上限 |
| Baseline (GLM-5) | 开源最强模型零样本上限 |
| Baseline (Qwen2.5-Coder-7B) | 微调基座未优化水平 |
| PE only | 纯提示词工程极限 |
| RAG only（向量） | 单路检索基准 |
| RAG only（三路 RRF） | 混合检索增益 |
| FT only | 领域知识固化效果 |
| PE + RAG | 免训练轻量级最优组合 |
| PE + FT | 无检索的内化知识组合 |
| PE + RAG + FT | 三者协同增益验证 |

## ⚡ Quick Start

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 查看评测集状态
python -m evaluation.baseline --eval-cases data/eval_cases_celery.json

# 3. 校验微调数据
python -m finetune.data_guard data/finetune_dataset_500.jsonl

# 4. 运行基线评测
make eval-baseline

# 5. 运行全部实验
make eval-all
```

## 📁 仓库结构

```
celery-dep-analysis/
├── README.md                          # Quick Start + 核心结论 + 复现步骤
├── plan.md                            # 完整实施方案
├── task.md                            # 考核任务要求
├── Makefile                           # make eval-baseline / make eval-all / make train
│
├── data/
│   ├── eval_cases_celery.json         # 50 条人工标注评测集
│   ├── fewshot_examples_20.json       # 20 条 few-shot 示例库
│   └── finetune_dataset_500.jsonl     # 500 条经验证的微调数据集
│
├── evaluation/
│   ├── baseline_eval.py               # 多模型并行基线评测
│   └── metrics_fqn.py                 # F1 / Recall@K / MRR / 幻觉率计算
│
├── pe/
│   ├── prompt_templates_v2.py         # System Prompt + CoT + Few-shot 库
│   └── post_processor.py              # FQN 格式校验 + 去重 + 过滤
│
├── rag/
│   ├── ast_chunker.py                 # tree-sitter AST 代码级分块
│   ├── indexer_three_way.py           # 三路索引构建
│   ├── retriever_rrf.py               # RRF(k=60) 融合检索
│   └── context_manager.py             # 上下文分层压缩 + Token 计数
│
├── finetune/
│   ├── data_guard.py                  # jedi+ast 防幻觉验证流水线
│   └── train_qlora.py                 # QLoRA 训练 + Early Stopping
│
├── experiments/
│   └── ablation_full_matrix.ipynb     # 完整消融实验（含雷达图/柱状图/热力图）
│
├── results/
│   └── *.json                         # 所有实验原始结果
│
├── reports/
│   ├── bottleneck_diagnosis.md        # 瓶颈诊断 + 热力图 + Bad Case 证据链
│   ├── pe_optimization.md             # PE 四维度独立增益报告
│   └── ablation_study.md              # 消融矩阵 + 策略边界 + 工程建议
│
├── external/
│   └── celery/                        # Celery 源码快照
│
└── docs/                              # 项目文档
```

## 🔬 Reproduce

每个实验的复现命令，10 分钟内可验证：

```bash
# 基线评测
make eval-baseline

# PE 消融
make eval-pe

# RAG 消融
make eval-rag

# 微调评测
make eval-ft

# 完整消融矩阵
make eval-all

# 训练模型
make train

# 生成报告
make report
```

## 📚 关键文档

- [plan.md](plan.md) - 完整实施方案
- [task.md](task.md) - 考核任务要求
- [docs/dataset_schema.md](docs/dataset_schema.md) - 数据集字段定义
- [docs/detailed_stage_playbook.md](docs/detailed_stage_playbook.md) - 逐阶段执行手册
- [docs/celery_case_mining.md](docs/celery_case_mining.md) - Celery 源码挖掘指南
- [docs/first_batch_candidates.md](docs/first_batch_candidates.md) - 首批候选样本 C01-C12
- [docs/repo_snapshot.md](docs/repo_snapshot.md) - Celery 版本绑定信息

## 当前状态

- ✅ 项目骨架搭建完成
- ✅ 文档体系完整
- ✅ Celery 源码已拉取（commit: b8f85213）
- ⏳ 评测集构建中（Day 1 任务）
