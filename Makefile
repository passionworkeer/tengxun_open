ifeq ($(shell command -v uv >/dev/null 2>&1 && echo yes),yes)
PYTHON ?= uv run python
REPORT_PYTHON ?= uv run --with matplotlib python
else
PYTHON ?= python3
REPORT_PYTHON ?= python3
endif
EVAL_CASES ?= data/eval_cases.json
RAG_DRAFT_CASES ?= data/eval_cases_migrated_draft_round4.json
FINETUNE_DATA ?= data/finetune_dataset_500.jsonl
FEWSHOT_DATA ?= data/fewshot_examples_20.json
CONFIG_DIR ?= configs
RAG_REPORT_DIR ?= artifacts/rag
TRAIN_CONFIG ?= $(CONFIG_DIR)/train_config_20260327_143745.yaml
TRAIN_STRICT_CONFIG ?= $(CONFIG_DIR)/train_config_strict_replay_20260329.yaml
RAG_FORMAL_REPORT ?= results/rag_google_eval_54cases_20260328.json

.PHONY: help eval-baseline eval-pe eval-rag eval-rag-draft eval-ft eval-all train train-strict train-strict-dry-run qwen-strict-rerun report report-final lint-data audit-strict rescore-strict check-train-env check-train-env-strict audit-train-log

help:
	@echo "可用目标："
	@echo "  make eval-baseline  - 输出正式评测集摘要"
	@echo "  make eval-pe        - 预览 PE 提示词元数据（v2 few-shot 方案）"
	@echo "  make eval-rag       - 运行正式评测集的 Google embedding 检索指标"
	@echo "  make eval-rag-draft - 运行 32 条 draft 评测集的检索指标并写入 JSON 报告"
	@echo "  make eval-ft        - 预留给微调模型评测入口"
	@echo "  make eval-all       - 一次性输出摘要、检索结果与提示词元数据"
	@echo "  make train          - 启动正式 LoRA 训练入口（LLaMA-Factory）"
	@echo "  make train-strict   - 启动 strict-clean LoRA 重训入口（含逐步 eval_loss）"
	@echo "  make train-strict-dry-run - 只做 strict 训练预检，不实际启动训练"
	@echo "  make qwen-strict-rerun - 在 GPU 环境上一键完成 strict-clean 训练与评测"
	@echo "  make check-train-env        - 检查正式训练环境是否就绪"
	@echo "  make check-train-env-strict - 检查 strict 训练环境是否就绪"
	@echo "  make audit-train-log        - 解析正式训练日志并导出结构化摘要"
	@echo "  make report         - 生成最终图表与指标快照"
	@echo "  make report-final   - 等同于 make report"
	@echo "  make lint-data      - 用 data_guard.py 校验微调数据"
	@echo "  make audit-strict   - 生成 strict 数据污染审计与去污染数据集"
	@echo "  make rescore-strict - 对现有结果做 strict 分层重评分"

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

eval-ft:
	@echo "eval-ft 当前还没有单独接线；请先产出 checkpoint，再补专门评测入口。"

eval-all:
	$(PYTHON) -m evaluation.baseline --mode all --prompt-version v2 --eval-cases $(EVAL_CASES)

train:
	@echo "=== 微调训练入口 ==="
	@echo "训练后端: LLaMA-Factory"
	@echo "硬件要求: A100 40G GPU"
	@echo "预计训练时间: 约 37 分钟"
	@echo "参考日志: logs/train_20260327_143745.log"
	$(PYTHON) finetune/train_lora.py --config $(TRAIN_CONFIG)

train-strict:
	@echo "=== Strict 微调训练入口 ==="
	@echo "训练后端: LLaMA-Factory"
	@echo "数据集: data/finetune_dataset_500_strict.jsonl"
	@echo "配置: $(TRAIN_STRICT_CONFIG)"
	$(PYTHON) finetune/train_lora.py --config $(TRAIN_STRICT_CONFIG)

train-strict-dry-run:
	@echo "=== Strict 微调预检 ==="
	$(PYTHON) finetune/train_lora.py --config $(TRAIN_STRICT_CONFIG) --dry-run

check-train-env:
	$(PYTHON) scripts/check_train_env.py --config $(TRAIN_CONFIG) --require-cuda

check-train-env-strict:
	$(PYTHON) scripts/check_train_env.py --config $(TRAIN_STRICT_CONFIG) --require-cuda

audit-train-log:
	$(PYTHON) scripts/analyze_training_log.py --log logs/train_20260327_143745.log --output results/training_log_summary_20260329.json

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
