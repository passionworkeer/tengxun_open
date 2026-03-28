# 微调训练证据审计（2026-03-29）

这份审计不替代正式训练日志，而是把已有日志整理成更容易答辩引用的结构化结论。

原始日志：`logs/train_20260327_143745.log`  
结构化摘要：`results/training_log_summary_20260329.json`

## 1. 已提取出的硬证据

通过执行：

```bash
python3 scripts/analyze_training_log.py \
  --log logs/train_20260327_143745.log \
  --output results/training_log_summary_20260329.json
```

得到以下关键信息：

| 指标 | 数值 |
|---|---:|
| step-level train loss 点数 | `33` |
| 首个 logged train loss | `1.6770` |
| 最后一个 logged train loss | `0.4021` |
| 最低 logged train loss | `0.3247` |
| 最终 train loss | `0.5720` |
| 最终 eval loss | `0.4779` |
| 训练时长 | `0:37:12.92` |
| 最终评测时长 | `0:00:19.77` |

补充统计：

- 从首个 logged train loss 到最后一个 logged train loss，下降了 `1.2749`
- `32` 个相邻步中，有 `18` 个是下降的
- 日志里没有 step-level `eval_loss` 曲线

## 2. 可以成立的结论

基于当前日志，以下说法是成立的：

- 训练 loss 整体呈下降趋势，不存在明显发散
- 最终 `eval_loss = 0.4779` 低于最终 `train_loss = 0.5720`
- 当前证据支持“训练过程收敛稳定”，不支持“出现明显后期崩溃或过拟合尖峰”

## 3. 不能过度声称的部分

以下说法仍然不能讲得太满：

- 不能说“已经有完整的逐步验证集曲线证明不过拟合”
- 不能说“已经做了最强形式的 overfitting monitoring”

原因很明确：

- 日志里只有最终 `eval_loss`
- `llamafactory` 在本次正式跑线上没有产出 step-level `eval_loss` plot
- 原始日志里仍然保留了 `No metric eval_loss to plot`

## 4. 更稳妥的答辩表述

建议统一成这句话：

> 正式训练日志保留了 33 个 step-level train loss 点和最终 `eval_loss=0.4779`。现有证据显示训练过程收敛稳定、没有明显发散，但由于没有逐步验证集曲线，关于“不过拟合”的证据强度仍然是中等，不是最强形式。

## 5. 下一步怎样把证据补到最硬

如果后续在 strict-clean 训练线上重跑，建议同时保证三件事：

1. 保存 step-level train loss
2. 保存 step-level eval loss
3. 把 strict adapter 对应的 `FT only / PE + FT / PE + RAG + FT` 一起重评

这样答辩时就可以把“训练证据强度中等”进一步升级成“训练与验证双曲线完整保留”。
