# 腾讯考核题 - Celery 跨文件依赖分析项目深度分析报告

> 生成时间：2026-04-12
> 分析方法：Agent Team 并行深度分析（3 个专业 Agent）
> 被分析项目：`E:\desktop\tengxun\tengxun_open`

---

## 一、项目概述与背景

### 1.1 项目基本信息

| 项目属性 | 值 |
|---------|-----|
| **项目名称** | celery-dep-analysis（腾讯实习考核题） |
| **核心任务** | Celery 开源项目的跨文件依赖符号解析 |
| **评测对象版本** | `external/celery @ b8f85213` (Celery 5.6.2) |
| **交付时间** | 2026-03-29 |
| **技术栈** | Python 3.11+ / PE / RAG / LoRA 微调 |
| **硬件需求** | A100 40G GPU（训练专用），CPU 可评测 |
| **评测集规模** | 54 条手工标注 |
| **微调数据集** | 500 条 strict-clean |
| **Few-shot 库** | 20 条 strict-clean |

### 1.2 核心能力要求

项目面向腾讯实习考核题，需要模型具备以下能力：
- 给定源码片段，识别 `direct / indirect / implicit` 三层依赖关系
- 处理再导出链、装饰器流程、动态字符串目标、长多跳链路等复杂场景
- 输出结构化 FQN（Fully Qualified Name）JSON 格式

### 1.3 评测集分布

| 维度 | 分布 |
|------|------|
| **Difficulty** | Easy 15 / Medium 19 / Hard 20 |
| **Failure Type** | Type A 7 / Type B 9 / Type C 11 / Type D 11 / Type E 16 |
| **Entry 模式** | 54/54 含 source_file，5/54 另有 entry_symbol |

---

## 二、技术架构总览

### 2.1 系统架构流程图

```
┌─────────────────────────────────────────────────────────┐
│                    输入层（Eval Case）                    │
│  question + entry_file (+ 可选 entry_symbol)             │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                  Prompt Engineering (PE)                  │
│  System Prompt  │  CoT Template  │  Few-shot Examples  │
│  (角色定义+输出格式)  (链式推理引导)  (按失效类型配比选例)    │
│                            │
│                            ▼
│  Post-Processor：JSON解析 + FQN规范化 + 去重 + 格式校验  │
└─────────────────────────────────────────────────────────┘
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│   GPT-5.4        │ │   Qwen3.5-9B     │ │   Qwen + FT          │
│   (商业模型)      │ │   (开源基线)      │ │   (LoRA微调)          │
└──────────────────┘ └──────────────────┘ └──────────────────────┘
           └──────────────────┼──────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────┐
│                         评测指标层                        │
│  Union F1 (三层并集) │ Macro F1 (活跃层平均) │ Mislayer Rate │
└─────────────────────────────────────────────────────────┘
```

### 2.2 RAG Pipeline 架构

```
                   Query输入
                      │
                      ▼
┌────────────────────────────────────────────────────────┐
│                  Query 模式选择                          │
│           question_only | question_plus_entry           │
└────────────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌────────┐   ┌───────────┐   ┌────────┐
   │  BM25  │   │ Semantic   │   │ Graph  │
   │  索引   │   │ (Embedding)│   │  索引   │
   └────────┘   └───────────┘   └────────┘
        │             │             │
        └─────────────┼─────────────┘
                      ▼
               ┌─────────────┐
               │  RRF融合    │
               │ (k=30)      │
               └─────────────┘
                      │
                      ▼
         ┌─────────────────────────┐
         │ Top-K Context Build    │
         │ (Token Budget: 4096)   │
         └─────────────────────────┘
                      │
                      ▼
                   生成模型
```

### 2.3 模块依赖关系

