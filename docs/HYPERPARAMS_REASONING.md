# Qwen3.5-9B LoRA 微调配置说明

## 整体说明

本文档详细解释 LoRA 微调的超参数配置及选型原因，帮助理解每个参数的作用和调整依据。

---

## 一、模型配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `model_name_or_path` | Qwen/Qwen3.5-9B | HuggingFace模型名或本地路径 |
| `trust_remote_code` | true | 允许执行模型的远程代码（如Qwen的chat模板）|

**选型原因**：
- Qwen3.5-9B 是9B参数版本的指令微调模型
- 在40GB显存的A100上可以运行 bf16精度 + LoRA微调
- 推理效果比3B等小模型好，适合作为基座模型

---

## 二、LoRA 微调配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `lora_target` | all | 对所有linear层应用LoRA，包括attention和ffn层 |
| `lora_rank` | 8 | LoRA秩，控制可训练参数量 |
| `lora_alpha` | 16 | LoRA缩放因子，通常设为rank的2倍 |
| `lora_dropout` | 0.05 | Dropout率，防止过拟合 |
| `additional_target` | [embed_tokens, lm_head] | 额外微调embedding和输出层 |

**选型原因详解**：

1. **lora_rank=8**：
   - 较小秩可以减少训练参数，降低过拟合风险
   - 适合500条中小规模数据集
   - 过大容易过拟合到特定代码模式

2. **lora_alpha=16**：
   - alpha=2*rank是社区常见设置
   - 控制LoRA支路的缩放权重

3. **lora_dropout=0.05**：
   - 轻微dropout可以防止过拟合
   - 不宜过大（>0.1），否则影响学习效果

4. **target=all**：
   - Qwen的attention层(q_proj/k_proj/v_proj/o_proj)是最重要的
   - 对所有linear层微调可以让模型学习更完整的依赖模式

5. **embedding微调**：
   - 增加 `embed_tokens` 和 `lm_head` 可以提升语言表达能力
   - 但会额外增加显存需求，需权衡

---

## 三、数据集配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `dataset` | fintune_qwen_dep | 数据集名称（需在dataset_info.json中注册）|
| `template` | qwen | 使用Qwen的对话模板 |
| `cutoff_len` | 1024 | 最大序列长度 |
| `max_samples` | 10000 | 最大采样数量 |

**选型原因**：
- **cutoff_len=1024**：依赖链分析任务输入较短，1024足够处理大多数案例
- **数据量**：500条高质量数据，来源主要是 celery/kombu 跨包依赖分析
- **任务类型**：目的是让模型学习分析代码依赖链，属于推理类任务

---

## 四、训练配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `per_device_train_batch_size` | 1 | 每个GPU的batch大小 |
| `gradient_accumulation_steps` | 8 | 梯度累积步数 |
| `learning_rate` | 5e-5 | 学习率 |
| `num_train_epochs` | 3.0 | 训练轮数 |
| `lr_scheduler_type` | cosine | 学习率调度策略 |
| `warmup_ratio` | 0.1 | 预热比例 |
| `bf16` | true | bfloat16精度 |

**选型原因详解**：

1. **learning_rate=5e-5**：
   - LoRA微调的常用学习率
   - 比全参数训练的学习率略高（全参数通常1e-5）
   - 需要配合 warmup 使用

2. **batch=1 + accum=8**：
   - 有效batch=8，在保证训练效果的同时节省显存
   - A100-40GB 可以轻松hold住

3. **epoch=3**：
   - 数据集较小（500条），需要多轮训练才能充分学习
   - 配合验证集做early stopping防止过拟合

4. **cosine调度**：
   - 余弦退火可以平滑学习率曲线，利于收敛到最优解

5. **warmup_ratio=10%**：
   - 前10%步数用于学习率预热
   - 稳定训练初期，避免梯度爆炸

6. **bf16=true**：
   - A100支持bfloat16精度
   - 比fp16更稳定，训练更快，显存利用率更高

---

## 五、评估配置

| 参数 | 值 | 说明 |
|------|-----|------|
| `val_size` | 0.1 | 验证集比例（10%）|
| `eval_strategy` | steps | 按步数评估 |
| `eval_steps` | 500 | 每500步评估一次 |

**选型原因**：
- **验证集10%**：用于监控训练过程中的过拟合
- **eval_steps=500**：配合save_steps，可以在早期停训

---

## 六、数据集统计

| 项目 | 数值 |
|------|------|
| 训练集 | 450条 (90%) |
| 验证集 | 50条 (10%) |
| 数据来源 | celery/kombu 跨包依赖分析 |
| 任务类型 | 代码依赖链推理 |

**难度分布**：
- Hard: 162条 (32.4%)
- Easy: 163条 (32.6%)
- Medium: 175条 (35.0%)

---

## 七、训练输出目录

```
saves/qwen3.5-9b/lora/finetune_dep/
├── adapters/           # LoRA adapter权重文件
├── training_log.json   # 训练日志（JSON格式）
└── runs/               # TensorBoard日志目录
```

---

## 八、预期训练时间

| GPU | 预计时间 | 说明 |
|-----|----------|------|
| A100-40GB | 30-60分钟 | 3 epoch, 500条数据 |

**瓶颈分析**：
- 主要瓶颈：GPU计算 + 数据加载IO
- 显存瓶颈：模型权重 + LoRA权重 + 梯度

---

## 九、显存需求估算

| 项目 | 显存需求 |
|------|----------|
| 模型权重(bf16) | ~18GB |
| LoRA权重 | ~1GB |
| 梯度(accum=8) | ~4GB |
| 中间激活值 | ~8GB |
| **总计** | **~31GB** |

A100-40GB 完全够用，还有约9GB余量。

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