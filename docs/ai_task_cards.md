# AI Task Cards

## 文档目标

本文件把高频任务写成标准任务卡，方便直接交给 AI。任务卡会明确：

- 任务意图
- 输入材料
- 应该读哪些文件
- 产出格式
- 验收标准
- 不该做什么

## 卡片格式

每张任务卡都按下面结构描述：

- `任务 ID`
- `任务名称`
- `适合谁做`
- `前置依赖`
- `必须输入`
- `建议读取`
- `必须产出`
- `完成标准`
- `常见错误`

---

## CARD-EVAL-002

- 任务 ID：`EVAL-002`
- 任务名称：标注 Easy 样本第 1 批
- 适合谁做：AI 起草
- 前置依赖：`EVAL-001`
- 必须输入：
  - [first_batch_candidates.md](first_batch_candidates.md)
  - [eval_case_annotation_template.md](eval_case_annotation_template.md)
  - [dataset_schema.md](dataset_schema.md)
- 建议读取：
  - `external/celery/celery/__init__.py`
  - `external/celery/celery/loaders/__init__.py`
  - `external/celery/celery/concurrency/__init__.py`
- 必须产出：
  - 4 条 Easy 样本草稿
  - 每条样本包含问题、入口、答案、证据链、难度、类别
- 完成标准：
  - 每条样本只有一个清晰问题
  - `gold_fqns` 是最终目标而不是中间跳板
  - 证据链能回到源码
- 常见错误：
  - 把顶层导出错当成最终实现
  - 把“可推测”写成“已证实”

## CARD-EVAL-004

- 任务 ID：`EVAL-004`
- 任务名称：标注 Hard 样本第 1 批
- 适合谁做：AI 起草，但必须人工复核
- 前置依赖：`EVAL-001`
- 必须输入：
  - [first_batch_candidates.md](first_batch_candidates.md)
  - [eval_case_annotation_template.md](eval_case_annotation_template.md)
- 建议读取：
  - `external/celery/celery/app/__init__.py`
  - `external/celery/celery/app/base.py`
  - `external/celery/celery/app/builtins.py`
  - `external/celery/celery/worker/strategy.py`
- 必须产出：
  - 4 条 Hard 样本草稿
  - 每条样本附完整证据链
  - 每条样本说明为什么是 `hard`
- 完成标准：
  - 证据链至少包含 3 个步骤
  - 明确指出隐式依赖发生在什么位置
  - 不得跳步得出结论
- 常见错误：
  - 只看装饰器表面，不追踪真实注册点
  - 遇到动态解析直接猜答案

## CARD-EVAL-009

- 任务 ID：`EVAL-009`
- 任务名称：统一样本格式并写入正式评测集
- 适合谁做：AI
- 前置依赖：`EVAL-006`、`EVAL-007`、`EVAL-008`
- 必须输入：
  - [dataset_schema.md](dataset_schema.md)
  - 已完成复核的样本草稿
- 建议读取：
  - 当前 `data/eval_cases.json`
- 必须产出：
  - 结构一致的正式 `eval_cases.json`
  - 难度分布统计
- 完成标准：
  - 字段完整
  - 命名统一
  - 没有重复 ID
  - easy / medium / hard 比例正确
- 常见错误：
  - 同一条样本的 `category` 和证据链不匹配
  - 出现大小写不一致的难度标签

## CARD-BASE-006

- 任务 ID：`BASE-006`
- 任务名称：将 bad case 归类到 Type A-E
- 适合谁做：AI 起草 + 人工复核
- 前置依赖：`BASE-005`
- 必须输入：
  - [plan.md](../plan.md)
  - bad case 清单
- 建议读取：
  - [reports/bottleneck_diagnosis.md](../reports/bottleneck_diagnosis.md)
- 必须产出：
  - 每条 bad case 的失效类型归类
  - 歧义样本列表
- 完成标准：
  - 每条样本归类理由明确
  - 不把多个错误原因压成一个标签
- 常见错误：
  - 看到动态加载就全部归到 Type E
  - 不区分“再导出链断裂”和“命名空间混淆”

## CARD-PE-003

- 任务 ID：`PE-003`
- 任务名称：从 bad case 反推 few-shot 类型配比
- 适合谁做：AI
- 前置依赖：`BASE-006`
- 必须输入：
  - bad case 分类结果
  - [plan.md](../plan.md)
- 建议读取：
  - [reports/bottleneck_diagnosis.md](../reports/bottleneck_diagnosis.md)
- 必须产出：
  - few-shot 类型配比建议
  - 每一类应覆盖的问题清单
- 完成标准：
  - 配比与 bad case 分布一致
  - Hard 类型样本被优先覆盖
- 常见错误：
  - few-shot 只偏向 easy case
  - 只给抽象建议，不给具体类别

## CARD-RAG-006

- 任务 ID：`RAG-006`
- 任务名称：制定检索评测方案
- 适合谁做：AI
- 前置依赖：`RAG-005`
- 必须输入：
  - [dataset_schema.md](dataset_schema.md)
  - RAG 方案草稿
- 建议读取：
  - [detailed_stage_playbook.md](detailed_stage_playbook.md)
- 必须产出：
  - Recall@5 评测口径
  - MRR 评测口径
  - 每条样本如何构造 gold retrieval target
- 完成标准：
  - 指标定义清晰
  - 可以直接用于实验日志
- 常见错误：
  - 检索 gold 和最终回答 gold 混为一谈

## CARD-FT-003

- 任务 ID：`FT-003`
- 任务名称：设计微调数据自动校验规则
- 适合谁做：AI
- 前置依赖：`FT-001`
- 必须输入：
  - [dataset_schema.md](dataset_schema.md)
  - [plan.md](../plan.md)
- 建议读取：
  - [detailed_stage_playbook.md](detailed_stage_playbook.md)
- 必须产出：
  - 校验维度清单
  - 通过 / 不通过规则
  - 需要人工抽检的边界样本类型
- 完成标准：
  - 至少覆盖字段完整性、FQN 格式、路径可连通性、Hard 样本比例
- 常见错误：
  - 只校验 JSON 格式，不校验事实正确性

## CARD-ABL-008

- 任务 ID：`ABL-008`
- 任务名称：提炼最优策略和边界条件
- 适合谁做：AI 起草 + 人工确认
- 前置依赖：`ABL-007`
- 必须输入：
  - 所有实验结果
  - [plan.md](../plan.md)
- 建议读取：
  - [reports/ablation_study.md](../reports/ablation_study.md)
- 必须产出：
  - 最优方案结论
  - 适用条件
  - 不适用条件
  - ROI 视角总结
- 完成标准：
  - 结论有数据支撑
  - 不只说“最好”，还说明“为什么”
- 常见错误：
  - 只说总分最高，不说代价
  - 不区分低深度关联和高隐式关联

---

## 任务卡扩展规则

- 如果一个 task 重复出现三次以上，就应该补成新的任务卡。
- 人工复核频率高的 task 优先补卡，因为最容易出错。
