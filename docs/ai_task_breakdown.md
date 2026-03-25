# AI Task Breakdown

## 文档目标

本文件把整个项目拆成适合交给 AI 执行的细粒度任务清单。目标不是“描述方向”，而是让 AI 或协作者拿到任务后能直接开工。

每个任务都尽量满足以下要求：

- 一次只解决一个明确问题
- 输入、输出、依赖清晰
- 能在完成后被快速验收
- 不把“人工判断”和“自动执行”混在一起

## 使用方法

1. 先看 [detailed_stage_playbook.md](detailed_stage_playbook.md)，明确当前项目在整体流程中的位置。
2. 再从本文件中挑选当前阶段的 task。
3. 真正发给 AI 时，优先配合 [ai_task_cards.md](ai_task_cards.md) 和 [ai_prompt_templates.md](ai_prompt_templates.md) 使用。

## 任务状态建议

- `todo`：还没开始
- `ready`：依赖齐全，可以直接做
- `doing`：正在执行
- `review`：已产出，需要人工复核
- `done`：已验收
- `blocked`：依赖未满足或存在风险

## 总体优先级

### P0：必须先完成

- 冻结文档口径
- 冻结仓库快照
- 完成首批 12 条样本

### P1：可以并行推进

- 扩展到 50 条评测样本
- baseline 评测与 bad case 分类
- few-shot 库准备

### P2：中期重点

- RAG 设计
- 微调数据集构建
- 实验日志与报告模板收口

### P3：后期收口

- 消融实验矩阵
- 报告图表
- 答辩材料

---

## 阶段 0：文档与口径冻结

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| DOC-001 | 复核考核要求与方案差异 | P0 | AI + 人工复核 | 无 | 差异清单 |
| DOC-002 | 统一失效类型定义 | P0 | AI | DOC-001 | `plan.md` 修订 |
| DOC-003 | 冻结评测集字段规范 | P0 | AI | DOC-001 | `dataset_schema.md` |
| DOC-004 | 冻结微调集字段规范 | P0 | AI | DOC-003 | `dataset_schema.md` |
| DOC-005 | 建立实验日志模板 | P1 | AI | DOC-001 | `experiment_log_template.md` |
| DOC-006 | 建立阶段执行手册 | P1 | AI | DOC-001 | `detailed_stage_playbook.md` |

## 阶段 1：目标仓库快照与版本绑定

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| REPO-001 | 拉取 Celery 仓库 | P0 | AI | 无 | `external/celery/` |
| REPO-002 | 记录仓库快照信息 | P0 | AI | REPO-001 | `repo_snapshot.md` |
| REPO-003 | 生成源码结构概览 | P1 | AI | REPO-001 | `celery_case_mining.md` 初稿 |
| REPO-004 | 列出高价值样本热点 | P1 | AI | REPO-003 | 热点清单 |

## 阶段 2：评测集设计与人工标注

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EVAL-001 | 建立首批候选样本清单 | P0 | AI | REPO-004 | `first_batch_candidates.md` |
| EVAL-002 | 标注 Easy 样本第 1 批 | P0 | AI 起草 + 人工复核 | EVAL-001 | 4 条样本草稿 |
| EVAL-003 | 标注 Medium 样本第 1 批 | P0 | AI 起草 + 人工复核 | EVAL-001 | 4 条样本草稿 |
| EVAL-004 | 标注 Hard 样本第 1 批 | P0 | AI 起草 + 人工复核 | EVAL-001 | 4 条样本草稿 |
| EVAL-005 | 审核首批 12 条样本 | P0 | 人工主导 | EVAL-002,EVAL-003,EVAL-004 | 首批正式样本 |
| EVAL-006 | 扩展 Easy 样本到 15 条 | P1 | AI 起草 + 人工复核 | EVAL-005 | Easy 完整集 |
| EVAL-007 | 扩展 Medium 样本到 20 条 | P1 | AI 起草 + 人工复核 | EVAL-005 | Medium 完整集 |
| EVAL-008 | 扩展 Hard 样本到 15 条 | P1 | AI 起草 + 人工复核 | EVAL-005 | Hard 完整集 |
| EVAL-009 | 统一样本格式并写入 `eval_cases.json` | P1 | AI | EVAL-006,EVAL-007,EVAL-008 | 正式评测集 |
| EVAL-010 | 做样本抽检与去歧义 | P1 | 人工主导 | EVAL-009 | 抽检记录 |

