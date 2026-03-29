ifeq ($(shell command -v uv >/dev/null 2>&1 && echo yes),yes)
PYTHON ?= uv run python
REPORT_PYTHON ?= uv run --with matplotlib python
else
PYTHON ?= python3
REPORT_PYTHON ?= python3
endif
EVAL_CASES ?= data/eval_cases.json
RAG_DRAFT_CASES ?= data/eval_cases_migrated_draft_round4.json
FINETUNE_DATA ?= data/finetune_dataset_500_strict.jsonl
FEWSHOT_DATA ?= data/fewshot_examples_20_strict.json
HISTORICAL_FINETUNE_DATA ?= data/finetune_dataset_500.jsonl
HISTORICAL_FEWSHOT_DATA ?= data/fewshot_examples_20.json
CONFIG_DIR ?= configs
RAG_REPORT_DIR ?= artifacts/rag
TRAIN_CONFIG ?= $(CONFIG_DIR)/strict_clean_20260329.yaml
TRAIN_STRICT_CONFIG ?= $(CONFIG_DIR)/train_config_strict_replay_20260329.yaml
HISTORICAL_TRAIN_CONFIG ?= $(CONFIG_DIR)/train_config_20260327_143745.yaml
TRAIN_LOG ?= logs/strict_clean_20260329.train.log
HISTORICAL_TRAIN_LOG ?= logs/train_20260327_143745.log
STRICT_ADAPTER_TARBALL ?= artifacts/handoff/strict_clean_20260329_minimal.tar.gz
STRICT_ADAPTER_DIR ?= artifacts/lora/qwen3.5-9b/strict_clean_20260329
FT_STRATEGY ?= ft
FT_OUTPUT ?=
RAG_FORMAL_REPORT ?= results/rag_google_eval_54cases_20260328.json

.PHONY: help eval-baseline eval-pe eval-rag eval-rag-draft eval-ft eval-all train train-historical train-strict train-strict-dry-run qwen-strict-rerun report report-final lint-data lint-data-historical audit-strict rescore-strict check-train-env check-train-env-historical check-train-env-strict audit-train-log audit-train-log-historical materialize-strict-adapter

help:
	@echo "可用目标："
	@echo "  make eval-baseline  - 输出正式评测集摘要"
	@echo "  make eval-pe        - 预览 PE 提示词元数据（v2 few-shot 方案）"
	@echo "  make eval-rag       - 运行正式评测集的 Google embedding 检索指标"
	@echo "  make eval-rag-draft - 运行 32 条 draft 评测集的检索指标并写入 JSON 报告"
	@echo "  make eval-ft        - 用 strict-clean adapter 运行 FT / PE+FT / PE+RAG+FT 评测"
	@echo "  make eval-all       - 一次性输出摘要、检索结果与提示词元数据"
	@echo "  make train          - 启动当前正式 strict-clean LoRA 训练入口（LLaMA-Factory）"
	@echo "  make train-historical - 启动历史正式 LoRA 训练入口（归档对照）"
	@echo "  make train-strict   - 启动 strict-clean LoRA 重训入口（含逐步 eval_loss）"
	@echo "  make train-strict-dry-run - 只做 strict 训练预检，不实际启动训练"
	@echo "  make qwen-strict-rerun - 在 GPU 环境上一键完成 strict-clean 训练与评测"
	@echo "  make check-train-env        - 检查当前正式 strict-clean 训练环境是否就绪"
	@echo "  make check-train-env-historical - 检查历史正式训练环境是否就绪"
	@echo "  make check-train-env-strict - 检查 strict 训练环境是否就绪"
	@echo "  make audit-train-log        - 解析当前正式 strict-clean 训练日志并导出结构化摘要"
	@echo "  make report         - 生成最终图表与指标快照"
	@echo "  make report-final   - 等同于 make report"
	@echo "  make lint-data      - 用 data_guard.py 校验当前 strict-clean 微调数据并做 overlap 审计"
	@echo "  make lint-data-historical - 校验历史正式微调数据（仅归档用途）"
	@echo "  make audit-strict   - 生成 strict 数据污染审计与去污染数据集"
	@echo "  make rescore-strict - 对现有结果做 strict 分层重评分"
	@echo "  make materialize-strict-adapter - 从 handoff 包提取 strict-clean adapter 到默认目录"

eval-baseline:
	$(PYTHON) -m evaluation.baseline --mode baseline --eval-cases $(EVAL_CASES)

eval-pe:
	$(PYTHON) -m evaluation.baseline --mode pe --prompt-version v2 --eval-cases $(EVAL_CASES)

