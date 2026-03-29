# 微调训练证据审计（2026-03-29）

这份审计不替代原始训练日志，而是把**当前默认 strict-clean 训练证据**整理成更容易答辩引用的结构化结论。

当前权威日志：`logs/strict_clean_20260329.train.log`  
结构化摘要：`results/training_log_summary_20260329.json`  
历史正式配置前置检查：`results/formal_train_env_20260329.json`  
strict replay 前置检查：`results/strict_replay_train_env_20260329.json`

## 1. 已提取出的硬证据

通过执行：

```bash
python3 scripts/analyze_training_log.py \
  --log logs/strict_clean_20260329.train.log \
  --output results/training_log_summary_20260329.json
```

得到以下关键信息：

| 指标 | 数值 |
|---|---:|
| step-level train loss 点数 | `33` |
| step-level eval loss 点数 | `7` |
| 首个 logged train loss | `1.6810` |
| 最后一个 logged train loss | `0.3306` |
| 最低 logged train loss | `0.3124` |
| best eval loss | `0.4661` |
| 最后一次 logged eval loss | `0.4664` |
| checkpoint | `50 / 100 / 150 / 200 / 250 / 300 / 339` |

补充统计：

- 从首个 logged train loss 到最后一个 logged train loss，下降了约 `1.3504`
- `eval_loss` 从 `0.7476` 逐步下降到 `0.4661`
- best eval loss 出现在 `checkpoint-300`

## 2. 可以成立的结论

基于当前日志，以下说法是成立的：

- 训练 loss 整体呈下降趋势，不存在明显发散
- 验证集 loss 有逐步记录，而不是只有最终单点
- 当前证据支持“训练过程收敛稳定，且有逐步验证集监控”
- 由于启用了 `load_best_model_at_end`，当前最终装载模型对应的 eval loss 可按 `0.4661` 理解

## 3. 仍需保持克制的部分

以下说法仍然要讲清边界：

- 不能把历史正式训练线和当前 strict-clean 训练线混成一个结论
- 不能仅凭 loss 曲线就宣称“泛化已经被完全证明”

原因很明确：

- 历史正式训练线确实只有最终 `eval_loss`
- 当前更强的训练证据来自 strict-clean 日志，而不是历史正式日志
- 因此答辩时应明确“当前默认训练证据已经补强”，不要回退去引用旧结论

## 4. 更稳妥的答辩表述

建议统一成这句话：

> 当前默认 strict-clean 训练日志保留了逐步 train / eval 曲线和中间 checkpoint。现有证据显示训练过程收敛稳定、best eval loss 出现在 `checkpoint-300`，已经满足“有监控过拟合”的验收要求；历史正式训练线则仅保留作归档对照。

## 5. 历史正式训练线为什么不再作默认证据

历史正式日志 `logs/train_20260327_143745.log` 仍保留，但它的边界也已经明确：

- `estimated_total_steps ≈ 339`
- `eval_steps = 500`
- `save_steps = 500`
- 因此不会触发中间 eval，也不会产生逐步 `eval_loss`

这条历史训练线现在只用于演进对照，不再作为当前默认交付的训练证据入口。