## 阶段 3：Baseline 与瓶颈诊断

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| BASE-001 | 定义 baseline 模型与参数口径 | P1 | AI + 人工确认 | EVAL-009 | baseline 配置说明 |
| BASE-002 | 设计 baseline 结果记录表 | P1 | AI | BASE-001 | 结果表模板 |
| BASE-003 | 运行 baseline 并收集原始结果 | P1 | AI | BASE-001,EVAL-009 | 原始结果 |
| BASE-004 | 计算 Easy / Medium / Hard 分层指标 | P1 | AI | BASE-003 | 指标表 |
| BASE-005 | 提取 bad cases | P1 | AI | BASE-003 | bad case 清单 |
| BASE-006 | 将 bad case 归类到 Type A-E | P1 | AI 起草 + 人工复核 | BASE-005 | 错误分类表 |
| BASE-007 | 写瓶颈诊断报告初稿 | P1 | AI | BASE-004,BASE-006 | `bottleneck_diagnosis.md` |

## 阶段 4：Prompt Engineering

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| PE-001 | 固定 System Prompt v1 | P1 | AI | BASE-006 | prompt 草案 |
| PE-002 | 固定 CoT 模板 v1 | P1 | AI | BASE-006 | CoT 草案 |
| PE-003 | 从 bad case 反推 few-shot 类型配比 | P1 | AI | BASE-006 | few-shot 配比计划 |
| PE-004 | 编写 Easy few-shot 样本 | P1 | AI + 人工复核 | PE-003 | few-shot 草稿 |
| PE-005 | 编写 Medium few-shot 样本 | P1 | AI + 人工复核 | PE-003 | few-shot 草稿 |
| PE-006 | 编写 Hard few-shot 样本 | P1 | AI + 人工复核 | PE-003 | few-shot 草稿 |
| PE-007 | 设计输出后处理规则 | P1 | AI | PE-001 | 后处理方案 |
| PE-008 | 跑 PE 逐步叠加实验 | P1 | AI | PE-001,PE-002,PE-004,PE-005,PE-006,PE-007 | 分步实验结果 |
| PE-009 | 写 PE 量化报告 | P1 | AI | PE-008 | `pe_optimization.md` |

## 阶段 5：RAG

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| RAG-001 | 定义 AST 分块规范 | P2 | AI | EVAL-009 | chunk 设计文档 |
| RAG-002 | 定义向量检索候选方案 | P2 | AI | RAG-001 | embedding 方案比较 |
| RAG-003 | 定义关键词检索方案 | P2 | AI | RAG-001 | BM25 方案 |
| RAG-004 | 定义图结构召回方案 | P2 | AI | RAG-001 | graph 方案 |
| RAG-005 | 定义 RRF 融合与窗口管理 | P2 | AI | RAG-002,RAG-003,RAG-004 | 融合策略 |
| RAG-006 | 制定检索评测方案 | P2 | AI | RAG-005,EVAL-009 | Recall@5 / MRR 评测说明 |
| RAG-007 | 跑检索模块独立评测 | P2 | AI | RAG-006 | 检索指标表 |
| RAG-008 | 跑 RAG 端到端实验 | P2 | AI | RAG-007,PE-008 | RAG 结果 |
| RAG-009 | 写 RAG 部分总结 | P2 | AI | RAG-008 | 报告内容 |

## 阶段 6：微调

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| FT-001 | 定义微调样本生成策略 | P2 | AI | BASE-006 | 数据生成方案 |
| FT-002 | 生成候选微调数据第 1 批 | P2 | AI | FT-001 | 候选数据 |
| FT-003 | 设计自动校验规则 | P2 | AI | FT-001 | 校验方案 |
| FT-004 | 清洗第 1 批候选数据 | P2 | AI | FT-002,FT-003 | 干净数据 |
| FT-005 | 扩展候选数据到 500+ | P2 | AI | FT-004 | 微调全集 |
| FT-006 | 审核 Hard 样本比例 | P2 | AI + 人工复核 | FT-005 | 配比记录 |
| FT-007 | 制定 LoRA / QLoRA 实验配置 | P2 | AI | FT-005 | 配置文档 |
| FT-008 | 跑 Fine-tune only 实验 | P2 | AI | FT-007 | 微调结果 |
| FT-009 | 记录训练与验证曲线 | P2 | AI | FT-008 | 训练记录 |

## 阶段 7：消融实验与答辩材料

| Task ID | 任务名 | 优先级 | 执行者 | 依赖 | 输出 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| ABL-001 | 冻结实验矩阵和指标口径 | P3 | AI + 人工确认 | PE-008,RAG-008,FT-008 | 实验矩阵说明 |
| ABL-002 | 跑 Baseline / PE / RAG / FT 单项实验 | P3 | AI | ABL-001 | 单项结果 |
| ABL-003 | 跑 PE + RAG | P3 | AI | ABL-001 | 组合结果 |
| ABL-004 | 跑 PE + Fine-tune | P3 | AI | ABL-001 | 组合结果 |
| ABL-005 | 跑 All | P3 | AI | ABL-001 | 最终结果 |
| ABL-006 | 汇总所有结果并生成图表数据 | P3 | AI | ABL-002,ABL-003,ABL-004,ABL-005 | 总表 |
| ABL-007 | 写消融实验报告 | P3 | AI | ABL-006 | `ablation_study.md` |
| ABL-008 | 提炼最优策略和边界条件 | P3 | AI + 人工确认 | ABL-007 | 结论清单 |
| ABL-009 | 生成答辩提纲 | P3 | AI | ABL-008 | 答辩提纲 |

