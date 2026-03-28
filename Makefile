PYTHON ?= uv run python
REPORT_PYTHON ?= uv run --with matplotlib python
EVAL_CASES ?= data/eval_cases.json
RAG_DRAFT_CASES ?= data/eval_cases_migrated_draft_round4.json
FINETUNE_DATA ?= data/finetune_dataset_500.jsonl
FEWSHOT_DATA ?= data/fewshot_examples_20.json
CONFIG_DIR ?= configs
RAG_REPORT_DIR ?= artifacts/rag

.PHONY: help eval-baseline eval-pe eval-rag eval-rag-draft eval-ft eval-all train report report-final lint-data

help:
	@echo "Available targets:"
	@echo "  make eval-baseline  - summarize the current eval dataset"
	@echo "  make eval-pe        - preview PE prompt metadata with v2 few-shot assets"
	@echo "  make eval-rag       - run retrieval metrics on the formal eval dataset"
	@echo "  make eval-rag-draft - run retrieval metrics on the 32-case round4 draft and write a JSON report"
	@echo "  make eval-ft        - placeholder for checkpoint evaluation wiring"
	@echo "  make eval-all       - run summary + retrieval + prompt preview metadata"
	@echo "  make train          - validate the LoRA scaffold config, then fail until trainer wiring exists"
	@echo "  make report         - generate final charts + metrics snapshot"
	@echo "  make report-final   - alias of make report"
	@echo "  make lint-data      - validate finetune dataset with data_guard.py"

eval-baseline:
	$(PYTHON) -m evaluation.baseline --mode baseline --eval-cases $(EVAL_CASES)

eval-pe:
	$(PYTHON) -m evaluation.baseline --mode pe --prompt-version v2 --eval-cases $(EVAL_CASES)

eval-rag:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(EVAL_CASES)

eval-rag-draft:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(RAG_DRAFT_CASES) --query-mode question_only --report-path $(RAG_REPORT_DIR)/rag_eval_round4_question_only.json

eval-ft:
	@echo "eval-ft is not wired yet; produce a checkpoint first and add a dedicated evaluation entrypoint."

eval-all:
	$(PYTHON) -m evaluation.baseline --mode all --prompt-version v2 --eval-cases $(EVAL_CASES)

train:
	$(PYTHON) finetune/train_lora.py --config $(CONFIG_DIR)/lora_9b.toml

report:
	$(PYTHON) scripts/generate_project_progress_report.py
	$(REPORT_PYTHON) scripts/generate_final_delivery_assets.py

report-final: report

lint-data:
	$(PYTHON) -m finetune.data_guard $(FINETUNE_DATA)

report-status:
	@echo "Reports:"
	@echo "  - reports/DELIVERY_REPORT.md"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/rag_pipeline.md"
	@echo "  - reports/ablation_study.md"
