"""
LoRA/QLoRA 微调模块。

本模块为代码依赖分析任务提供微调数据准备、验证和训练支持，
适用于 Celery 等 Python 项目的 FQN（完全限定名）依赖预测场景。

主要导出：

    ValidationSummary  -- 数据集验证结果摘要
    validate_record     -- 验证单条微调记录
    validate_jsonl      -- 验证 JSONL 格式的微调数据集
    validate_fqn        -- 验证 FQN 路径是否真实存在
    weighted_sampling   -- 按难度加权采样，支持 Hard 样本过采样

微调数据来源与用途：

    数据来源为 ``data/finetune_dataset_*.jsonl``，每条记录包含：

        - instruction / input / output    -- 问答格式的训练样本
        - difficulty                      -- easy / medium / hard 三档难度
        - ground_truth                    -- direct_deps / indirect_deps / implicit_deps
        - verified / verify_method         -- 标注质量标记

    用途是让模型学习真实代码库中的模块级依赖关系，
    从而在给定调用栈时准确推断出直接依赖、间接依赖和隐式依赖。
    data_guard 模块在数据进入训练流程前执行格式校验、FQN 路径存在性检查
    以及与评测集的重叠审计，确保模型学到的依赖关系真实可复现。
"""

