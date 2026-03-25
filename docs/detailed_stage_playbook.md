# Detailed Stage Playbook

## 文档目标

本文件把项目拆成可执行的阶段手册。每个阶段都明确：

- 这一阶段为什么做
- 开始前必须具备什么
- 具体要做哪些事
- 产出什么文档或数据
- 什么时候算完成
- 常见风险是什么

适用范围：当前工作区 `E:\desktop\tengxun`，分析对象绑定为 `external/celery/` 对应的 Celery 快照。

如果要把任务分配给 AI 协助执行，请同时参考：

- [ai_task_breakdown.md](ai_task_breakdown.md)
- [ai_task_cards.md](ai_task_cards.md)
- [ai_prompt_templates.md](ai_prompt_templates.md)

## 总体推进原则

1. 先冻结口径，再大规模造数。
2. 先做人工可复核的数据，再做自动化。
3. 先拿到 baseline 和 bad case，再谈优化。
4. 每次实验只改一个关键变量，确保消融成立。
5. 每个阶段都要沉淀成文档，而不是只留在聊天或临时笔记里。

## 当前执行状态（2026-03-25）

- 阶段 0 已完成：主方案、执行路线、AI 分工文档已经落地。
- 阶段 1 已完成：`external/celery/` 已绑定到固定提交。
- 阶段 2 正在推进到“24 条可复核版本”里程碑：
  - 旧版正式集仍有 12 条旧 schema 样本
  - 新一轮 16 条 eval 草稿已经独立写入 `docs/drafts/`
  - schema migration 方案已经独立写成草稿
  - 严格 reviewer 正在逐条审稿
- 阶段 4 也已提前进入 few-shot 草稿阶段，但正式 few-shot 文档尚未回填。

当前真实下一步不是继续无脑造数，而是先完成 review -> migration draft -> approved integration 这条链。

---

## 阶段 0：文档与口径冻结

### 阶段目标

- 把考核题目、技术路线、评测口径、命名规范统一
- 消除方案内部的前后矛盾
- 让后续样本构建和实验记录有统一模板

### 开始前条件

- 已有 [task.md](../task.md)
- 已有 [plan.md](../plan.md)
- 已确认分析方向为“跨文件依赖分析”

### 具体动作

1. 复核题目要求，明确低难度与中难度的差异。
2. 修正 `plan.md` 中术语、失效类型、实验矩阵和边界条件的口径不一致。
3. 明确评测集字段规范、微调集字段规范、命名规范。
4. 明确实验日志模板，保证后续每次实验都能追溯。
5. 明确样本挖掘指南，避免后续标注全靠临场判断。

### 本阶段产出

- [plan.md](../plan.md)
- [docs/dataset_schema.md](dataset_schema.md)
- [docs/execution_roadmap.md](execution_roadmap.md)
- [docs/ai_task_breakdown.md](ai_task_breakdown.md)
- [docs/ai_task_cards.md](ai_task_cards.md)
- [docs/ai_prompt_templates.md](ai_prompt_templates.md)
- [docs/eval_case_annotation_template.md](eval_case_annotation_template.md)
- [docs/experiment_log_template.md](experiment_log_template.md)
- [docs/celery_case_mining.md](celery_case_mining.md)

### 完成标准

- 失效类型、实验矩阵、交付物不再互相冲突
- 评测集和微调集字段定义明确
- 新同学只看文档就知道下一步要做什么

### 风险与处理

- 风险：文档写得太抽象，无法指导实际标注
- 处理：必须提供真实文件路径、候选样本和字段模板

---

## 阶段 1：目标仓库快照与版本绑定

### 阶段目标

- 把真实分析对象固定到当前文件夹
- 绑定仓库地址、分支、提交号和拉取时间
- 确保后续所有样本、报告和实验都对应同一份源码

### 开始前条件

- 阶段 0 已完成
- 当前工作区可以联网拉取仓库

### 具体动作

1. 将 Celery 官方仓库拉到 `external/celery/`。
2. 记录远程地址、分支、提交号和拉取时间。
3. 明确后续文件路径统一相对 `external/celery/` 记录。
4. 规定如果未来切换提交号，必须补充新的快照说明。