---

## 当前建议直接执行的任务

### 适合立刻交给 AI 的

- EVAL-002
- EVAL-003
- EVAL-004
- EVAL-006
- EVAL-007
- EVAL-008

### 需要人工强参与的

- EVAL-005
- EVAL-010
- BASE-006
- FT-006
- ABL-008

---

## 当前活动批次（2026-03-25）

本节只记录当前这一轮真实在跑的任务，便于直接分发给 AI 或子 agent。

| Task ID | 任务名 | 状态 | 输入 | 输出 | 完成条件 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EVAL-011 | 新增 Easy / Medium 样本草稿 Round 1 | review | `external/celery/`、`dataset_schema.md` | `docs/drafts/eval_easy_medium_round1.md` | reviewer 逐条给出 verdict |
| EVAL-012 | 新增 Hard 样本草稿 Round 1 | review | `external/celery/`、`dataset_schema.md` | `docs/drafts/eval_hard_round1.md` | reviewer 逐条给出 verdict |
| PE-010 | 补齐 few-shot 空位 Round 1 | review | `docs/fewshot_examples.md`、`external/celery/` | `docs/drafts/fewshot_round1.md` | reviewer 逐条给出 verdict |
| EVAL-013 | 旧 schema -> 新 schema 迁移方案 | done | `data/eval_cases.json`、`docs/dataset_schema.md` | `docs/drafts/schema_migration_round2.md` | 映射表、风险、步骤齐备 |
| EVAL-014 | 双 reviewer 对抗式审稿 | done | `review_round1.md` + 3 份草稿 | `review_round2_findings.md`、`review_round3_challenge.md` | 每条 item 均有 pass/hold/reject |
| EVAL-015 | 仲裁双 reviewer 分歧项 | done | 两份 review 文件 + 原始草稿 | `docs/drafts/review_round4_arbitration.md` | 争议项有最终 keep/repair/drop |
| EVAL-016 | 旧 12 条样本迁移为新 schema draft | done | `schema_migration_round2.md`、审稿结论 | `data/eval_cases_migrated_draft.json` | 旧 12 条全部迁移且字段齐全 |
| EVAL-017 | 将通过审核的新样本合入正式评测集 | doing | 迁移 draft + pass 条目 | `data/eval_cases.json` | 正式集至少 24 条，新 schema 统一 |
| PE-011 | few-shot round 2 重写 | doing | `fewshot_round1.md` + review objection | `docs/drafts/fewshot_round2.md` | 先产出不泄漏 eval 的修订版 |
| PE-012 | round 2 修订稿二次复审 | done | `eval_easy_medium_round2.md`、`eval_hard_round2.md`、`fewshot_round2.md` | `docs/drafts/review_round5_round2.md` | 修订稿得到 accept / needs_more_fix / reject |
| PE-013 | 将通过审核的 few-shot 回填正式文档 | doing | 二次复审结论 + `fewshot_round2.md` | `docs/fewshot_examples.md` | 正式 few-shot 文档已补齐一批空位 |
| PE-014 | 继续修订未过审 few-shot | doing | `review_round5_round2.md` | `docs/drafts/fewshot_round3.md` | B03 / B04 / E03 过线或被替换 |
| PE-015 | few-shot 尾项 final review | done | `eval_remaining_round3.md`、`fewshot_round3.md` | `docs/drafts/review_round6_tail.md` | 尾项得到 accept / needs_more_fix / reject |
| PE-016 | 修复 few-shot E03 与继续补齐 Type A / D | todo | `review_round6_tail.md`、正式 few-shot 文档 | `docs/drafts/fewshot_round4.md` 或等价产物 | few-shot 结构更完整，E03 过线 |
| PM-001 | 更新阶段进度并推送远端 | todo | 当前进展与审稿结论 | 进度文档 + git push | 本地与远端一致 |

## 当前批次的质量门禁

### 对 eval 草稿

1. 不允许 mixed schema。
2. 不允许用中间跳板符号充当最终 `ground_truth`。
3. 不允许 `difficulty` 和 `implicit_level` 明显失配。
4. 不允许与旧 12 条高重复。

### 对 few-shot 草稿

1. 不允许只做“问题换皮”。
2. 不允许把 easy 题伪装成 hard 对抗样例。
3. 不允许没有清晰 bad case 对应关系。
4. 不允许输出结构与正式 schema 脱节。

## 任务拆分原则补充

- 如果一个任务同时需要“读源码 + 造数据 + 写报告”，就拆成至少两个 task。
- 如果一个任务的产出无法在 10 分钟内被人工看懂，也要继续拆。
- 任何需要事实真值的任务，都必须保留“AI 起草 + 人工复核”环节。
