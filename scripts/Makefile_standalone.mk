# =============================================================================
# Standalone Makefile fragment for RAG cache management
#
# 用法（在项目根目录执行）:
#   make -f scripts/Makefile_standalone.mk prepare-rag-cache
#   make -f scripts/Makefile_standalone.mk rebuild-rag-cache
#
# 依赖环境变量:
#   GOOGLE_API_KEY / MODELSCOPE_API_KEY — 必须设置
# =============================================================================

ifeq ($(shell command -v uv >/dev/null 2>&1 && echo yes),yes)
PYTHON ?= uv run python
else
PYTHON ?= python
endif

REPO_ROOT := $(shell cd $(dir $(lastword $(MAKEFILE_LIST))).. && pwd)

.PHONY: prepare-rag-cache rebuild-rag-cache check-api-key

# ---------------------------------------------------------------------------
# RAG Cache targets
# ---------------------------------------------------------------------------

# 检查 API Key 是否设置
check-api-key:
	@if [ -z "$$GOOGLE_API_KEY" ] && [ -z "$$MODELSCOPE_API_KEY" ]; then \
		echo "ERROR: Neither GOOGLE_API_KEY nor MODELSCOPE_API_KEY is set."; \
		echo "Set one of them before running this target."; \
		exit 1; \
	fi

# 确保 cache 存在（如果已存在则跳过）
prepare-rag-cache: check-api-key
	@echo "=== RAG cache bootstrap ==="
	@EMBEDDING_PROVIDER=google GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001 \
	$(PYTHON) scripts/ensure_rag_cache.py --repo-root external/celery

# 强制重建 cache（无论是否已存在）
rebuild-rag-cache: check-api-key
	@echo "=== RAG cache force rebuild ==="
	@GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001 \
	GOOGLE_EMBEDDING_DIM=3072 \
	$(PYTHON) -m scripts.precompute_embeddings --repo-root external/celery
	@echo "Done. Cache rebuilt."
