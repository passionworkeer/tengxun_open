# 严格数据污染审计（2026-03-29）

## 结论

- few-shot 与 eval 的 exact GT overlap：`2`
- finetune 与 eval 的 exact GT overlap row-case pair 数：`26`
- finetune 与 eval 的 exact GT overlap row 数：`19`
- finetune 与 eval 的 exact GT overlap case 数：`14`
- official few-shot normalized exact question overlap：`0`
- official finetune normalized exact question overlap：`4`
- official few-shot hard question overlap (exact or >= 0.90)：`0`
- official finetune hard question overlap (exact or >= 0.90)：`7`
- 已生成 strict few-shot：`data/fewshot_examples_20_strict.json`
- 已生成 strict finetune：`data/finetune_dataset_500_strict.jsonl`
- strict few-shot 与 eval 的 exact GT overlap：`0`
- strict finetune 与 eval 的 exact GT overlap：`0`
- strict few-shot normalized exact question overlap：`0`
- strict finetune normalized exact question overlap：`0`
- strict few-shot hard question overlap (exact or >= 0.90)：`0`
- strict finetune hard question overlap (exact or >= 0.90)：`0`

## Exact Overlap

### Few-shot

- `C01` -> `easy_001`
- `E04` -> `celery_type_d_006`

### Finetune

- overlap row-case pair 数：`26`
- overlap row 数：`19`
- overlap case 数：`14`

## 近似问题重合（问题文本）

### Few-shot Top Candidates

- `C03` ~ `easy_007`: similarity=0.88, normalized_exact=False
- `E02` ~ `celery_medium_017`: similarity=0.7611, normalized_exact=False
- `B03` ~ `celery_hard_013`: similarity=0.7317, normalized_exact=False
- `B04` ~ `celery_hard_013`: similarity=0.7222, normalized_exact=False
- `A02` ~ `easy_005`: similarity=0.642, normalized_exact=False
- `C05` ~ `celery_easy_023`: similarity=0.6389, normalized_exact=False
- `C02` ~ `easy_005`: similarity=0.6154, normalized_exact=False
- `C01` ~ `easy_007`: similarity=0.5833, normalized_exact=False

- official few-shot review queue (0.85~0.90): `1`

### Finetune Top Candidates

- `ft_030` ~ `celery_easy_022`: similarity=1.0, normalized_exact=True
- `ft_094` ~ `easy_007`: similarity=1.0, normalized_exact=True
- `ft_095` ~ `easy_008`: similarity=1.0, normalized_exact=True
- `ft_126` ~ `easy_007`: similarity=1.0, normalized_exact=True
- `ft_172` ~ `easy_007`: similarity=0.9565, normalized_exact=False
- `ft_185` ~ `easy_007`: similarity=0.9565, normalized_exact=False
- `ft_187` ~ `medium_008`: similarity=0.9091, normalized_exact=False
- `ft_099` ~ `easy_007`: similarity=0.88, normalized_exact=False

- official finetune review queue (0.85~0.90): `1`

## Strict 替换说明

- removed overlap few-shot ids: C01, E04
- removed hard question-overlap few-shot rows: 0
- added strict supplement few-shot rows: 2
- removed overlap finetune rows: 19
- removed hard question-overlap finetune rows: 5
- added strict supplement variants: 24

## Strict Finetune 分布

- `Type A`: `104`
- `Type B`: `116`
- `Type C`: `89`
- `Type D`: `94`
- `Type E`: `97`

## 说明

- strict few-shot 的目标是去除 eval exact overlap，不覆盖原始正式 few-shot 文件。
- strict finetune 先移除 exact overlap 和 hard question overlap，再补入不与 eval 重合的 manual strict variants，以维持 `500` 条。
- 当前 strict 构建规则：过滤 exact GT overlap、normalized exact question overlap、以及 similarity >= 0.90 的 hard overlap。
- similarity 介于 0.85 和 0.90 之间的样本只进入审计报告，不自动删除。
- 这些 strict 资产适合用来做复验和答辩防守，不应无提示地覆盖当前正式口径。

