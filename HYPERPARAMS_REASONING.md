# Qwen3.5-9B LoRA 微调配置说明

## 超参数配置及选型原因

### 1. 模型配置
```yaml
model_name_or_path: Qwen/Qwen3.5-9B
trust_remote_code: true
```
- **模型**: Qwen/Qwen3.5-9B (指令微调版本)
- **选型原因**: 9B参数规模在40GB显存A100上可跑bf16+LoRA，推理效果比更小的模型好

### 2. LoRA 配置
```yaml
lora_target: all              # 对所有linear层应用LoRA
lora_rank: 8                  # LoRA秩
lora_alpha: 16                # LoRA缩放因子
lora_dropout: 0.05            # Dropout率
additional_target: [embed_tokens, lm_head]  # 也微调embedding
```
- **lora_rank=8**: 较小秩减少训练参数，降低过拟合风险，适合中小数据集
- **lora_alpha=16**: alpha=2*rank是常见设置
- **lora_dropout=0.05**: 轻微dropout防止过拟合
- **target=all**: Qwen的attention层(q/k/v/o)是最重要的，对所有linear层微调效果更好
- **embedding微调**: 增加 `embed_tokens` 和 `lm_head` 提升语言表达能力

### 3. 数据集配置
```yaml
dataset: fintune_qwen_dep     # 依赖链分析数据集
template: qwen                # Qwen对话模板
cutoff_len: 1024              # 最大序列长度
max_samples: 10000            # 最大采样数
```
- **cutoff_len=1024**: 依赖链分析任务输入较短，1024足够
- **数据量**: 500条高质量数据，来源主要是 celery/kombu 跨包依赖分析
- **任务类型**: 目的是让模型学习分析代码依赖链，属于推理类任务

### 4. 训练配置
```yaml
per_device_train_batch_size: 1      # 每设备batch
gradient_accumulation_steps: 8      # 梯度累积步数
learning_rate: 5.0e-5               # 学习率
num_train_epochs: 3.0               # 训练轮数
lr_scheduler_type: cosine           # 学习率调度
warmup_ratio: 0.1                   # 预热比例
bf16: true                          # bfloat16精度
```
- **lr=5e-5**: LoRA微调常用学习率，比全参数训练略高
- **batch=1 + accum=8**: 有效batch=8，省显存
- **epoch=3**: 数据集小，适当多轮训练
- **cosine调度**: 平滑学习率曲线，利于收敛
- **warmup=10%**: 稳定训练初期
- **bf16=true**: A100支持，对比fp16更稳定，训练更快

### 5. 评估配置
```yaml
val_size: 0.1                # 10%验证集
eval_strategy: steps         # 按步评估
eval_steps: 500              # 每500步评估
```
- **验证集10%**: 用于监控过拟合
- **eval_steps=500**: 配合save_steps，早停监控

---

## 数据集统计

- **训练集**: 450条 (90%)
- **验证集**: 50条 (10%)
- **数据来源**: celery/kombu 跨包依赖分析
- **任务类型**: 代码依赖链推理
- **难度分布**: 以hard为主，涵盖多种失败类型

---

## 训练输出目录

```
saves/qwen3.5-9b/lora/finetune_dep/
├── adapters/           # LoRA权重
├── training_log.json   # 训练日志
└── runs/               # TensorBoard日志
```

---

## 预期训练时间

- A100-40GB: 约 30-60分钟 (3 epoch, 500条数据)
- 瓶颈: GPU计算 + 数据加载