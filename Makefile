PYTHON ?= uv run python
EVAL_CASES ?= data/eval_cases.json
FINETUNE_DATA ?= data/finetune_dataset_500.jsonl
FEWSHOT_DATA ?= data/fewshot_examples_20.json
CONFIG_DIR ?= configs

.PHONY: help eval-baseline eval-pe eval-rag eval-ft eval-all train report lint-data

help:
	@echo "Available targets:"
	@echo "  make eval-baseline  - summarize the current eval dataset"
	@echo "  make eval-pe        - preview PE prompt metadata with v2 few-shot assets"
	@echo "  make eval-rag       - run retrieval metrics on the current eval dataset"
	@echo "  make eval-ft        - placeholder for checkpoint evaluation wiring"
	@echo "  make eval-all       - run summary + retrieval + prompt preview metadata"
	@echo "  make train          - validate the QLoRA scaffold config, then fail until trainer wiring exists"
	@echo "  make report         - generate ablation report with charts"
	@echo "  make lint-data      - validate finetune dataset with data_guard.py"

eval-baseline:
	$(PYTHON) -m evaluation.baseline --mode baseline --eval-cases $(EVAL_CASES)

eval-pe:
	$(PYTHON) -m evaluation.baseline --mode pe --prompt-version v2 --eval-cases $(EVAL_CASES)

eval-rag:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(EVAL_CASES)

eval-ft:
	@echo "eval-ft is not wired yet; produce a checkpoint first and add a dedicated evaluation entrypoint."

eval-all:
	$(PYTHON) -m evaluation.baseline --mode all --prompt-version v2 --eval-cases $(EVAL_CASES)

train:
	$(PYTHON) finetune/train_qlora.py --config $(CONFIG_DIR)/qlora_7b.toml

report:
	jupyter nbconvert --execute experiments/ablation_full_matrix.ipynb

lint-data:
	$(PYTHON) -m finetune.data_guard $(FINETUNE_DATA)

report-status:
	@echo "Reports:"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/ablation_study.md"