```
evaluation/
├── baseline.py          ← 评测入口、数据加载、RAG检索评测
├── metrics.py           ← F1/Recall/MRR 指标计算
├── run_gpt_eval.py      ← GPT-5.4 评测
├── run_glm_eval.py      ← GLM-5 评测
└── run_qwen_eval.py     ← Qwen 评测

pe/
├── prompt_templates_v2.py  ← System Prompt + CoT + Few-shot 模板
├── prompt_templates.py      ← 旧版模板（归档）
└── post_processor.py       ← JSON解析 + FQN规范化

rag/
├── ast_chunker.py          ← AST级代码分块
├── embedding_provider.py    ← Embedding抽象层(Google/ModelScope)
└── rrf_retriever.py        ← 三路检索 + RRF融合

finetune/
├── train_lora.py           ← LoRA训练脚本
└── data_guard.py           ← 数据质量校验

scripts/
├── generate_final_delivery_assets.py  ← 图表生成
├── build_strict_datasets.py           ← strict数据集构建
├── precompute_embeddings.py           ← Embedding预计算
├── check_train_env.py                 ← 训练环境检查
└── run_pe_eval.py                     ← PE评测脚本
```

---

## 三、数据资产清单与质量分析

### 3.1 核心数据集总览

| 数据集 | 文件路径 | 规模 | 状态 |
|--------|---------|------|------|
| **正式评测集** | `data/eval_cases.json` | 54条 | 全部手工标注 |
| **Few-shot库** | `data/fewshot_examples_20_strict.json` | 20条 | strict-clean |
| **微调数据集** | `data/finetune_dataset_500_strict.jsonl` | 500条 | strict-clean |
| 历史正式few-shot | `data/fewshot_examples_20.json` | 20条 | 归档对照 |
| 历史正式微调集 | `data/finetune_dataset_500.jsonl` | 500条 | 归档对照 |

### 3.2 数据质量保障

| 保障措施 | 实现 |
|---------|------|
| FQN格式校验 | 正则 `^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)+$` |
| FQN路径存在性 | `data_guard.py` 对Celery内部FQN做源码校验 |
| 白名单机制 | 外部依赖包做显式放行 |
| Overlap审计 | 对`eval_cases.json`做三层（Exact/Question/Hard）overlap检查 |
| strict-clean | 微调数据与评测集完全去污染 |

---

## 四、Prompt Engineering（PE）方案详解

### 4.1 PE 四阶段优化路径效果（GPT-5.4）

| 阶段 | Easy | Medium | Hard | Avg | 相对Baseline增益 |
|------|-----:|-------:|-----:|----:|----------------:|
| baseline | 0.3907 | 0.2602 | 0.2010 | 0.2745 | — |
| system_prompt | 0.4306 | 0.3039 | 0.2356 | 0.3138 | +0.0393 |
| cot | 0.4791 | 0.4170 | 0.3834 | 0.4218 | +0.1080 |
| fewshot | 0.6492 | 0.5351 | 0.5525 | 0.5733 | +0.1515 |
| postprocess | **0.6651** | **0.6165** | **0.5522** | **0.6062** | +0.0329 |
| **postprocess_targeted** | **0.6895** | **0.6493** | **0.5774** | **0.6338** | **+0.3523** |

**核心结论**：PE是当前最强单项优化，相对baseline提升 **+120.8%**。

### 4.2 PE 关键设计

- **System Prompt**：角色定义 + 输出格式约束
- **CoT Template**：5步链式推理 checklist
- **Layer Guard Rules**：三层依赖边界定义
- **Few-shot 选例**：多因子评分（token重叠度/失效类型/入口符号/长链路加分）
- **Post-Processor**：JSON解析 + FQN规范化 + 去重 + 白名单过滤

---

## 五、RAG Pipeline 详解

### 5.1 核心指标

| View | Recall@5 | MRR |
|------|---------:|-----:|
| fused chunk_symbols | 0.4305 | 0.5292 |
| fused expanded_fqns | 0.4502 | 0.5596 |

### 5.2 三路检索效果对比

| Source | Chunk Recall@5 | Expanded Recall@5 |
|--------|---------------:|------------------:|
| BM25 | 0.2569 | 0.4345 |
| Semantic | 0.1767 | 0.1377 |
| Graph | 0.3772 | 0.3596 |
| **Fused (RRF)** | **0.4305** | **0.4502** |

