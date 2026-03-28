# experiments 目录说明

这个目录用于放置“实验组织层”的内容，而不是正式原始结果。

当前项目的正式实验资产主要分布在以下位置：

- 原始结果：`results/`
- 正式报告：`reports/`
- 图表输出：`img/final_delivery/`
- 图表生成脚本：`scripts/generate_final_delivery_assets.py`

之所以保留 `experiments/` 目录，是为了给后续两类内容留稳定位置：

1. 消融矩阵补充实验
2. Notebook / 可视化原型 / 临时分析草稿

当前推荐的正式阅读顺序是：

1. `README.md`
2. `reports/DELIVERY_REPORT.md`
3. `reports/ablation_study.md`
4. `reports/bottleneck_diagnosis.md`

如果后续需要补 Notebook，建议放在这里，并遵守以下规则：

- 文件名使用中文或清晰的英文语义名
- Notebook 只做分析展示，不作为唯一真相来源
- 最终结论必须回写到 `reports/` 和 `README.md`
