# AI Prompt Templates

## 文档目标

本文件提供可直接发给 AI 的 prompt 模板，减少每次重新组织需求的成本。

使用原则：

- 一次只发一个 task
- 明确输入文档和允许修改的文件
- 明确输出格式
- 明确“不要做什么”

---

## 模板 1：样本标注任务

```text
你现在负责执行任务：<TASK_ID>。

任务目标：
<一句话目标>

请先阅读这些文档：
- docs/dataset_schema.md
- docs/eval_case_annotation_template.md
- docs/first_batch_candidates.md
- docs/celery_case_mining.md

请重点查看这些源码文件：
- <file 1>
- <file 2>
- <file 3>

你的输出必须包含：
1. 样本草稿列表
2. 每条样本的 id / difficulty / category / question / entry_file / entry_symbol / gold_fqns
3. 每条样本的证据链
4. 你认为需要人工复核的风险点

要求：
- 不要编造源码中不存在的符号
- 一条样本只问一个问题
- 如果证据不足，明确说不确定，不要猜
- 先给出草稿，不要直接修改正式评测集
```

## 模板 2：错误归类任务

```text
你现在负责执行任务：<TASK_ID>。

请基于已有 baseline 错误样本，把 bad case 归类到 Type A-E。

请先阅读：
- plan.md
- reports/bottleneck_diagnosis.md
- docs/detailed_stage_playbook.md

输入材料：
- <bad case 清单路径或内容>

你的输出必须包含：
1. 每条 bad case 的归类结果
2. 归类理由
3. 归类不确定的样本列表
4. 统计汇总表

要求：
- 不要只给标签，要给理由
- 不确定时允许多候选，但要说明为什么
- 不要修改其他实验结论
```

## 模板 3：few-shot 设计任务

```text
你现在负责执行任务：<TASK_ID>。

目标是根据 bad case 分布，设计 few-shot 示例库的覆盖方案。

请先阅读：
- plan.md
- reports/bottleneck_diagnosis.md
- docs/ai_task_breakdown.md

你的输出必须包含：
1. 推荐的 few-shot 类型分布
2. 每类建议的样本数量
3. 每类要覆盖的典型问题
4. 哪些 bad case 会被这些 few-shot 针对

要求：
- 重点覆盖 hard case
- 不要只给抽象原则，要落到具体类型
```

## 模板 4：RAG 方案设计任务

```text
你现在负责执行任务：<TASK_ID>。

目标是为跨文件依赖分析设计 RAG 检索方案。

请先阅读：
- plan.md
- docs/detailed_stage_playbook.md
- docs/dataset_schema.md

你的输出必须包含：
1. chunking 方案
2. 向量检索方案
3. BM25 方案
4. 图结构召回方案
5. RRF 融合与窗口管理策略
6. 独立检索评测方案

要求：
- 明确每一部分解决什么问题
- 明确为什么单靠向量检索不够
- 不要直接跳到“最终效果会更好”的结论
```

## 模板 5：微调数据清洗规则任务

```text
你现在负责执行任务：<TASK_ID>。

目标是设计微调数据集的自动校验规则，防止伪链路和脏数据进入训练集。

请先阅读：
- plan.md
- docs/dataset_schema.md
- docs/detailed_stage_playbook.md

你的输出必须包含：
1. 校验维度清单
2. 每个维度的通过规则
3. 必须人工抽检的样本类型
4. Hard 样本比例控制建议

要求：
- 不要只检查字段格式
- 必须覆盖“路径真实连通性”
- 要说明哪些情况容易出现幻觉数据
```

## 模板 6：消融结论提炼任务

```text
你现在负责执行任务：<TASK_ID>。

目标是根据完整实验结果，提炼最优策略、适用边界和 ROI 结论。

请先阅读：
- plan.md
- reports/ablation_study.md
- docs/detailed_stage_playbook.md

你的输出必须包含：
1. 最优策略
2. 最优策略为什么成立
3. 在什么条件下 PE + RAG 已经够用
4. 在什么条件下必须加 Fine-tune
5. 风险和代价

要求：
- 所有结论都要有数据支撑
- 不要只报总分最高项
- 要写边界，不要只写优势
```