### 5.3 RAG 端到端效果

| 指标 | No-RAG | With-RAG | Delta |
|------|--------|---------|-------|
| Overall Avg F1 | 0.2783 | 0.2940 | **+0.0157** |
| Easy | 0.3963 | 0.2722 | -0.1241 |
| Medium | 0.2696 | 0.2656 | -0.0040 |
| Hard | 0.1980 | 0.3372 | **+0.1392** |

**核心发现**：RAG的价值是"定向修复hard场景"，而非全局提分。

### 5.4 RAG 按 Failure Type 分析

| Failure Type | n | Chunk Recall@5 | 检索难度 |
|-------------|---:|-------------:|:--------|
| Type C (Re-export) | 11 | 0.8636 | 简单（路径清晰）|
| Type A (Lifecycle) | 7 | 0.4837 | 中等 |
| Type D (Namespace) | 11 | 0.4773 | 中等 |
| Type B (Decorator) | 9 | 0.2333 | 较难 |
| **Type E (Dynamic)** | 16 | **0.1882** | **最难** |

---

## 六、微调方案详解

### 6.1 训练配置（strict-clean）

```yaml
model_name_or_path: Qwen/Qwen3.5-9B
quantization_bit: 4              # QLoRA 4bit量化
finetuning_type: lora
lora_rank: 4
lora_alpha: 8
dataset: finetune_qwen_dep_strict
cutoff_len: 512
per_device_train_batch_size: 1
gradient_accumulation_steps: 4   # effective_batch=4
learning_rate: 5.0e-5
num_train_epochs: 3.0
bf16: true
val_size: 0.1
```

### 6.2 strict-clean FT Family 效果

| 策略 | Easy | Medium | Hard | Avg | 说明 |
|------|-----:|-------:|-----:|----:|------|
| Qwen Baseline | 0.0667 | 0.0526 | 0.0000 | 0.0370 | strict recovered |
| Qwen FT only | 0.1556 | 0.0895 | 0.0500 | 0.0932 | strict-clean |
| Qwen PE + FT | 0.5307 | 0.4277 | 0.2393 | **0.3865** | strict-clean，低复杂度 |
| Qwen PE + RAG + FT | 0.6168 | 0.5196 | 0.3986 | **0.5018** | strict-clean，开源最优 |

---

## 七、实验结果分析

### 7.1 主评测结果矩阵（54-case 正式口径）

| 策略 / 模型 | Easy | Medium | Hard | Avg | 说明 |
|------------|-----:|-------:|-----:|----:|------|
| GPT-5.4 Baseline | 0.4348 | 0.2188 | 0.2261 | 0.2815 | 商业模型基线 |
| GLM-5 Baseline | 0.1048 | 0.0681 | 0.0367 | 0.0666 | 官方API |
| Qwen3.5-9B Baseline | 0.0667 | 0.0526 | 0.0000 | 0.0370 | strict recovered |
| GPT-5.4 PE | **0.6651** | **0.6165** | **0.5522** | **0.6062** | **最优单项** |
| GPT-5.4 RAG | 0.2722 | 0.2656 | 0.3372 | 0.2940 | Hard场景补偿 |
| Qwen PE + RAG + FT | 0.6168 | 0.5196 | 0.3986 | **0.5018** | 开源最强 |
| Qwen PE + FT | 0.5307 | 0.4277 | 0.2393 | 0.3865 | 低复杂度路线 |

### 7.2 层级质量分析（strict-clean）

| 策略 | Avg Union | Avg Macro | Avg Mislayer | Exact Layer |
|------|----------:|----------:|-------------:|------------:|
| Qwen FT only | 0.0932 | 0.0833 | 0.0185 | 0.0556 |
| Qwen PE + FT | 0.3865 | 0.2998 | 0.1198 | 0.0926 |
| Qwen PE + RAG + FT | 0.5018 | 0.3645 | 0.2207 | 0.1481 |

### 7.3 失效类型分析

