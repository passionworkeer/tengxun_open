# Celery Cross-file Dependency Analysis

本仓库是基于 [task.md](task.md) 与 [plan.md](plan.md) 搭建的第一版项目骨架，目标是完成腾讯实习筛选考核中的“基于微调 / Prompt Engineering / RAG 的代码分析领域效果优化”中难度方案。

当前实现重点不是把全部实验一次性做完，而是先把后续开发、实验和答辩需要的结构搭稳：

- 统一项目目标、范围与交付物
- 固化评测、PE、RAG、微调、报告五条主线
- 提供最小可用脚手架，方便后续逐步填充真实实现

当前阶段采用“先文档、后实现、再实验”的推进方式：

- 先把任务边界、数据口径、实验矩阵和交付物写清楚
- 再拉取真实分析对象仓库，绑定版本信息
- 最后开始评测集构建、Prompt 设计、RAG 和微调

## 目标范围

本项目聚焦一个明确方向：

- 分析任务：跨文件依赖分析
- 标的项目：Celery
- 评测集：人工构建不少于 50 条评测用例
- 微调集：经校验后不少于 500 条数据
- 核心实验：Baseline / PE only / RAG only / Fine-tune only / PE + RAG / PE + Fine-tune / All

## 仓库结构

```text
.
├── plan.md
├── task.md
├── README.md
├── Makefile
├── requirements.txt
├── docs/
│   ├── dataset_schema.md
│   ├── celery_case_mining.md
│   ├── ai_prompt_templates.md
│   ├── ai_task_breakdown.md
│   ├── ai_task_cards.md
│   ├── ai_work_batches.md
│   ├── candidate_task_packets.md
│   ├── detailed_stage_playbook.md
│   ├── eval_case_annotation_template.md
│   ├── experiment_log_template.md
│   ├── first_batch_candidates.md
│   ├── execution_roadmap.md
│   └── repo_snapshot.md
├── data/
│   ├── eval_cases.json
│   └── finetune_dataset.jsonl
├── external/
│   └── celery/
├── evaluation/
│   ├── __init__.py
│   ├── baseline.py
│   └── metrics.py
├── pe/
│   ├── __init__.py
│   ├── prompt_templates.py
│   └── post_processor.py
├── rag/
│   ├── __init__.py
│   ├── ast_chunker.py
│   └── rrf_retriever.py
├── finetune/
│   ├── __init__.py
│   ├── data_guard.py
│   └── train_qlora.py
└── reports/
    ├── bottleneck_diagnosis.md
    ├── pe_optimization.md
    └── ablation_study.md
```

## 模块说明

### `docs/`

- `dataset_schema.md`：评测集与微调集的字段定义、命名约束与抽样原则
- `celery_case_mining.md`：基于 Celery 当前源码结构整理的样本挖掘热点地图
- `ai_prompt_templates.md`：可以直接发给 AI 的任务 prompt 模板
- `ai_task_breakdown.md`：按阶段拆开的细粒度任务清单，适合排期和分工
- `ai_task_cards.md`：高频任务的标准任务卡，适合直接派发
- `ai_work_batches.md`：任务派发顺序和并行规则，适合连续给 AI 派单
- `candidate_task_packets.md`：首批候选样本 `C01-C12` 的逐条任务包，适合直接拆单
- `detailed_stage_playbook.md`：逐阶段执行手册，明确每一阶段的输入、动作、产出与验收标准
- `eval_case_annotation_template.md`：单条评测样本的人工标注模板与填写规范
- `experiment_log_template.md`：实验记录模板，统一记录模型、Prompt、检索与结果
- `first_batch_candidates.md`：第一批可直接开工的评测样本候选清单
- `execution_roadmap.md`：按阶段推进的落地路线图、里程碑与风险项
- `repo_snapshot.md`：外部分析对象仓库的来源、分支、提交号和拉取时间

### `external/`

- `celery/`：真实分析对象源码，后续评测集、bad case 和微调样本都基于该快照构建

### `evaluation/`

- `baseline.py`：评测入口脚本骨架，负责加载评测集并输出当前数据状态
- `metrics.py`：F1、Recall@K、MRR 等核心指标计算

### `pe/`

