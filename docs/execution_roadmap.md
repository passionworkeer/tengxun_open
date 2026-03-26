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

- 三模型（GPT-5.4 / GLM-5 / Qwen3.5-9B）基线评测
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
- 跑通 LoRA 训练
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
| 7B OOM | 训练无法进行 | 降级到 Qwen3.5-3B |
| 训练超时 | 影响进度 | LoRA rank 从 16 降到 8 |

---

## 当前状态

- ✅ 阶段 0：文档定稿（已完成）
- ✅ 阶段 1：目标仓库准备（已完成，commit: b8f85213）
- ⏳ 阶段 2：评测集构建（32 条新 schema draft 已产出，但正式 `data/eval_cases.json` 仍保持 hold）
- ⏳ 阶段 4：few-shot 正式池已补齐 20 条，`prompt_templates_v2.py` 与 `fewshot_examples_20.json` 已落地；下一步转向高价值 eval 起草
- ⏳ 阶段 6：微调线已完成 schema / guard / train scaffold 对齐，但正式数据仍为 0 条

## 当前并行批次（2026-03-25）

### 已完成草稿

- `docs/drafts/eval_easy_medium_round1.md`：新增 8 条 eval 草稿
- `docs/drafts/eval_hard_round1.md`：新增 8 条 eval 草稿
- `docs/drafts/fewshot_round1.md`：新增 8 条 few-shot 草稿
- `docs/drafts/schema_migration_round2.md`：旧 schema 迁移方案

### 正在进行

- reviewer 双审与仲裁已完成：`medium_006` 可收，`celery_hard_013 / 017` 需修后再收
- 正式评测集迁移 draft 已扩到：`data/eval_cases_migrated_draft_round4.json`（32 条）
- few-shot 扩展审稿链已补齐：`docs/drafts/fewshot_type_a_round3.md` + `docs/drafts/review_round13_type_a_round3.md` + `docs/drafts/review_round12_bc_tail.md` + `docs/drafts/review_round13_bc_arbitration.md` + `docs/drafts/review_round14_strict_challenge.md`
- few-shot 文档已补齐 20 条正式条目：`A01 / A02 / B01-B05 / C01-C05 / D01-D04 / E01-E04`
- A02 已以收紧版回填：默认 app 解析与 `Celery.tasks -> finalize(auto=True)` 已明确拆开
- B05 已以收紧版回填：补足 execv 场景的 env import 时序前置条件，ground truth 只保留首跳入口
- 正式升格审核结论：当前 28 条 draft 暂不替换正式 `data/eval_cases.json`
- 严格 reviewer 新增安全提醒：`B01 / D04 / E03` 已完成收紧修复，并形成 `docs/drafts/review_round15_formal_pool_safety.md`
- 高价值下一批 eval 候选已整理：`docs/drafts/eval_high_value_candidates_round4.md`
- round 4 双轮严格审稿已完成：
  - `docs/drafts/review_round16_eval_round4_gate.md`
  - `docs/drafts/review_round17_eval_round4_findings.md`
  - `docs/drafts/review_round18_eval_round4_r2.md`
- round 4 目前有 4 条可继续推进的高价值 eval：
  - `celery_hard_121`
  - `celery_hard_122`
  - `celery_hard_024`
  - `celery_hard_025`
- 微调线阻塞已显式暴露并收口：
  - `finetune/data_guard.py` 已对齐 `instruction / input / output / difficulty / verified`，并默认卡 `min_records=500` 与 `min_hard_ratio=0.3`
  - `finetune/train_lora.py` 已支持 `--config`，但当前仍是 scaffold-only，未接入真实 trainer backend
  - `configs/lora_9b.toml` 与 `data/finetune_dataset_500.jsonl` 占位已落地
- 仍待继续处理：把 round 4 通过项并入正式待集成队列，并继续保持正式 `data/eval_cases.json` 的 hold

### 下一步顺序

1. 把 `celery_hard_121 / 122 / 024 / 025` 并入正式待集成队列，并保持 formal hold 不变。
2. 继续补下一批 Type A / Type D / hard eval，优先填 `32 -> 50` 的缺口。
3. 启动 500 条微调数据的候选生成，但只在 `data_guard.py` 口径下沉淀干净记录。
