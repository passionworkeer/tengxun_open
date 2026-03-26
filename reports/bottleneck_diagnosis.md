# Bottleneck Diagnosis

## 目标

- 基于真实 Celery 评测集分析 baseline 低分原因
- 用错误样本而不是主观描述来定义失效模式
- 绘制 5 类失效在 Easy/Medium/Hard 上的**分布热力图**

## 模型配置

| 角色 | 模型 | 用途 |
|------|------|------|
| 评测基线 A | `GPT-5.4`（API） | 国际顶尖商业模型，作为上界参照 |
| 评测基线 B | `GLM-5`（API） | 开源代码最强模型，国产自研 |
| 评测基线 C | `Qwen3.5-9B`（未微调） | 微调前的对照基座 |

## 待补数据

- 总评测样本数：50 条
- Easy / Medium / Hard 分布：15 / 20 / 15
- 各难度 F1（分三个 baseline）
- 典型 bad cases

## 分层指标表

| Model | Easy F1 | Medium F1 | Hard F1 | Avg F1 | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| GPT-5.4 | TBD | TBD | TBD | TBD | |
| GLM-5 | TBD | TBD | TBD | TBD | |
| Qwen3.5-9B | TBD | TBD | TBD | TBD | |

## 失效模式定义

### Type A: 长上下文截断丢失

- **现象**: 超出窗口导致上游定义节点被遗漏
- **典型案例**: `celery/app/base.py` 这类超长文件
- **证据样本**: （待补充）
- **对最终输出的影响**: （待补充）

### Type B: 隐式依赖断裂（幻觉）

- **现象**: `@app.task` 装饰器注册时 LLM 编造不存在的内部调用
- **典型案例**: `celery/app/__init__.py`、`celery/app/builtins.py`
- **证据样本**: （待补充）
- **对最终输出的影响**: （待补充）

### Type C: 再导出链断裂

- **现象**: 跨多层 `__init__.py` 别名转发，链路在中间节点中断
- **典型案例**: `celery/__init__.py`、`celery/app/__init__.py`
- **证据样本**: （待补充）
- **对最终输出的影响**: （待补充）

### Type D: 跨文件命名空间混淆

- **现象**: 同名函数/类导致 LLM 张冠李戴
- **典型案例**: 多个模块里同名类/函数、顶层导出与真实实现分离的场景
- **证据样本**: （待补充）
- **对最终输出的影响**: （待补充）

### Type E: 动态加载与字符串引用失配

- **现象**: `importlib`/配置字符串，LLM 无法把字符串入口映射回真实符号
- **典型案例**: `loaders/*`、`utils/imports.py`、`beat.py`、`bootsteps.py`
- **证据样本**: （待补充）
- **对最终输出的影响**: （待补充）

## 失效分布热力图

（待补充：使用 matplotlib 绘制 Type A-E × Easy/Medium/Hard 的热力图）

## Bad Case 清单

| Case ID | Difficulty | Failure Type | Baseline Answer | Gold Answer | Root Cause |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TBD | | | | | |

## Bad Case 专栏（必填 2-3 个典型案例）

### Bad Case 1: （待补充）

1. **原始问题**: （具体的依赖分析题目）
2. **Baseline 错误答案**: （模型给出了什么，含幻觉内容）
3. **失效归因**: 属于 Type A-E 中的哪一类，为什么会失败
4. **优化后答案**: （RAG / FT 如何纠正）
5. **纠正机理**: （为什么这个优化手段对这类失效有效）

### Bad Case 2: （待补充）

（同上格式）

### Bad Case 3: （待补充）

（同上格式）

## 结论

- 最主要的失效类型是：
- 对 Hard 样本影响最大的失效类型是：
- PE 最能解决的失效类型是：
- RAG 最能解决的失效类型是：
- FT 最能解决的失效类型是：