### 本阶段产出

- [docs/repo_snapshot.md](repo_snapshot.md)
- [external/celery](../external/celery)

### 完成标准

- `external/celery/` 可正常访问
- `git` 能在该目录中识别工作树
- 文档已记录绑定版本

### 风险与处理

- 风险：后面更新源码但忘记更新文档
- 处理：每次 `pull`、`checkout` 或重新 clone 后，必须回写 `repo_snapshot.md`

---

## 阶段 2：评测集设计与人工标注

### 阶段目标

- 构建至少 50 条高质量人工评测样本
- 样本必须来自真实 Celery 源码，而不是 AI 编造
- 样本要覆盖 easy / medium / hard 三个层次

### 开始前条件

- 阶段 1 完成，仓库版本已冻结
- 已有字段规范和标注模板

### 具体动作

#### 2.1 样本池准备

1. 通读 [docs/celery_case_mining.md](celery_case_mining.md)。
2. 从 [docs/first_batch_candidates.md](first_batch_candidates.md) 开始选第一批候选。
3. 建立候选池，不急着直接写入正式评测集。

#### 2.2 单条样本标注

每条样本都要完成以下内容：

1. 明确问题定义，只问一个清晰问题。
2. 记录 `source_file` 和 `source_commit`，必要的入口符号信息可写入 `source_note`。
3. 追踪真实依赖链，分别写出：
   - `ground_truth.direct_deps`
   - `ground_truth.indirect_deps`
   - `ground_truth.implicit_deps`
4. 用“证据链”写清楚是怎么从源码走到答案的，至少覆盖关键跳转。
5. 给样本打 `difficulty`、`category`、`failure_type`、`implicit_level` 标签。
6. 写 `reasoning_hint`，但不要把最终答案直接泄露成一句话抄写。

#### 2.3 样本质检

1. 每 10 条样本做一次抽检。
2. Hard 样本必须二次复核。
3. 有歧义的样本要么补证据，要么删掉，不允许带病入库。
4. AI 起草内容先进入独立草稿文件，不直接改正式评测集。
5. reviewer 必须逐条给出 `pass / hold / reject`。
6. `hold / reject` 条目修完前，不允许合入正式集。

#### 2.4 旧 schema 迁移

当前仓库已有 12 条旧 schema 样本，因此阶段 2 不只是“继续新增”，还要补做迁移：

1. 先根据 `docs/dataset_schema.md` 生成迁移 draft，不直接改正式文件。
2. 将旧字段映射到新字段结构，统一 `ground_truth` 子字段。
3. 人工补齐 `failure_type`、`implicit_level` 以及必要的 `indirect_deps / implicit_deps`。
4. 迁移后的旧样本也要走 reviewer 复核，不能因为“原来就在库里”就跳过。

#### 2.5 比例控制

- Easy：15 条
- Medium：20 条
- Hard：15 条

### 推荐执行顺序

1. 先完成 12 条首批样本，确保流程可用。
2. 再扩展到 30 条，覆盖所有主要类别。
3. 最后补足到 50 条，并修正难度分布不平衡的问题。

### 本阶段产出

- [docs/first_batch_candidates.md](first_batch_candidates.md)
- `data/eval_cases.json`
- `docs/drafts/eval_easy_medium_round1.md`
- `docs/drafts/eval_hard_round1.md`
- `docs/drafts/schema_migration_round2.md`
- reviewer 审稿文档
- 人工标注时产生的中间笔记或抽检记录

### 完成标准

- 正式评测集不少于 50 条
- 正式评测集已统一到新 schema
- 每条样本都能回溯到真实源码
- 难度分布达到目标比例
- 每条样本都有可复核证据链

### 风险与处理

- 风险：样本全是简单 import，无法支撑中难度考核
- 处理：优先抽样 `shared_task`、`connect_on_app_finalize`、`symbol_by_name`、`importlib`

- 风险：样本问题定义太大，一题包含多条链
- 处理：强制“一条样本只问一个问题”

---

## 阶段 3：Baseline 跑分与瓶颈诊断

