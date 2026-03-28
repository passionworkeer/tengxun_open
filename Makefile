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
	@echo "可用目标："
	@echo "  make eval-baseline  - 输出正式评测集摘要"
	@echo "  make eval-pe        - 预览 PE 提示词元数据（v2 few-shot 方案）"
	@echo "  make eval-rag       - 运行正式评测集的检索指标"
	@echo "  make eval-rag-draft - 运行 32 条 draft 评测集的检索指标并写入 JSON 报告"
	@echo "  make eval-ft        - 预留给微调模型评测入口"
	@echo "  make eval-all       - 一次性输出摘要、检索结果与提示词元数据"
	@echo "  make train          - 校验 LoRA 训练配置并运行训练脚手架"
	@echo "  make report         - 生成最终图表与指标快照"
	@echo "  make report-final   - 等同于 make report"
	@echo "  make lint-data      - 用 data_guard.py 校验微调数据"

eval-baseline:
	$(PYTHON) -m evaluation.baseline --mode baseline --eval-cases $(EVAL_CASES)

eval-pe:
	$(PYTHON) -m evaluation.baseline --mode pe --prompt-version v2 --eval-cases $(EVAL_CASES)

eval-rag:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(EVAL_CASES)

eval-rag-draft:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(RAG_DRAFT_CASES) --query-mode question_only --report-path $(RAG_REPORT_DIR)/rag_eval_round4_question_only.json

eval-ft:
	@echo "eval-ft 当前还没有单独接线；请先产出 checkpoint，再补专门评测入口。"

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
	@echo "正式报告："
	@echo "  - reports/DELIVERY_REPORT.md"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/rag_pipeline.md"
	@echo "  - reports/ablation_study.md"
