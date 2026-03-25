# Remaining Work Checklist

## 当前执行快照（2026-03-25）

- 主仓库已拉到当前文件夹，GitHub 私有仓库已建立并可同步。
- `external/celery/` 已固定到提交：`b8f85213f45c937670a6a6806ce55326a0eb537f`。
- 正式评测集当前仍是 `data/eval_cases.json`，其中只有旧 schema 的 12 条样本。
- 本轮并行草稿已产出：
  - `docs/drafts/eval_easy_medium_round1.md`：新增 8 条 eval 草稿
  - `docs/drafts/eval_hard_round1.md`：新增 8 条 eval 草稿
  - `docs/drafts/fewshot_round1.md`：新增 8 条 few-shot 草稿
  - `docs/drafts/schema_migration_round2.md`：旧 schema -> 新 schema 迁移方案
- 双 reviewer 审稿已完成：
  - `docs/drafts/review_round2_findings.md`
  - `docs/drafts/review_round3_challenge.md`
- 审稿仲裁已完成：
  - `docs/drafts/review_round4_arbitration.md`
- round 2 修订稿已产出：
  - `docs/drafts/eval_easy_medium_round2.md`
  - `docs/drafts/eval_hard_round2.md`
  - `docs/drafts/fewshot_round2.md`
- round 2 二次复审已完成：
  - `docs/drafts/review_round5_round2.md`
- 尾项复审已完成：
  - `docs/drafts/review_round6_tail.md`
- E03 spot review 已完成：
  - `docs/drafts/review_round8_e03.md`
- Type A / D 的严格审稿已补齐：
  - `docs/drafts/review_round9_type_ad.md`
  - `docs/drafts/type_a_review_notes.md`
  - `docs/drafts/type_d_review_notes.md`
  - `docs/drafts/type_ad_challenge_notes.md`
  - `docs/drafts/review_round10_type_ad_arbitration.md`
- 新 schema 迁移 draft 已产出：
  - `data/eval_cases_migrated_draft.json`（28 条：旧 12 条迁移 + 当前批次已稳定的 eval 条目）
- 正式 few-shot 文档已继续回填：
  - 已并入 `A01`、`B02`、`B03`、`B04`、`C02`、`C03`、`D01`、`D02`、`D03`、`D04`、`E02`、`E03`、`E04`
- 正式升格审核已完成：
  - `docs/drafts/review_round7_eval_dataset.md`
  - 结论：`do_not_promote_yet`
- few-shot 扩展批次已启动：
  - `docs/drafts/fewshot_gap_plan_round1.md`
  - `docs/drafts/fewshot_type_a_round1.md` 已修到 `A01` 可回填
  - `docs/drafts/fewshot_type_a_round2.md` 已产出，`A02` 当前在 `docs/drafts/review_round11_type_a_round2.md` 中为 `needs_more_fix`
  - `docs/drafts/fewshot_type_d_round1.md`、`docs/drafts/fewshot_type_d_round2.md` 已修订并完成仲裁
  - `docs/drafts/fewshot_bc_tail_round1.md` 已产出，待审 `B05 / C04 / C05`
- 当前最高优先级不是继续堆样本，而是先把 `A02` replacement 修过审，再审 `B05 / C04 / C05`，再继续扩 eval。

## 审稿结论摘要

### 双 reviewer 共同通过，可优先进入待集成队列

- `easy_007`
- `medium_005`
- `medium_008`
- `celery_hard_014`
- `celery_hard_016`
- `celery_hard_019`

### 双 reviewer 有分歧，必须先仲裁

- `medium_006`
- `celery_hard_013`
- `celery_hard_017`

### 仲裁结论

- `medium_006`：`keep`
- `celery_hard_013`：`repair`
- `celery_hard_017`：`repair`

### 明确需要修订或重写的 eval 条目

- `easy_005`
- `easy_006`
- `easy_008`
- `medium_007`
- `celery_hard_015`
- `celery_hard_018`
- `celery_hard_020`

### Few-shot 结论

- `fewshot_round1.md` 整体不能直接集成。
- `fewshot_round2.md` 已有一批条目通过二次复审并回填正式文档。
- 当前 round 1 few-shot 主要问题：
  - 与 eval 主链重复过高
  - Type A 的原 A02 题眼错误，不能带入正式 few-shot
  - Proxy / 环境前置 / direct-indirect-implicit 拆分不稳
