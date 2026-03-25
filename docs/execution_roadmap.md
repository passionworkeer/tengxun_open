# Execution Roadmap

本文件是"简版路线图"。如果要按阶段执行，请直接配合 [detailed_stage_playbook.md](detailed_stage_playbook.md) 一起使用。

## 总体策略

项目按"文档先行、样本先行、实验后置"的顺序推进，避免一开始就陷入工具实现，却没有稳定评测口径。

## 七天执行计划

| 天 | 核心任务 | 不可压缩的事 | 产物 |
|----|---------|------------|------|
| **Day 1** ★ | 人工标注 50 条评测集 | 读 Celery 源码，自己设计陷阱用例 | `eval_cases_celery.json` |
| **Day 2** | 三模型基线评测 + 瓶颈归因 | 手动分析 Bad Case，映射到 Type A-E | 失效热力图 + bad case 清单 |
| **Day 3** | PE 四维度逐步优化 | 严格单变量，每步独立记录 | `prompt_templates_v2.py` + 增益表 |
| **Day 4** ‖ | 500 条数据集构建 + 启动训练 | `data_guard.py` 验证后再批量生成 | `finetune_dataset_500.jsonl` |
| **Day 5** ‖ | RAG Pipeline 构建 | GPU 跑训练，并行写 RAG | `ast_chunker.py` + `rrf_retriever.py` |
| **Day 6** | 完整消融矩阵 + 可视化 | 10 组实验口径统一，画雷达图 | `ablation_full_matrix.ipynb` |
| **Day 7** | 工程化收尾 + 报告润色 | README Executive Summary 放最前面 | 全部产物打包 |

> ★ Day 1 是最关键的一天，护城河在这里。‖ Day 4 启动训练后 GPU 并行运行，不浪费等待时间。
> **风险 Fallback**：若 7B OOM → 降级 3B；若训练超时 → LoRA rank 从 16 降到 8。

---

## 阶段划分

### 阶段 0：文档定稿（Day 0）

- 对齐 [task.md](../task.md) 的验收要求
- 修正 [plan.md](../plan.md) 中的失效类型与实验口径
- 固化评测集、微调集字段定义

阶段完成标志：

- 方案文档无前后矛盾
- 数据 schema 明确
- 交付清单明确
- 已有可执行阶段手册

### 阶段 1：目标仓库准备（Day 0）

- 拉取 Celery 官方仓库
- 记录仓库地址、默认分支、当前提交号
- 确定后续分析只针对该快照进行

阶段完成标志：

- `external/celery/` 可用
- 已记录版本信息
- 已明确后续样本都绑定当前提交号

### 阶段 2：评测集构建（Day 1）★

- 人工梳理不少于 50 条样本
- 先做 Easy 和 Medium，再集中补 Hard
- 每条样本都要能回链到真实源码
- 每条样本都按统一模板完成证据链标注

阶段完成标志：

- 50 条评测样本齐备
- 难度分布满足 15 / 20 / 15 的目标比例
- 第一批 12 条样本已先行打通流程

### 阶段 3：Baseline 与瓶颈诊断（Day 2）

- 三模型（GPT-4o / GLM-5 / Qwen2.5-Coder-7B）基线评测
- 抽取 bad cases
- 将错误映射到 Type A-E 失效类型
- 绘制失效分布热力图

阶段完成标志：

- 有 Easy / Medium / Hard 分层指标
- 有失效分布图和代表性 bad cases
- bad case 已映射到 Type A-E

### 阶段 4：PE 优化（Day 3）

- System Prompt 固定
- CoT 模板设计
- Few-shot 库构建（20+ 条）
- 后处理规则
- **严格单变量逐步叠加**

阶段完成标志：

- 四项增益可单独量化
- 有可复用的 Prompt 文档
- few-shot 覆盖主要 bad case 类型

### 阶段 5：RAG 与微调（Day 4-5）