### 阶段目标

- 测出当前 baseline 的真实表现
- 找出 low-score 样本的共性
- 用错误样本支撑“瓶颈诊断”，而不是主观猜测

### 开始前条件

- 阶段 2 的评测集已经成型
- 已明确要比较哪些模型作为 baseline

### 具体动作

1. 固定 baseline 模型与推理参数。
2. 在全量评测集上跑一次完整评测。
3. 统计 Easy / Medium / Hard 的分层指标。
4. 把错误样本按 Type A-E 分类。
5. 记录代表性 bad case，至少覆盖每一类主要失效。
6. 绘制失效类型和难度分布图。

### 本阶段产出

- `reports/bottleneck_diagnosis.md`
- baseline 实验日志
- bad case 列表

### 完成标准

- 有分层 F1 或等价指标
- 有错误样本表和失效类型归因
- 能回答“模型为什么错”而不是只会报一个总分

### 风险与处理

- 风险：只记录总分，没有错误类型
- 处理：每个错误样本至少记录“错在什么环节”

- 风险：同一种错误被归到不同类别
- 处理：先写失效类型判断规则，再集中归类

---

## 阶段 4：Prompt Engineering 优化

### 阶段目标

- 系统性优化 Prompt，而不是零散试几句提示词
- 拆出 System Prompt、CoT、Few-shot、Post-processing 的独立增益

### 开始前条件

- 已有 baseline 结果和 bad case 分析
- 已知道 Hard 样本主要错在哪些模式

### 具体动作

#### 4.1 System Prompt

1. 固定角色定义，例如“资深 Python 静态分析专家”。
2. 固定输出格式，只允许输出 FQN JSON 列表。
3. 压缩无关解释，降低输出噪声。

#### 4.2 CoT

1. 把推理步骤固定为入口识别、显式 import、隐式依赖、最终路径组装。
2. 对比有无 CoT 的提升。

#### 4.3 Few-shot

1. 从 bad case 中反推 few-shot 类型分布。
2. 优先覆盖再导出链、`shared_task`、动态加载、字符串映射。
3. 至少准备 20 条高质量示例。

#### 4.4 Post-processing

1. 统一输出解析规则。
2. 去重、过滤无效 FQN、规避明显幻觉格式。

### 实验要求

- 必须逐步叠加，不能一次性把所有优化全开
- 每次只新增一个组件，保留前一步结果

### 本阶段产出

- `reports/pe_optimization.md`
- Prompt 版本记录
- few-shot 库

### 完成标准

- 四项优化都有独立量化结果
- 能说清楚哪一步最有效、对哪类样本最有效

### 风险与处理

- 风险：few-shot 很多，但没有针对 bad case
- 处理：few-shot 来源优先取自阶段 3 的错误样本

- 风险：后处理把错误掩盖成“看起来更干净”
- 处理：后处理只做格式净化，不做事实修正

---

## 阶段 5：RAG 设计与检索评测

### 阶段目标

- 建立适合代码依赖分析的检索管线
- 独立评测检索质量，而不是只看最终生成结果

### 开始前条件

- PE 方案已经有可对比版本
- 评测集稳定，不再频繁改 schema

### 具体动作

#### 5.1 AST 分块

1. 以函数、类、全局作用域为单位切块。
2. 记录每个 chunk 对应的文件、符号、行号范围。

#### 5.2 多路检索

1. 向量检索：比较 `CodeBERT` 和 `text-embedding-3-small`。
2. 关键词检索：BM25 覆盖变量名、类名、函数名。
3. 图结构召回：import 图、继承关系、注册关系。

#### 5.3 融合与上下文管理

1. 用 RRF 融合多路结果。
2. Top-1 放完整 chunk，Top-2~5 放压缩上下文。
3. 记录 token 成本，避免盲目加上下文。

#### 5.4 检索评测

1. 对每条样本计算 Recall@5。
2. 计算 MRR。
3. 分析哪些类别最容易召回失败。

### 本阶段产出

- 检索实验日志
- `reports/ablation_study.md` 中的检索部分
- RAG 设计说明

### 完成标准