| Failure Type | 含义 | 样本数 | PE前 | PE后 | 主要增益来源 |
|-------------|------|--------|------|------|-------------|
| Type A | 长上下文链路 | 7 | 0.1329 | 0.5133 | CoT |
| Type B | 隐式依赖/装饰器 | 9 | 0.1669 | 0.5502 | Few-shot |
| Type C | 再导出链 | 11 | 0.3939 | 0.7394 | Post-process |
| Type D | 命名空间混淆 | 11 | 0.2904 | 0.6159 | Few-shot |
| Type E | 动态加载/symbol_by_name | 16 | 0.2297 | 0.5801 | Few-shot |

### 7.4 关键发现

1. **PE是最强杠杆**：商业模型提升120%+，开源模型提升500%+
2. **RAG是hard场景补偿器**：Hard +0.139，但Easy反而-0.124
3. **FT需与PE协同**：单独FT效果有限，PE+FT >> FT only
4. **Qwen PE+RAG+FT = 0.5018**：开源最优完整路线

---

## 八、代码质量与工程化分析

### 8.1 总体评级

| 维度 | 评分 | 说明 |
|------|------|------|
| **算法质量** | A | 核心算法（RRF、AST分块、分层指标）设计严谨、科学 |
| **代码规范** | B+ | 类型标注完整、注释充分，但部分文件过大 |
| **测试覆盖** | C+ | 评测和校验逻辑测试充分，但核心检索模块无测试 |
| **工程化** | B | 架构清晰、Makefile完善，但配置不一致、硬编码路径多 |
| **可维护性** | B | 代码可读性好，但全局状态和大文件是长期隐患 |

**综合评级**：B+（工程价值高，核心算法优秀，测试覆盖和工程化细节需加强）

### 8.2 核心模块质量评级

| 模块 | 文件 | 评级 | 说明 |
|------|------|------|------|
| Post-Processor | `pe/post_processor.py` | A | FQN正则、规范化、去重逻辑完整 |
| AST Chunker | `rag/ast_chunker.py` | A | 函数/类/模块四级粒度，语义完整 |
| Data Guard | `finetune/data_guard.py` | A | FQN存在性验证、三层Overlap审计严密 |
| Metrics | `evaluation/metrics.py` | A | Active-layer macro F1 设计科学 |
| RRF Retriever | `rag/rrf_retriever.py` | A- | 算法优秀，但1047行过大，有全局状态问题 |
| Baseline | `evaluation/baseline.py` | A- | 双Schema兼容，但baseline.py 755行过大 |
| Embedding Provider | `rag/embedding_provider.py` | B+ | 多Provider抽象好，缓存容错逻辑需加强 |
| Train LoRA | `finetune/train_lora.py` | B+ | 功能实用，但手写YAML解析器脆弱 |
| PE Eval Script | `scripts/run_pe_eval.py` | B+ | 11种策略覆盖全面，但API端点硬编码 |

### 8.3 必须修复的问题

1. **`rag/rrf_retriever.py` 全局状态**：`test_train_lora.py` 中 `_GLOBAL_CHUNK_REGISTRY` 的跨实例共享会在多测试场景下导致状态污染
2. **RAG 检索无测试**：`rag/rrf_retriever.py`（核心模块）完全没有测试
3. **AST 分块无测试**：`rag/ast_chunker.py` 没有单元测试

### 8.4 强烈建议修复

4. **拆分 `rag/rrf_retriever.py`**（1047行 → 建议拆分 3-4 个文件）
5. **`strict_clean_20260329.yaml` 配置不一致**：缺少 `save_strategy`、`load_best_model_at_end`
6. **数据集别名 typo**：`fintune_qwen_dep_strict` 应为 `finetune_qwen_dep_strict`
7. **`run_pe_eval.py` 硬编码配置**：API_BASE_URL、DEFAULT_MODEL 应外置
8. **`generate_final_delivery_assets.py` 输入路径硬编码**

---

## 九、报告体系说明

