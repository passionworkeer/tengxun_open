# Celery 跨文件依赖分析项目

## 项目概述

本项目聚焦**跨文件依赖分析（Cross-file Dependency Analysis）**方向，选取真实复杂开源项目 `Celery` 作为评测标的，研究如何通过 **提示词工程（PE）**、**检索增强生成（RAG）** 和 **模型微调（FT）** 三种手段提升大模型在代码依赖分析任务上的表现。

### 核心研究问题

> 经过 LoRA 领域微调的 9B 模型，在窄域任务上能否以 1/10 推理成本逼近顶级模型？

这是工业界真正关心的 ROI 问题。

---

## 核心研究成果

| 发现 | 描述 |
|------|------|
| **共性天花板** | GPT-5.4 在 Hard 级隐式依赖场景下召回率显著下降，当前所有模型的共性瓶颈是 **Type D/E 类失效** |
| **RAG 补偿效果** | 三路 RRF RAG 对 Type C/D 有显著补偿，但对 Type E（动态加载/字符串映射）无效 |
| **工程建议** | 仅对 `implicit_level ≥ 3` 的模块启用完整 RAG+FT 策略，约占 35%，可节省约 65% Token 消耗 |

---

## 模型基线

| 模型 | 类型 | 定位 |
|------|------|------|
| GPT-5.4 | 闭源商业 | 国际顶尖商业模型天花板 |
| GLM-5 | 开源 MIT | 开源代码模型最强 |
| Qwen3.5-9B | 开源，本地微调 | 微调基座，ROI 研究目标 |

---

## 技术架构

```
代码解析层
    └── tree-sitter AST 分块
        按函数 / 类 / 全局作用域精确切割

索引层（三路并行）
    ├── 向量索引：CodeBERT / text-embedding-3-small
    ├── BM25 索引：函数名 + 类名 + 模块名关键词精确匹配
    └── 图索引：import + 继承树 NetworkX 构图

融合层
    └── RRF(k=60) 三路合并

上下文管理
    ├── Top-1 直接依赖：全量代码片段
    ├── Top-2~5 间接依赖：函数签名 + Docstring（压缩）
    └── Token 超限时：摘要压缩
```

---

## 项目结构

```
celery-dep-analysis/
├── README.md                      # 本文档
├── Makefile                      # 快捷命令入口
├── plan.md                       # 完整实施方案
├── task.md                       # 考核任务要求
│
├── data/                         # 数据目录
│   ├── eval_cases.json           # 正式评测集（12 条旧 schema）
│   ├── eval_cases_migrated_draft_round4.json  # 新 schema draft（32 条）
│   ├── fewshot_examples_20.json  # 20 条 few-shot 示例库
│   └── finetune_dataset_500.jsonl # 微调数据集（500 条）
│
├── evaluation/                   # 评测模块
│   ├── baseline.py               # 数据集概览 / prompt 预览 / RAG 检索评测
│   └── metrics.py                # Recall@K / MRR 等指标计算
│
├── pe/                           # 提示词工程模块
│   ├── prompt_templates_v2.py    # System Prompt + CoT + Few-shot 库
│   └── post_processor.py         # FQN 格式校验 + 去重 + 过滤
│
├── rag/                          # 检索增强模块
│   ├── ast_chunker.py            # AST 代码级分块
│   └── rrf_retriever.py          # BM25 / semantic / graph + RRF 融合检索
│
├── finetune/                     # 微调模块
│   ├── data_guard.py             # 数据验证流水线（防幻觉）
│   └── train_lora.py             # LoRA 训练脚手架
│
├── reports/                      # 分析报告
│   ├── bottleneck_diagnosis.md   # 瓶颈诊断报告
│   ├── pe_optimization.md        # PE 优化报告
│   └── ablation_study.md         # 消融实验报告
│
├── docs/                         # 项目文档
│   ├── dataset_schema.md         # 数据集字段定义
│   ├── celery_case_mining.md     # Celery 源码挖掘指南
│   └── ...
│
└── external/celery/             # Celery 源码快照
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 查看评测集摘要

```bash
python -m evaluation.baseline --eval-cases data/eval_cases.json
```

### 3. 验证微调数据集

```bash
python -m finetune.data_guard data/finetune_dataset_500.jsonl
```

### 4. 运行评测

```bash
# 基线评测
make eval-baseline

# PE 消融
make eval-pe

# RAG 检索评测
make eval-rag

# 完整消融矩阵
make eval-all

# 训练模型
make train
```

---

## 失效类型分类

基于基线测试的 Bad Case 归纳出 5 类失效模式：

| 类型 | 失效特征 | 典型案例 |
|------|---------|---------|
| **Type A** | 长上下文截断丢失 | 超出窗口导致上游定义节点被遗漏 |
| **Type B** | 隐式依赖断裂（幻觉） | `@app.task` 装饰器注册时模型编造不存在的内部调用 |
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

## 数据格式

### 评测案例 (eval_cases.json)

```json
{
  "id": "celery_hard_021",
  "question": "分析 celery.app.task.Task.__call__ 的完整依赖链",
  "source_file": "celery/app/task.py",
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

### 微调数据 (finetune_dataset_500.jsonl)

```jsonl
{"instruction": "分析以下 Python 函数的完整跨文件依赖链", "input": "...", "output": "...", "difficulty": "hard", "verified": true}
```

---

## 注意事项

### 编码问题

- 所有 JSON 文件使用 `UTF-8` 编码，带 BOM 标记
- 读取时使用 `encoding="utf-8-sig"` 以兼容带 BOM 的文件
- 写入时使用 `ensure_ascii=False` 以正确输出中文

### 依赖版本

- Python 3.10+
- 请参考 `requirements.txt` 获取完整依赖列表

---

## 文档索引

- [plan.md](plan.md) - 完整实施方案
- [task.md](task.md) - 考核任务要求
- [docs/dataset_schema.md](docs/dataset_schema.md) - 数据集字段定义
- [docs/detailed_stage_playbook.md](docs/detailed_stage_playbook.md) - 逐阶段执行手册
- [docs/celery_case_mining.md](docs/celery_case_mining.md) - Celery 源码挖掘指南
