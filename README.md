# Celery Cross-file Dependency Analysis

## 📊 核心研究发现（预期形式）

1. **GPT-5.4 在 Hard 级隐式依赖场景下召回率仅约 X%**，与 Easy 场景相差 38%——当前所有模型的共性天花板不是规模，而是 Type D/E 类失效
2. **三路 RRF RAG 对 Type C/D 有显著补偿**（预计 +23% F1），但对 Type E（动态加载/字符串映射）无效，说明检索覆盖的是静态结构，动态语义仍需微调解决
3. **工程落地建议**：仅对 `implicit_level ≥ 3` 的模块启用完整 RAG+FT 策略，约占文件总量 35%，可节省约 65% Token 消耗，F1 损失 < 3%

## 🏗️ 基线模型选型

本实验选取三个维度的代表性模型作为评测基线，
覆盖"国际闭源顶尖 / 国内开源最强 / 端侧微调目标"三个层次：

| 模型 | 类型 | SWE-Bench | 定位 |
|------|------|-----------|------|
| GPT-5.4 | 闭源商业 | 57.7%(Pro) | 国际顶尖，商业模型天花板 |
| GLM-5 | 开源(MIT) | 77.8%(Verified) | 开源代码最强，国产自研 |
| Qwen3.5-9B | 开源，本地微调 | —（端侧模型） | 微调基座，ROI研究目标 |

选型依据：
- GPT-5.4：唯一有官方完整基准表格的闭源模型，可作为"国际商业模型天花板"的可信锚点
- GLM-5：SWE-Bench Verified 77.8%，当前开源代码模型最高分，MIT协议来源干净
- Qwen3.5-9B：核心研究对象，验证"窄域微调能否以1/10推理成本逼近顶级模型"这一工程命题

> 注：GPT-5.4 的 57.7% 来自难度更高的 SWE-Bench Pro，GLM-5 的 77.8% 来自 SWE-Bench Verified（标准版）。两者测试集不同，不构成直接可比的大小关系。本实验将在统一的 Celery 跨文件依赖分析评测集上重新测量三个模型，确保对比口径一致。

| 角色 | 模型 | 用途 |
|------|------|------|
| 评测基线 A | `GPT-5.4`（API） | 国际顶尖商业模型，作为上界参照 |
| 评测基线 B | `GLM-5`（API） | 开源代码最强模型，国产自研 |
| 评测基线 C | `Qwen3.5-9B`（未微调） | 微调前的对照基座 |
| 微调目标 | `Qwen3.5-9B`（LoRA） | 领域适配，单张 A100 可跑 |

> **核心叙事**：经过 LoRA 领域微调的 9B 模型，在窄域任务上能否以 1/10 推理成本逼近顶级模型 ——这是工业界真正关心的 ROI 问题

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
| Baseline (GPT-5.4) | 国际商业模型天花板，零样本上限 |
| Baseline (GLM-5) | 开源最强模型零样本上限 |
| Baseline (Qwen3.5-9B) | 微调基座未优化水平 |
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

# 2. 查看当前评测集摘要
python -m evaluation.baseline --eval-cases data/eval_cases.json

# 3. 校验微调数据
python -m finetune.data_guard data/finetune_dataset_500.jsonl

# 4. 运行当前 baseline 摘要命令
make eval-baseline

# 5. 运行当前 summary + RAG + PE 预览组合命令
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
│   ├── eval_cases.json                # 当前正式评测集（12 条旧 schema）
│   ├── eval_cases_migrated_draft_round4.json # 新 schema 迁移+round4 draft（32 条）
│   ├── fewshot_examples_20.json       # 20 条 few-shot 示例库
│   └── finetune_dataset_500.jsonl     # 500 条经验证的微调数据集
│
├── evaluation/
│   ├── baseline.py                    # 数据集概览 / prompt 预览 / RAG 检索评测
│   └── metrics.py                     # Recall@K / MRR 等指标计算
│
├── pe/
│   ├── prompt_templates_v2.py         # System Prompt + CoT + Few-shot 库
│   └── post_processor.py              # FQN 格式校验 + 去重 + 过滤
│
├── rag/
│   ├── ast_chunker.py                 # tree-sitter AST 代码级分块
│   └── rrf_retriever.py               # BM25 / semantic / graph + RRF 融合检索
│
├── finetune/
│   ├── data_guard.py                  # jedi+ast 防幻觉验证流水线
│   └── train_lora.py                  # LoRA 训练 + Early Stopping
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