- Recall@5、MRR 都能稳定汇报
- 能解释三路检索各自的贡献

### 风险与处理

- 风险：只看端到端分数，不看检索本身好坏
- 处理：检索模块必须单独评估

- 风险：向量检索覆盖不到字符串映射和 alias
- 处理：必须保留关键词检索和图结构召回

---

## 阶段 6：微调数据集与 LoRA / QLoRA

### 阶段目标

- 构建不少于 500 条高保真微调数据
- 用自动校验过滤脏数据
- 跑通微调并监控过拟合

### 开始前条件

- 评测集和 bad case 已经足够稳定
- 已经知道 Hard 样本的主要失败模式

### 具体动作

#### 6.1 候选数据生成

1. 用 LLM 辅助生成候选 QA。
2. 标注候选数据来源文件和类别。

#### 6.2 数据清洗

1. 使用 `ast` / `jedi` 做自动校验。
2. 剔除无法在真实源码中连通的伪链路。
3. 确保 Hard 样本比例不低于 30%。

#### 6.3 微调训练

1. 确定基座模型。
2. 配置 LoRA / QLoRA 参数。
3. 划分训练集和验证集。
4. 记录 `train_loss` 与 `val_loss`。
5. 触发 Early Stopping，防止死记源码。

### 本阶段产出

- `data/finetune_dataset.jsonl`
- 微调实验日志
- 训练曲线和关键超参记录

### 完成标准

- 数据量满足要求且校验通过
- 有验证集监控结果
- Fine-tune only 可以纳入消融矩阵

### 风险与处理

- 风险：数据量够了，但大部分是简单样本
- 处理：保留 Hard 样本配额，单独监控

- 风险：模型只是背会 Celery 特定代码
- 处理：用验证集和早停控制过拟合

---

## 阶段 7：完整消融实验与最终答辩材料

### 阶段目标

- 跑全实验矩阵
- 找出最优策略和适用边界
- 输出可展示、可复现、可答辩的最终材料

### 开始前条件

- PE、RAG、Fine-tune 都已经具备独立结果
- 评测集版本固定

### 具体动作

1. 统一实验矩阵：
   - Baseline
   - PE only
   - RAG only
   - Fine-tune only
   - PE + RAG
   - PE + Fine-tune
   - All
2. 统一指标口径：
   - Easy F1
   - Medium F1
   - Hard F1
   - Avg F1
   - Recall@5
   - MRR
   - Token Cost
3. 统一实验日志命名和图表样式。
4. 归纳不同策略在哪类问题上最有效。
5. 给出最终落地建议和边界条件。

### 本阶段产出

- `reports/ablation_study.md`
- 最终 README
- 图表素材
- 答辩主讲提纲

### 完成标准

- 七组实验全部齐备
- 可以明确回答“最优方案是什么”“为什么不是别的方案”
- 可以明确回答“在什么条件下只用 PE+RAG 就够了，什么条件下必须加微调”

### 风险与处理

- 风险：实验很多，但变量不干净，结论不可信
- 处理：所有实验都要基于统一评测集和记录模板

- 风险：报告只罗列结果，不提边界
- 处理：必须单独写“适用条件”和“失败边界”

---

## 推荐里程碑顺序

1. 阶段 0-1 先彻底做完，冻结口径和源码版本。
2. 阶段 2 先出 12 条，再扩到 50 条。
3. 阶段 3 先拿 baseline 和 bad case。
4. 阶段 4-6 再分别做 PE、RAG、Fine-tune。
5. 阶段 7 最后统一收口，形成答辩材料。

## 当前建议的下一步

当前最该做的是把阶段 2 和阶段 4 的“门禁工作”做实：

1. 收到 reviewer 对 Round 1 eval / few-shot 草稿的逐条结论。
2. 根据 `schema_migration_round2.md` 生成旧 12 条样本的新 schema draft。
3. 只把 reviewer 通过的条目并入正式评测集，先做成 24 条稳定版本。
4. 回填通过审核的 few-shot 到正式文档。
5. 等评测集与 few-shot 口径都稳定后，再启动 baseline 评测。
