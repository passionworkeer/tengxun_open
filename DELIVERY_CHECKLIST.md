# 交付检查清单

> 项目：**Celery 跨文件依赖分析 - PE / RAG / FT 效果优化**
> 版本：v1.0 | 日期：2026-03-29
> 状态：✅ 可交付

---

## 1. 项目概述

| 项目 | 说明 |
|------|------|
| **任务** | 面向腾讯实习考核题：Celery 开源项目上的跨文件依赖分析 |
| **核心能力** | 给定源码片段，识别 direct / indirect / implicit 依赖符号及所在文件 |
| **优化策略** | Prompt Engineering (PE) / RAG 增强检索 / LoRA 微调 |
| **评估口径** | FQN 三层并集精确匹配，54 条手工标注评测集 |

---

## 2. 目录结构

```
tengxun/
├── data/                    # 正式数据资产
│   ├── eval_cases.json              # 54 条评测集（核心）
│   ├── fewshot_examples_20.json    # 20 条 few-shot 示例
│   └── finetune_dataset_500.jsonl  # 500 条微调数据
│
├── evaluation/              # 评测模块
│   ├── baseline.py                   # 数据摘要 / RAG 评测入口
│   ├── metrics.py                    # F1 / Recall / MRR 计算
│   ├── run_gpt_eval.py               # GPT-5.4 评测
│   ├── run_glm_eval.py               # GLM-5 评测
│   ├── run_qwen_eval.py              # Qwen 评测
│   └── run_gpt_rag_eval.py           # GPT 端到端 RAG 评测
│
├── pe/                      # Prompt Engineering
│   ├── prompt_templates_v2.py        # 系统 Prompt + CoT + Few-shot
│   └── post_processor.py              # 输出解析 / 过滤 / 排序
│
├── rag/                      # RAG Pipeline
│   ├── ast_chunker.py                # AST 级代码切片
│   ├── embedding_provider.py          # Embedding 抽象层（Google/ModelScope）
│   └── rrf_retriever.py              # BM25 + 语义 + 图谱三路 RRF 融合
│
├── finetune/                 # 微调
│   ├── train_lora.py                  # LoRA 训练脚本
│   └── data_guard.py                  # 数据质量校验
│
├── configs/                  # 训练配置
├── scripts/                  # 自动化脚本
├── results/                  # 所有评估结果 JSON
├── reports/                  # 正式报告文档
├── docs/                     # 操作指南
├── img/final_delivery/       # 正式图表
├── experiments/              # 未来实验组织层
└── tests/                    # 单元测试
```

---

## 3. 快速启动

### 环境安装

```bash
pip install -r requirements.txt
pip install -r requirements-finetune.txt  # GPU 训练用
```

### 一键复现

```bash
# 数据校验
make lint-data

# 基线评测
make eval-baseline

# PE 评测
make eval-pe

# RAG 评测（需要 GOOGLE_API_KEY）
export EMBEDDING_PROVIDER=google
export GOOGLE_API_KEY=your_key
make eval-rag

# 生成图表
make report
```

### 训练（需 CUDA GPU）

```bash
make train           # 正式训练
make train-strict   # strict-clean 重训
make check-train-env-strict  # 环境检查
```

---

## 4. 核心结论速查

### 主评测表（54-case 正式口径）

| 策略 | Easy | Medium | Hard | Avg | 说明 |
|------|-----:|------:|-----:|----:|------|
| GPT-5.4 Baseline | 0.43 | 0.22 | 0.23 | 0.28 | 商业模型基线 |
| **GPT-5.4 PE** | **0.67** | **0.62** | **0.55** | **0.61** | 最优单项 |
| GPT-5.4 RAG | 0.27 | 0.27 | 0.34 | 0.29 | Hard 场景补偿 |
| Qwen3.5-9B PE + RAG + FT | 0.62 | 0.52 | 0.40 | 0.50 | strict-clean 开源最高分 |
| Qwen3.5-9B PE + FT | 0.52 | 0.54 | 0.26 | 0.43 | 历史正式完整 54-case 参考路线 |

### 关键发现

1. **PE 是最强单项增益**：GPT-5.4 从 0.28 提升至 0.61（+120%）
2. **RAG 定向修复 Hard 场景**：Hard 难度从 0.23→0.34，而非全局无差别提分
3. **PE + FT 是开源性价比最优解**：0.43 分，接近商业模型基线

---

## 5. 交付物清单

| 类型 | 文件 | 说明 |
|------|------|------|
| 📊 图表 | `img/final_delivery/*.png` | 7 张正式图表 |
| 📝 答辩 PPT | `reports/defense_deck_20260329.pptx` | 答辩逐页成品 |
| 📋 答辩稿 | `reports/defense_script_20260329.md` | 主讲稿 |
| 📋 追问 Q&A | `reports/defense_qa_20260329.md` | 导师追问预判 |
| 📄 交付报告 | `reports/DELIVERY_REPORT.md` | 总报告 |
| 📄 消融实验 | `reports/ablation_study.md` | PE/RAG/FT 消融矩阵 |
| 📄 瓶颈诊断 | `reports/bottleneck_diagnosis.md` | 技术瓶颈分析 |
| 📄 数字速查 | `reports/final_numbers_cheatsheet_20260329.md` | 数字一页纸 |
| 📄 提交清单 | `reports/final_submission_checklist_20260329.md` | 答辩前检查 |

---

## 6. 已知限制

| 限制 | 说明 | 状态 |
|------|------|------|
| **LoRA 权重** | strict-clean adapter 未直接提交到仓库，仅提交配置 / 日志 / 结果与 handoff 包 | ⚠️ 如需原始权重需外部保存 |
| **Embedding Cache** | 约 326MB，未进 git（`artifacts/` 已 .gitignore） | 可用 `scripts/precompute_embeddings.py` 重建 |
| **Strict PE + FT** | strict replay 当前仅有 `48/54` 条样本，不作为完整 `54-case` 主结果 | ⚠️ 需补齐或保留历史正式口径 |
| **商业模型 API Key** | GPT/GLM 评测依赖 API Key | ⚠️ 需用户提供 |

---

## 7. 依赖环境

- Python >= 3.11
- A100 40G GPU（训练专用，评测可用 CPU）
- API Keys: `GOOGLE_API_KEY`（RAG）, `OPENAI_API_KEY`（GPT评测）, `ZHIPUAI_API_KEY`（GLM评测）

---

## 8. 权威文档入口

```
reports/DELIVERY_REPORT.md          # 总交付报告
reports/ablation_study.md           # 消融实验报告
reports/bottleneck_diagnosis.md     # 瓶颈诊断
reports/pe_optimization.md          # PE 优化详情
reports/rag_pipeline.md             # RAG 技术方案
docs/official_asset_manifest.md     # 正式资产清单
docs/qwen_strict_gpu_runbook_20260329.md  # CUDA 执行手册
```

---

_本清单最后更新于 2026-03-29_