- 完成 AST 分块与三路混合检索设计
- 完成微调数据清洗（data_guard.py）
- 跑通 QLoRA 训练
- GPU 训练与 RAG 开发并行

阶段完成标志：

- Recall@5、MRR 可汇报
- 微调数据集满足数量和质量要求（≥500 条）
- 有检索模块独立评测结果
- 有 train/val loss 曲线

### 阶段 6：消融实验与答辩材料（Day 6-7）

- 跑全矩阵（10 组实验）
- 统一图表（雷达图/柱状图/热力图）
- 形成最优策略与边界结论
- Bad Case 专栏（2-3 个典型案例）

阶段完成标志：

- 10 组实验结果齐备（含三个 Baseline）
- README、报告、图表可直接展示
- 最优策略与边界条件可直接讲述
- 能区分"分数最高""ROI 最优""高隐式依赖唯一解"

---

## 风险与应对

| 风险 | 影响 | 应对 |
| :--- | :--- | :--- |
| Hard 样本不足 | 微调和 All 方案优势不明显 | 尽早优先抽样装饰器、自动发现、字符串入口样本 |
| 评测口径漂移 | 各阶段结果无法横向比较 | 先冻结 schema，再开始大规模造数 |
| 仓库版本漂移 | 数据无法复现 | 每轮实验绑定提交号 |
| 过早实现工具 | 代码很多但结果无法验收 | 以样本和指标为主线，工具后补 |
| 7B OOM | 训练无法进行 | 降级到 Qwen2.5-Coder-3B |
| 训练超时 | 影响进度 | LoRA rank 从 16 降到 8 |

---

## 当前状态

- ✅ 阶段 0：文档定稿（已完成）
- ✅ 阶段 1：目标仓库准备（已完成，commit: b8f85213）
- ⏳ 阶段 2：评测集构建（旧 12 条仍待迁移到新 schema）
- ⏳ 阶段 4：few-shot 正式回填中（Type D 已补齐，A01 已回填，A02 待 replacement）

## 当前并行批次（2026-03-25）

### 已完成草稿

- `docs/drafts/eval_easy_medium_round1.md`：新增 8 条 eval 草稿
- `docs/drafts/eval_hard_round1.md`：新增 8 条 eval 草稿
- `docs/drafts/fewshot_round1.md`：新增 8 条 few-shot 草稿
- `docs/drafts/schema_migration_round2.md`：旧 schema 迁移方案

### 正在进行

- reviewer 双审与仲裁已完成：`medium_006` 可收，`celery_hard_013 / 017` 需修后再收
- 正式评测集迁移 draft 已产出：`data/eval_cases_migrated_draft.json`（28 条）
- A / D few-shot 审稿链已补齐：`docs/drafts/review_round9_type_ad.md` + `docs/drafts/review_round10_type_ad_arbitration.md`
- Type A round 2 已产出并完成严格复审：`docs/drafts/fewshot_type_a_round2.md` + `docs/drafts/review_round11_type_a_round2.md`
- few-shot 文档已回填：`A01 / B02 / B03 / B04 / C02 / C03 / D01 / D02 / D03 / D04 / E02 / E03 / E04`
- A / D 仲裁结论：修订后 `A01`、`D01-D04` 可集成；`A02` round 2 replacement 已起草，但当前仍是 `needs_more_fix`
- B / C 尾项草稿已产出：`docs/drafts/fewshot_bc_tail_round1.md`（待正式审稿）
- 正式升格审核结论：当前 28 条 draft 暂不替换正式 `data/eval_cases.json`
- 仍待继续处理：继续收紧 `A02` replacement，并审 `B05 / C04 / C05`

### 下一步顺序

1. 先修 `docs/drafts/fewshot_type_a_round2.md` 里的 `A02`，让 replacement 过线。
2. 再审 `docs/drafts/fewshot_bc_tail_round1.md`，决定 `B05 / C04 / C05` 哪些可直接回填。
3. 继续补 eval 的 Type A / Type D / hard 配额，但在更强复核前不升级正式 `data/eval_cases.json`。
