# Round 19 Strict Review: Finetune Alignment And Round4 Integration

## Scope

This narrowed review only covers the 5 highest-risk files:

- `E:\desktop\tengxun\finetune\data_guard.py`
- `E:\desktop\tengxun\finetune\train_qlora.py`
- `E:\desktop\tengxun\Makefile`
- `E:\desktop\tengxun\data\eval_cases_migrated_draft_round4.json`
- `E:\desktop\tengxun\docs\remaining_work_checklist.md`

Review rule for this pass:

- Prefer real integration risk over style comments.
- Treat "placeholder that exits 0" as a real defect if surrounding workflow can misread it as ready.
- For eval draft, prioritize single-question single-target, runtime stability, and closure discipline.

## Executive Conclusion

Verdict on the current 5-file slice: `hold`

The repo is not blocked by syntax. It is blocked by false-readiness risk:

- `data_guard.py` is not a real gate yet because it passes an empty dataset.
- `train_qlora.py` is still a stub but returns success.
- `eval_cases_migrated_draft_round4.json` is valid JSON but still contains formal-pool-unsafe items.
- `Makefile` and `remaining_work_checklist.md` are less broken by themselves, but both can amplify the two risks above if read optimistically.

## File-By-File Findings

### 1. `E:\desktop\tengxun\finetune\data_guard.py`

Verdict: `hold`

Reasons:

- The validator only checks record shape. It does not enforce dataset-level readiness constraints.
- `validate_jsonl()` computes `hard_ratio` but never gates on it. See `finetune/data_guard.py:133-170`.
- `main()` returns success whenever `invalid_records == 0` at `finetune/data_guard.py:181`.
- That means an empty dataset passes. This is already happening with the current placeholder `data/finetune_dataset_500.jsonl`, which yields `valid_records=0`, `invalid_records=0`, `hard_ratio=0.0`.
- A gate that passes zero records is not a usable production gate.
- Validation is purely structural: regex FQN check plus JSON extraction. There is no semantic verification of whether the dependencies are real, linked, or correct for the prompt.
- `VALID_FAILURE_TYPES` includes `Type A` at `finetune/data_guard.py:16`. If downstream docs or generators still assume a narrower enum, this creates silent contract drift.

Required fix:

- Fail on empty dataset.
- Add at least `min_records` and `min_hard_ratio` enforcement.
- Make the accepted `failure_type` enum explicit and consistent with the docs used by data generation.
- Do not describe this file as a strong anti-hallucination gate until semantic checks exist.

### 2. `E:\desktop\tengxun\finetune\train_qlora.py`

Verdict: `reject`

Reasons:

- This file does not train anything. `main()` only loads config, checks dataset path existence, creates output dir, prints config, prints a TODO, and exits `0`. See `finetune/train_qlora.py:134-145`.
- `TrainingConfig` exposes operational parameters such as `validation_split`, `early_stopping_patience`, `eval_steps`, and `metric_for_best_model`, but none of them are consumed by any trainer code.
- This creates a high-risk false-positive path: `make train` can look successful even though no model training, evaluation, checkpointing, or early stopping occurred.
- As long as this file returns success, any downstream automation or teammate can misclassify the finetune lane as runnable.

Required fix:

- Either implement a real trainer path, or explicitly fail after printing scaffold information.
- Until then, all docs and workflow surfaces must call this a scaffold, not a training pipeline.

### 3. `E:\desktop\tengxun\Makefile`

Verdict: `accept_with_fix`

Reasons:

- `train` correctly points to `finetune/train_qlora.py --config configs/qlora_7b.toml`.
- `lint-data` correctly points to `python -m finetune.data_guard data/finetune_dataset_500.jsonl`.
- `eval-ft` is honestly marked placeholder at `Makefile:29-30`.
- The problem is not the command wiring itself. The problem is that the wiring currently fronts weak or stubbed implementations, so the Make targets can appear more meaningful than they are.
- In particular, `make lint-data` can go green on an empty dataset because `data_guard.py` accepts zero valid rows, and `make train` can go green on a non-training stub.

Required fix:

- Keep the targets, but label `train` and `lint-data` as scaffold-level commands until the underlying gate and trainer are real.
- Do not let CI or project status treat these two targets as proof of finetune readiness.

### 4. `E:\desktop\tengxun\data\eval_cases_migrated_draft_round4.json`

Verdict: `hold`

Reasons:

- Positive first: the file is valid JSON, contains `32` items, has no duplicate IDs, and all dependency strings are syntactically valid dotted FQNs.
- That is necessary but not sufficient. Several items still violate strict formal-pool rules.
- `medium_006` has two `direct_deps`: `celery.app.base.Celery._get_backend` and `celery.backends.rpc.RPCBackend`. This mixes trigger site and final resolved class. Under single-target judgment, that is over-closed.
- `celery_hard_013` has two `direct_deps`: `celery.app.base.Celery.tasks` and `celery.app.base.Celery.finalize`. The question asks for the singular "关键入口符号". The answer set still refuses to commit.
- `celery_medium_020` has two `direct_deps`: `celery.app.base.Celery.loader` and `celery.loaders.default.Loader`. Same structural defect.
- `celery_hard_015` is still a dual-ask question: "目标函数是什么，以及它由哪条调用链触发". That is not single-question single-judgment.
- `celery_hard_018` remains runtime-conditional. Its own note says it should not be integrated as an unconditional eval item if Django fixup preconditions do not hold.
- `celery_hard_018` also uses `os.environ.get` as an `implicit_dep`. That is FQN-shaped but semantically unstable as a dependency label. Environment predicates usually belong in sample constraints, not in closure labels.

Required fix:

- For `medium_006`, `celery_hard_013`, and `celery_medium_020`, choose one direct answer and demote or drop the rest.
- Rewrite `celery_hard_015` into a single-target question.
- Keep `celery_hard_018` out of unconditional formal integration unless its runtime assumptions are made part of the sample contract and the closure is tightened.
- Keep this file in draft status; do not promote it to formal eval pool yet.

### 5. `E:\desktop\tengxun\docs\remaining_work_checklist.md`

Verdict: `accept_with_fix`

Reasons:

- This file is closer to reality than the more optimistic top-level docs. It already records that `data/finetune_dataset_500.jsonl` is currently `0` valid records and that the formal eval pool is still on hold.
- The remaining issue is omission, not fabrication: it says `finetune/train_qlora.py` "已支持 --config", but does not say that the file is still only a scaffold and performs no training.
- It also says `finetune/data_guard.py` is aligned to schema, but does not warn that the guard still passes an empty dataset and does not enforce dataset-level thresholds.
- Because this checklist is likely to be read as ground-truth project status, those omissions matter.

Required fix:

- Add one explicit line that `train_qlora.py` is scaffold-only and not yet a runnable training backend.
- Add one explicit line that `data_guard.py` currently validates record shape, not full semantic correctness or dataset readiness.

## Integration Judgment

Can move forward now:

- `Makefile`, after wording fixes.
- `docs/remaining_work_checklist.md`, after wording fixes.

Cannot be treated as ready:

- `finetune/data_guard.py` as a release gate.
- `finetune/train_qlora.py` as a training pipeline.
- `data/eval_cases_migrated_draft_round4.json` as a formal eval file.

## Top 3 Risks

1. False green on finetune data quality: the current guard accepts an empty dataset.
2. False green on finetune execution: the current trainer stub exits successfully without training.
3. False promotion on round4 eval: the 32-item draft is structurally cleaner, but still contains multi-target and runtime-conditional samples that are unsafe for formal integration.