- `prompt_templates.py`：System Prompt、CoT 模板、Few-shot 数据结构
- `post_processor.py`：模型输出清洗、FQN 归一化、去重与基本合法性校验

### `rag/`

- `ast_chunker.py`：AST 级别的 Python 代码分块
- `rrf_retriever.py`：混合召回的 RRF 融合逻辑

### `finetune/`

- `data_guard.py`：微调数据校验与脏数据阻断
- `train_qlora.py`：QLoRA 训练配置入口骨架

### `reports/`

- 三份报告模板，分别承接瓶颈诊断、PE 量化与完整消融实验

## 第一版任务拆解

### 阶段 1：数据与评测基线

- 手工梳理 Celery 源码，沉淀 50 条跨文件依赖评测样本
- 明确每条样本的 `question`、`entry_symbol`、`gold_fqns`、`difficulty`
- 跑通 baseline 评测脚本，形成首版错误样本池

### 阶段 2：Prompt Engineering

- 落 System Prompt 的固定输出格式
- 累积 20+ 条高质量 few-shot
- 拆分 CoT 与后处理的独立增益

### 阶段 3：RAG 管线

- 先做 AST 分块
- 再做关键词 / 向量 / 图结构三路召回
- 最后补上下文拼接与端到端评测

### 阶段 4：微调

- 用 LLM 辅助生成候选训练集
- 用 `ast` / `jedi` 做自动验真
- 做 QLoRA 训练与验证集监控

### 阶段 5：答辩材料

- 统一实验矩阵
- 统一表格与图表
- 总结边界条件与推荐策略

## 当前推荐工作流

1. 先阅读 [plan.md](plan.md) 和 [docs/dataset_schema.md](docs/dataset_schema.md)，统一评测口径。
2. 检查 [docs/repo_snapshot.md](docs/repo_snapshot.md)，确认当前分析绑定的 Celery 版本。
3. 阅读 [docs/detailed_stage_playbook.md](docs/detailed_stage_playbook.md)，按阶段执行，不要跳步骤。
4. 如果要让 AI 帮忙执行，先用 [docs/ai_task_breakdown.md](docs/ai_task_breakdown.md) 选任务，再参考 [docs/ai_work_batches.md](docs/ai_work_batches.md) 决定派发顺序，并配合 [docs/ai_task_cards.md](docs/ai_task_cards.md) 和 [docs/ai_prompt_templates.md](docs/ai_prompt_templates.md) 派发。
5. 如果要把首批样本继续拆细，就直接使用 [docs/candidate_task_packets.md](docs/candidate_task_packets.md) 逐条派发 `C01-C12`。
6. 先过一遍 [docs/first_batch_candidates.md](docs/first_batch_candidates.md)，再结合 [docs/celery_case_mining.md](docs/celery_case_mining.md) 和 [docs/eval_case_annotation_template.md](docs/eval_case_annotation_template.md) 开始人工标注。
7. 等评测集稳定后，再开始 PE、RAG、Fine-tune 的逐层实验。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 查看当前评测集状态

```bash
python -m evaluation.baseline --eval-cases data/eval_cases.json
```

### 3. 校验微调数据

```bash
python -m finetune.data_guard data/finetune_dataset.jsonl
```

### 4. 使用 Makefile

```bash
make help
make eval-baseline
make eval-all
```

## 当前状态

这是一版“可继续施工”的骨架，不代表实验已经完成。当前仍需优先补齐以下真实内容：

- `data/eval_cases.json` 中的人工标注评测集
- `data/finetune_dataset.jsonl` 中的高保真微调数据
- `pe/prompt_templates.py` 中的 20+ few-shot 实例
- `rag/` 中与向量检索、BM25、图召回相关的真实实现
- `reports/` 中的实验结果与图表
- `external/celery/` 中的真实分析对象源码与版本记录

## 假设说明

- 以当前目录 `E:\desktop\tengxun` 作为项目根目录
- 暂保留 `plan.md` 与 `task.md` 作为上游需求文档
- 第一版先交付骨架与最小可用脚本，后续再补 Celery 实验数据与模型调用链
- 外部目标仓库默认放在 `external/` 目录下，避免和本项目文档、脚手架混放