eval-rag:
	@echo "=== RAG 检索评测（正式口径） ==="
	@echo "Embedding: google / gemini-embedding-001"
	@echo "输出文件: $(RAG_FORMAL_REPORT)"
	@test -n "$$GOOGLE_API_KEY" || (echo "错误：未设置 GOOGLE_API_KEY" && exit 1)
	@EMBEDDING_PROVIDER=google GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001 \
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(EVAL_CASES) \
	--query-mode question_plus_entry --rrf-k 30 --per-source 12 --top-k 5 \
	--report-path $(RAG_FORMAL_REPORT)

eval-rag-draft:
	$(PYTHON) -m evaluation.baseline --mode rag --eval-cases $(RAG_DRAFT_CASES) --query-mode question_only --report-path $(RAG_REPORT_DIR)/rag_eval_round4_question_only.json

materialize-strict-adapter:
	$(PYTHON) scripts/materialize_strict_adapter.py --tarball $(STRICT_ADAPTER_TARBALL) --output-dir $(STRICT_ADAPTER_DIR)

eval-ft: materialize-strict-adapter
	$(PYTHON) run_ft_eval.py --strategy $(FT_STRATEGY) --cases $(EVAL_CASES) --repo-root external/celery --adapter-path $(STRICT_ADAPTER_DIR) $(if $(FT_OUTPUT),--output $(FT_OUTPUT),)

eval-all:
	$(PYTHON) -m evaluation.baseline --mode all --prompt-version v2 --eval-cases $(EVAL_CASES)

train:
	@echo "=== 当前正式 strict-clean 训练入口 ==="
	@echo "训练后端: LLaMA-Factory"
	@echo "配置: $(TRAIN_CONFIG)"
	@echo "数据集: $(FINETUNE_DATA)"
	@echo "参考日志: $(TRAIN_LOG)"
	$(PYTHON) finetune/train_lora.py --config $(TRAIN_CONFIG)

train-historical:
	@echo "=== 微调训练入口 ==="
	@echo "训练后端: LLaMA-Factory"
	@echo "硬件要求: A100 40G GPU"
	@echo "预计训练时间: 约 37 分钟"
	@echo "参考日志: $(HISTORICAL_TRAIN_LOG)"
	$(PYTHON) finetune/train_lora.py --config $(HISTORICAL_TRAIN_CONFIG)

train-strict: train
	@echo "=== Strict 微调训练入口 ==="
	@echo "训练后端: LLaMA-Factory"
	@echo "数据集: $(FINETUNE_DATA)"
	@echo "配置: $(TRAIN_CONFIG)"

train-strict-dry-run:
	@echo "=== Strict 微调预检 ==="
	$(PYTHON) finetune/train_lora.py --config $(TRAIN_STRICT_CONFIG) --dry-run

check-train-env:
	$(PYTHON) scripts/check_train_env.py --config $(TRAIN_CONFIG) --require-cuda

check-train-env-historical:
	$(PYTHON) scripts/check_train_env.py --config $(HISTORICAL_TRAIN_CONFIG) --require-cuda

check-train-env-strict: check-train-env

audit-train-log:
	$(PYTHON) scripts/analyze_training_log.py --log $(TRAIN_LOG) --output results/training_log_summary_20260329.json

audit-train-log-historical:
	$(PYTHON) scripts/analyze_training_log.py --log $(HISTORICAL_TRAIN_LOG) --output results/training_log_summary_historical_20260329.json

qwen-strict-rerun:
	@echo "=== Qwen strict-clean 一键复验 ==="
	@echo "需要 CUDA GPU + llamafactory-cli"
	./scripts/run_qwen_strict_full.sh

report:
	$(PYTHON) scripts/generate_project_progress_report.py
	$(REPORT_PYTHON) scripts/generate_final_delivery_assets.py

report-final: report

lint-data:
	$(PYTHON) -m finetune.data_guard $(FINETUNE_DATA)

lint-data-historical:
	$(PYTHON) -m finetune.data_guard $(HISTORICAL_FINETUNE_DATA)

audit-strict:
	$(PYTHON) scripts/build_strict_datasets.py

rescore-strict:
	$(PYTHON) scripts/rescore_official_results.py

report-status:
	@echo "正式报告："
	@echo "  - reports/DELIVERY_REPORT.md"
	@echo "  - reports/bottleneck_diagnosis.md"
	@echo "  - reports/pe_optimization.md"
	@echo "  - reports/rag_pipeline.md"
	@echo "  - reports/ablation_study.md"