- 当前 few-shot 正式文档中已稳定的新增条目：
  - `A01`
  - `B02`
  - `B03`
  - `B04`
  - `C02`
  - `C03`
  - `D01`
  - `D02`
  - `D03`
  - `D04`
  - `E02`
  - `E03`
  - `E04`
- A / D 仲裁后的最终结论：
  - `A01`：修订后已可回填正式 few-shot 文档
  - `D01 / D02 / D03 / D04`：修订后已可回填正式 few-shot 文档
  - `A02`：`reject`，需要改题或改入口后重写
- Type A round 2 结论：
  - `A01`：新版已 `accept`
  - `A02`：replacement 已起草，但仍是 `needs_more_fix`
- B / C 尾项状态：
  - `fewshot_bc_tail_round1.md` 已产出，但尚未经过严格 reviewer

## 阶段状态总览

| 阶段 | 目标 | 当前状态 | 下一个关口 |
| :--- | :--- | :--- | :--- |
| 阶段 0 | 文档与口径冻结 | 已完成 | 持续修正文档漂移 |
| 阶段 1 | 仓库快照与版本绑定 | 已完成 | 任何源码更新后回写快照文档 |
| 阶段 2 | 评测集设计与人工标注 | 进行中 | 完成 review + 迁移 draft + 24 条里程碑 |
| 阶段 3 | Baseline 与瓶颈诊断 | 未开始 | 评测集新 schema 稳定后启动 |
| 阶段 4 | Prompt Engineering | 进行中（few-shot 草稿阶段） | 先审 few-shot，再写入正式池 |
| 阶段 5 | RAG | 未开始 | 等阶段 2/4 稳定后进入设计 |
| 阶段 6 | 微调 | 未开始 | 等 bad case 与 schema 冻结 |
| 阶段 7 | 消融与答辩材料 | 未开始 | 等实验结果产出后收口 |

## 当前 P0 清单（必须先做完）

### P0-01：拿到双 reviewer 逐条审稿结论

- 状态：`done`
- 输入：
  - `docs/drafts/eval_easy_medium_round1.md`
  - `docs/drafts/eval_hard_round1.md`
  - `docs/drafts/fewshot_round1.md`
- 输出：
  - `docs/drafts/review_round2_findings.md`
  - `docs/drafts/review_round3_challenge.md`
- 完成标准：
  - 每条 item 都有 `pass / hold / reject`
  - 每条都写具体 objection
  - 有可执行的最小修复建议

### P0-01b：仲裁双 reviewer 的分歧项

- 状态：`done`
- 输入：
  - `docs/drafts/review_round2_findings.md`
  - `docs/drafts/review_round3_challenge.md`
- 输出：
  - `docs/drafts/review_round4_arbitration.md`
- 当前仲裁范围：
  - `medium_006`
  - `celery_hard_013`
  - `celery_hard_017`

### P0-02：冻结旧 -> 新 schema 的迁移执行方案

- 状态：`done`
- 输入：
  - `docs/dataset_schema.md`
  - `data/eval_cases.json`
- 输出：
  - `docs/drafts/schema_migration_round2.md`
- 已明确内容：
  - 旧字段 -> 新字段映射
  - 哪些字段可机械迁移
  - 哪些字段必须人工补齐
  - 推荐先生成迁移 draft，再人工审校

### P0-03：生成旧 12 条样本的新 schema draft

- 状态：`done`
- 前置依赖：
  - P0-01 reviewer 结论到位
  - P0-02 迁移方案冻结
- 输出：
  - `data/eval_cases_migrated_draft.json`
- 完成标准：
  - 旧 12 条全部转为新 schema
  - `failure_type` / `implicit_level` 不再留空
  - `ground_truth.direct_deps / indirect_deps / implicit_deps` 结构统一
  - 当前结果：已形成 18 条 draft（旧 12 条迁移 + 双审共同通过 6 条）

### P0-04：只集成 reviewer 通过的新 eval 草稿

- 状态：`doing`
- 输入：
  - 旧 12 条迁移 draft
  - Round 1 新增 16 条 eval 草稿
  - reviewer 审稿结果
- 输出：
  - 新 schema 版 `data/eval_cases.json`
- 完成标准：
  - 至少达到 24 条有效样本
  - 不混入 `hold / reject` 条目
  - 同步更新数量统计和难度分布
