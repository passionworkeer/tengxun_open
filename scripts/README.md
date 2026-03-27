# 脚本说明

## 🎯 评测跑线脚本

| 脚本 | 用途 | 命令 |
|------|------|------|
| `step1_baseline.sh` | 基线测试（未微调） | `bash step1_baseline.sh` |
| `step2_train.sh` | 启动微调训练 | `bash step2_train.sh` |
| `step3_ft_eval.sh` | FT模型评测 | `bash step3_ft_eval.sh` |
| `step4_pe_ft.sh` | PE+FT评测 | `bash step4_pe_ft.sh` |
| `step5_pe_rag_ft.sh` | PE+RAG+FT评测 | `bash step5_pe_rag_ft.sh` |

## 🛠️ 工具脚本

| 脚本 | 用途 |
|------|------|
| `run_qwen_eval.sh` | Qwen评估运行 |
| `check_download.sh` | 检查模型下载进度 |
| `start_qwen_vllm.sh` | 启动vLLM服务 |

## 🚀 完整跑线

```bash
# Step 1: 基线测试
cd tengxun_open
bash scripts/step1_baseline.sh

# Step 2: 启动微调（等Step1完成）
bash scripts/step2_train.sh

# Step 3-5: 评测
bash scripts/step3_ft_eval.sh
bash scripts/step4_pe_ft.sh
bash scripts/step5_pe_rag_ft.sh
```

## 📊 输出结果

评测结果保存在 `results/`:
- `qwen_baseline.json` - 基线结果
- `qwen_ft_results.json` - FT结果
- `qwen_pe_ft_results.json` - PE+FT结果
- `qwen_pe_rag_ft_results.json` - 完整策略结果

## ⚡ 实时监控

```bash
# 查看vLLM服务
curl http://localhost:8000/v1/models

# 查看训练日志
tail -f logs/train.log

# 查看GPU
nvidia-smi
```