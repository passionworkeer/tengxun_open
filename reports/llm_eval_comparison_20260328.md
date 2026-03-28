# GPT / GLM 正式评测对比报告

## 总览

- GPT 请求模型：`gpt-5.4`
- GPT 响应模型：`N/A`
- GLM 请求模型：`glm-5`
- GLM 响应模型：`glm-5`

| 模型 | 样本数 | 平均F1 | Pass Rate (F1>0) | F1=0 数量 |
|------|--------|--------|------------------|-----------|
| gpt-5.4 | 54 | 0.2815 | 55.6% | 24 |
| glm-5 | 54 | 0.0666 | 13.0% | 47 |

## 难度分层

### gpt-5.4

| Difficulty | Cases | Avg F1 |
|------------|-------|--------|
| easy | 15 | 0.4348 |
| medium | 19 | 0.2188 |
| hard | 20 | 0.2261 |

### glm-5

| Difficulty | Cases | Avg F1 |
|------------|-------|--------|
| easy | 15 | 0.1048 |
| medium | 19 | 0.0681 |
| hard | 20 | 0.0367 |

## 头对头

- GLM 更好：`5`
- GPT 更好：`27`
- 持平：`22`

## F1=0 失败类型分布

### gpt-5.4

| Failure Type | Count |
|--------------|-------|
| Type E | 8 |
| Type D | 5 |
| Type B | 5 |
| Type A | 4 |
| Type C | 2 |

### glm-5

| Failure Type | Count |
|--------------|-------|
| Type E | 11 |
| Type C | 10 |
| Type D | 10 |
| Type B | 9 |
| Type A | 7 |

## glm-5 相对 gpt-5.4 提升最大的 10 个 case

| Case | Difficulty | GPT F1 | GLM F1 | Delta |
|------|------------|--------|--------|-------|
| easy_001 | easy | 0.3333 | 1.0000 | +0.6667 |
| medium_002 | medium | 0.0000 | 0.5000 | +0.5000 |
| hard_004 | hard | 0.0000 | 0.3333 | +0.3333 |
| celery_easy_020 | easy | 0.2500 | 0.5714 | +0.3214 |
| celery_medium_019 | medium | 0.4444 | 0.5714 | +0.1270 |
| celery_easy_021 | easy | 0.0000 | 0.0000 | +0.0000 |
| celery_hard_014 | hard | 0.0000 | 0.0000 | +0.0000 |
| celery_hard_018 | hard | 0.0000 | 0.0000 | +0.0000 |
| celery_hard_024 | hard | 0.0000 | 0.0000 | +0.0000 |
| celery_medium_020 | medium | 0.0000 | 0.0000 | +0.0000 |

## gpt-5.4 相对 glm-5 提升最大的 10 个 case

| Case | Difficulty | GPT F1 | GLM F1 | Delta |
|------|------------|--------|--------|-------|
| celery_easy_023 | easy | 1.0000 | 0.0000 | -1.0000 |
| celery_type_d_001 | hard | 1.0000 | 0.0000 | -1.0000 |
| easy_002 | easy | 1.0000 | 0.0000 | -1.0000 |
| medium_004 | medium | 1.0000 | 0.0000 | -1.0000 |
| celery_medium_017 | medium | 0.7500 | 0.0000 | -0.7500 |
| celery_type_d_002 | hard | 0.7273 | 0.0000 | -0.7273 |
| celery_easy_018 | easy | 0.6667 | 0.0000 | -0.6667 |
| celery_hard_121 | hard | 0.6154 | 0.0000 | -0.6154 |
| easy_005 | easy | 0.5714 | 0.0000 | -0.5714 |
| celery_hard_013 | hard | 0.5556 | 0.0000 | -0.5556 |