- 当前已知可候选集成：
  - 双 reviewer 共同通过 6 条
  - 仲裁后新增可保留：`medium_006`
  - round 2 二次复审新增可保留：`easy_005`、`easy_006`、`easy_008`、`medium_007`、`celery_hard_013`、`celery_hard_015`、`celery_hard_018`
  - 尾项复审新增可保留：`celery_medium_017`、`celery_medium_020`
  - 当前迁移 draft 已达 28 条，超过“24 条可复核版本”里程碑，但尚未替换正式 `data/eval_cases.json`
  - `review_round7_eval_dataset.md` 的正式结论是：先不升级正式集

### P0-05：把通过审核的 few-shot 回填到正式文档

- 状态：`doing`
- 输入：
  - `docs/fewshot_examples.md`
  - `docs/drafts/fewshot_round1.md`
  - reviewer 审稿结果
- 输出：
  - 更新后的 `docs/fewshot_examples.md`
- 完成标准：
  - 明确哪些空位已经补齐
  - Type B / C / E 的覆盖数有记录
  - 保留未过审项的待办说明
- 当前阻塞原因：
  - Type A 仍缺通过审稿的 `A02` replacement
  - 总量仍未到 20 条，`B05 / C04 / C05` 已起草但还没过审

### P0-05b：为什么正式评测集暂不升级

- 状态：`done`
- 依据：
  - `docs/drafts/review_round7_eval_dataset.md`
- 当前结论：
  - 先不把 `data/eval_cases_migrated_draft.json` 覆盖成正式 `data/eval_cases.json`
- 主要原因：
  - 旧 12 条迁移字段仍需补强复核
  - Type A 缺失、Type D 偏少
  - 总量仍只有 28 条，离 50 条目标有明显差距

### P0-06：更新进度文档并推送

- 状态：`doing`
- 输出：
  - `docs/remaining_work_checklist.md`
  - `docs/execution_roadmap.md`
  - `docs/ai_task_breakdown.md`
  - git commit / push
- 完成标准：
  - 文档状态与仓库实际一致
  - 远端与本地无漂移

## 当前批次的 AI 并行分工

| 线路 | 目标 | 当前产物 | 门禁 |
| :--- | :--- | :--- | :--- |
| Lane A | 新增 Easy / Medium eval 草稿 | `docs/drafts/eval_easy_medium_round1.md` | reviewer 通过后才能入正式集 |
| Lane B | 新增 Hard eval 草稿 | `docs/drafts/eval_hard_round1.md` | reviewer 通过后才能入正式集 |
| Lane C | few-shot 草稿补齐 | `docs/drafts/fewshot_round1.md` | reviewer 通过后才能回填正式文档 |
| Lane D | 旧 schema 迁移方案 | `docs/drafts/schema_migration_round2.md` | 先生成迁移 draft，不直接覆盖正式文件 |
| Lane E | 严格审核 | `review_round2_findings.md` / `review_round3_challenge.md` | 逐条 pass / hold / reject |
| Lane F | Type A / D 对抗审稿与仲裁 | `review_round9_type_ad.md` / `review_round10_type_ad_arbitration.md` | 只有仲裁通过的条目才能回填正式 few-shot |

## 评测集集成门禁

只有同时满足以下条件的内容，才允许进入正式 `data/eval_cases.json`：

1. reviewer 结论为 `pass`，或 `hold` 问题已修完并复审通过。
2. 使用新 schema 全字段结构。
3. FQN 是最终真实符号，不是中间跳板。
4. `difficulty`、`failure_type`、`implicit_level` 三者口径一致。
5. 能回链到当前 `external/celery/` 绑定提交。

## few-shot 集成门禁

只有同时满足以下条件的 few-shot，才允许回填正式文档：

1. 对应明确 bad case 类型。
2. 推理过程至少 4 步，且关键跳转可复核。
3. 不是简单重复已有 eval 样本表述。
4. 输出结构与 `ground_truth.direct_deps / indirect_deps / implicit_deps` 兼容。

## 暂时不允许做的事

- 不要在 reviewer 结果没出来前直接改正式 `data/eval_cases.json`。
- 不要把旧 schema 样本和新 schema 样本混写在同一个正式文件里。
- 不要为了凑满 24 条 / 50 条，把 `hold` 或 `reject` 的样本硬塞进去。
- 不要先写 baseline / RAG / 微调结论，再倒推数据集。

## 达成 24 条里程碑后的下一步

1. 冻结评测集 v0.2，启动 baseline 评测。
2. 从 baseline bad case 反推 few-shot 配比和新增 Hard 样本方向。
3. 继续把评测集从 24 条扩到 50 条。
4. 再进入 RAG / 微调的正式实现阶段。
