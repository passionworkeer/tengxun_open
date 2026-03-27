# Celery 跨文件依赖分析 - 项目文档

## 📁 项目结构

```
tengxun_open/
├── 📄 文档
│   ├── plan.md                     # 项目计划（7天执行方案）
│   ├── task.md                     # 任务说明
│   ├── HYPERPARAMS_REASONING.md    # 超参数选型说明
│   ├── DEPLOYMENT_COMPLETE.md      # 部署完成说明
│   └── DEPLOYMENT_SUMMARY.md       # 部署总结
│
├── 📂 数据集
│   ├── data/eval_cases.json        # 评测数据 (54条)
│   ├── data/eval_cases_final_v1.json # 正式评测集
│   └── data/finetune_dataset_500.jsonl # 微调数据 (500条)
│
├── 🧪 评测模块 (evaluation/)
│   ├── baseline.py                 # 基础评测
│   ├── run_qwen_eval.py            # Qwen评估运行
│   └── metrics.py                  # 评估指标
│
├── 🏷️ 提示工程 (pe/)
│   └── prompt_templates_v2.py      # System Prompt + CoT + Few-shot
│
├── 🔍 RAG检索 (rag/)
│   ├── ast_chunker.py              # AST代码分块
│   └── rrf_retriever.py            # 三路RRF检索
│
├── 🎯 模型微调 (finetune/)
│   ├── train_lora.py               # LoRA训练配置
│   └── data_guard.py               # 数据验证流水线
│
├── 📊 实验结果 (results/)
│   └── *.json                      # 各模型评测结果
│
└── 🚀 脚本
    ├── scripts/
    │   ├── step1_baseline.sh       # Step 1: 基线测试
    │   ├── step2_train.sh          # Step 2: 启动微调
    │   ├── step3_ft_eval.sh        # Step 3: FT评测
    │   ├── step4_pe_ft.sh          # Step 4: PE+FT评测
    │   ├── step5_pe_rag_ft.sh      # Step 5: PE+RAG+FT评测
    │   └── run_qwen_eval.sh        # Qwen评测脚本
    │
    ├── train_lora.sh               # 一键训练脚本
    ├── run_finetune_with_logging.sh # 完整训练(带日志)
    ├── check_download.sh           # 检查模型下载
    └── start_qwen_vllm.sh          # 启动vLLM服务
```

## 🚀 快速开始

### 1. 基线测试 (Step 1)
```bash
cd tengxun_open
bash scripts/step1_baseline.sh
```

### 2. 启动微调训练 (Step 2)
```bash
cd tengxun_open
bash scripts/step2_train.sh
# 或带完整日志
bash run_finetune_with_logging.sh
```

### 3. 后续评测 (Step 3-5)
```bash
bash scripts/step3_ft_eval.sh      # FT评测
bash scripts/step4_pe_ft.sh        # PE+FT评测
bash scripts/step5_pe_rag_ft.sh    # PE+RAG+FT评测
```

## 📊 数据说明

### 评测集 (eval_cases.json)
- **数量**: 54条
- **难度**: Easy 15条, Medium 19条, Hard 20条
- **来源**: Celery源码人工标注

### 微调数据集 (finetune_dataset_500.jsonl)
- **数量**: 500条
- **难度**: Hard 162, Easy 163, Medium 175
- **验证**: 全部通过data_guard验证

### 失效类型分类 (5类)
| 类型 | 描述 |
|------|------|
| Type A | 长上下文截断丢失 |
| Type B | 隐式依赖断裂（装饰器） |
| Type C | 再导出链断裂 |
| Type D | 跨文件命名空间混淆 |
| Type E | 动态加载与字符串引用失配 |

## 🔬 消融实验矩阵

| 实验组 | 说明 |
|--------|------|
| Baseline (Qwen3.5-9B) | 基线，未优化 |
| PE only | 纯提示词工程 |
| RAG only | 纯检索增强 |
| FT only | 领域微调 |
| PE + RAG | 提示词 + 检索 |
| PE + FT | 提示词 + 微调 |
| PE + RAG + FT | 完整策略 |

## 📋 超参数配置

训练配置见 `lora_config.yaml`:
- **模型**: Qwen/Qwen3.5-9B
- **LoRA rank**: 8
- **学习率**: 5e-5
- **batch**: 1 (accum 8)
- **epoch**: 3
- **精度**: bf16

详细说明见 `HYPERPARAMS_REASONING.md`

## 📞 支持

- 查看训练日志: `logs/training_YYYYMMDD_HHMMSS/`
- 查看 результат: `results/`
- 监控GPU: `nvidia-smi`

---

**项目计划**: 7天完成，包含模块1-6的完整实验