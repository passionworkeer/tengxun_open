PYTHON ?= python
EVAL_CASES ?= data/eval_cases.json
FINETUNE_DATA ?= data/finetune_dataset.jsonl

.PHONY: help eval-baseline eval-all lint-data report-status

help:
	@echo "Available targets:"
	@echo "  make eval-baseline  - summarize eval dataset and baseline inputs"
	@echo "  make eval-all       - summarize full experiment inputs"
	@echo "  make lint-data      - validate finetune dataset schema"
	@echo "  make report-status  - print report placeholders"

eval-baseline:
	$(PYTHON) -m evaluation.baseline --eval-cases $(EVAL_CASES) --mode baseline

eval-all:
	$(PYTHON) -m evaluation.baseline --eval-cases $(EVAL_CASES) --mode all

lint-data:
	$(PYTHON) -m finetune.data_guard $(FINETUNE_DATA)

report-status:
	@echo "Reports:"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/ablation_study.md"

