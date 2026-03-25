PYTHON ?= python
EVAL_CASES ?= data/eval_cases_celery.json
FINETUNE_DATA ?= data/finetune_dataset_500.jsonl
FEWSHOT_DATA ?= data/fewshot_examples_20.json
CONFIG_DIR ?= configs

.PHONY: help eval-baseline eval-pe eval-rag eval-ft eval-all train report lint-data

help:
	@echo "Available targets:"
	@echo "  make eval-baseline  - run baseline evaluation (GPT-4o / GLM-5 / Qwen2.5-Coder-7B)"
	@echo "  make eval-pe        - run PE ablation (System → CoT → Few-shot → Post-processing)"
	@echo "  make eval-rag       - run RAG ablation (Vector → BM25 → Graph → RRF)"
	@echo "  make eval-ft        - run fine-tuned model evaluation"
	@echo "  make eval-all       - run full ablation matrix (10 experiments)"
	@echo "  make train          - train Qwen2.5-Coder-7B with QLoRA"
	@echo "  make report         - generate ablation report with charts"
	@echo "  make lint-data      - validate finetune dataset with data_guard.py"

eval-baseline:
	$(PYTHON) evaluation/baseline_eval.py --models gpt-4o glm-5 qwen2.5-coder-7b --eval-cases $(EVAL_CASES)

eval-pe:
	$(PYTHON) evaluation/baseline_eval.py --model gpt-4o --pe-ablation --eval-cases $(EVAL_CASES)

eval-rag:
	$(PYTHON) evaluation/baseline_eval.py --model gpt-4o --rag --rag-ablation --eval-cases $(EVAL_CASES)

eval-ft:
	$(PYTHON) evaluation/baseline_eval.py --model qwen2.5-coder-7b-ft --eval-cases $(EVAL_CASES)

eval-all:
	$(PYTHON) experiments/ablation_full_matrix.py --all --eval-cases $(EVAL_CASES)

train:
	$(PYTHON) finetune/train_qlora.py --config $(CONFIG_DIR)/qlora_7b.yaml

report:
	jupyter nbconvert --execute experiments/ablation_full_matrix.ipynb

lint-data:
	$(PYTHON) -m finetune.data_guard $(FINETUNE_DATA)

report-status:
	@echo "Reports:"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/ablation_study.md"