| 报告 | 文件 | 用途 |
|------|------|------|
| 交付总报告 | `reports/DELIVERY_REPORT.md` | 项目整体交付 |
| 消融实验 | `reports/ablation_study.md` | 策略矩阵分析 |
| 瓶颈诊断 | `reports/bottleneck_diagnosis.md` | 低分共性问题 |
| PE优化 | `reports/pe_optimization.md` | 四阶段PE效果 |
| RAG管线 | `reports/rag_pipeline.md` | RAG技术方案 |
| 答辩PPT | `reports/defense_deck_20260329.pptx` | 正式答辩 |
| 数字速查 | `reports/final_numbers_cheatsheet_20260329.md` | 一页纸总结 |

### 图表清单

```
img/final_delivery/
├── 01_model_baselines_20260328.png      # 模型基线对比
├── 02_pe_progression_20260328.png       # PE逐步增益
├── 03_bottleneck_heatmap_20260328.png   # 瓶颈热力图
├── 04_rag_retrieval_20260328.png       # RAG检索表现
├── 05_rag_end_to_end_20260328.png      # RAG端到端增益
├── 06_qwen_strategies_20260328.png     # Qwen组合策略
└── 07_training_curve_20260328.png      # 训练曲线
```

---

## 十、技术债务与遗留问题

### 10.1 已识别问题

| 问题 | 影响 | 解决方案 |
|------|------|---------|
| 326MB Embedding Cache未进git | 换机器需重建 | `make prepare-rag-cache`自动重建 |
| strict-clean与历史正式并存 | 口径混淆风险 | README明确标注当前默认 |
| GPT-5.4依赖API Key | 无法离线评测 | 需用户提供 |
| Qwen baseline解析失败率高 | 45/54 parse fail | PE约束已缓解 |
| Hard场景仍是短板 | Hard avg < 0.40 | PE+RAG+FT协同 |

### 10.2 遗留优化方向

1. **条件式RAG触发**：只对hard/TypeA/TypeE启用RAG
2. **层级精细优化**：继续降低mislayer rate
3. **更大规模微调**：当前500条可扩展到1000+
4. **模型蒸馏**：基于GPT-5.4的PE经验蒸馏到开源模型

---

## 十一、项目完成度矩阵

| 题目要求 | 要求 | 当前状态 | 完成度 |
|---------|------|---------|--------|
| 真实项目评测集 | ≥50条 | 54条手工标注 | 100% |
| 低分瓶颈分析 | 识别共性问题 | 5类失效类型全覆盖 | 100% |
| PE四维优化 | 量化每步贡献 | 完整四阶段实验 | 100% |
| RAG Pipeline | 检索+融合 | 三路RRF融合 | 100% |
| 微调数据集 | ≥500条 | 500条strict-clean | 100% |
| LoRA微调 | 训练+评测 | 完整矩阵落盘 | 100% |
| 消融矩阵 | 完整策略组合 | PE/RAG/FT全矩阵 | 100% |
| 报告体系 | 结构化交付 | 10+份报告 | 100% |

---

## 十二、环境状态总结

### 12.1 Celery 版本确认

```
Celery 版本：5.6.2
Commit: b8f85213f45c937670a6a6806ce55326a0eb537f
来源：Gitee 镜像 + checkout 到指定 commit
位置：E:\desktop\tengxun\tengxun_open\external\celery
```

### 12.2 Git 状态

```
分支：main
最新提交：5d3cd87 tighten delivery report audit wording
工作区：干净
远程：origin + upstream 均已绑定
```

### 12.3 注意事项

- `artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json` (~326MB) 未进git
- `LLaMA-Factory` 子模块映射已失效，不影响运行
- `external/celery_gitee` 为临时镜像，已清理

---

## 附录：Agent Team 分析摘要

| Agent | 分析方向 | 状态 |
|-------|---------|------|
| Explore | 项目结构、架构、数据资产 | ✅ 完成 |
| data-scientist | 实验结果、指标分析、效果对比 | ✅ 完成 |
| Code Reviewer | 代码质量、工程化、测试覆盖 | ✅ 完成 |

生成报告：2026-04-12
分析工具：Claude Agent Team（3 Agent 并行）
