#!/usr/bin/env bash
# =============================================================================
# 重建 RAG Embedding Cache
#
# 用法:
#   bash scripts/rebuild_rag_cache.sh
#   EMBEDDING_PROVIDER=google GOOGLE_API_KEY=xxx bash scripts/rebuild_rag_cache.sh
#
# 依赖环境变量（优先从环境读取，缺失则提示）:
#   GOOGLE_API_KEY        - Google API Key（用于 gemini-embedding-001）
#   MODELSCOPE_API_KEY    - ModelScope API Key（fallback 方案）
#   EMBEDDING_PROVIDER    - google | modelscope（默认自动检测）
#   GOOGLE_EMBEDDING_MODEL - 嵌入模型名（默认 models/gemini-embedding-001）
#   GOOGLE_EMBEDDING_DIM    - 嵌入维度（默认 3072）
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== RAG Embedding Cache Rebuild ==="
echo "Repo root: $REPO_ROOT"

# 检测 provider
if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
    PROVIDER_LABEL="google"
    echo "Provider: $PROVIDER_LABEL (GOOGLE_API_KEY set)"
elif [[ -n "${MODELSCOPE_API_KEY:-}" ]]; then
    PROVIDER_LABEL="modelscope"
    echo "Provider: $PROVIDER_LABEL (MODELSCOPE_API_KEY set)"
else
    echo "ERROR: Neither GOOGLE_API_KEY nor MODELSCOPE_API_KEY is set." >&2
    echo "Please set one of them before running this script." >&2
    exit 1
fi

# 检查 Python
if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
    echo "ERROR: Python not found in PATH" >&2
    exit 1
fi

PYTHON_CMD="${PYTHON:-python}"
echo "Python: $PYTHON_CMD"

cd "$REPO_ROOT"

# 运行预计算脚本
# embedding_provider.py 中 cache 文件名由环境变量决定
# 默认 google: artifacts/rag/embeddings_cache_google_gemini_embedding_001_3072.json
export EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-}"
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
export MODELSCOPE_API_KEY="${MODELSCOPE_API_KEY:-}"
export GOOGLE_EMBEDDING_MODEL="${GOOGLE_EMBEDDING_MODEL:-models/gemini-embedding-001}"
export GOOGLE_EMBEDDING_DIM="${GOOGLE_EMBEDDING_DIM:-3072}"

echo "Embedding model: $GOOGLE_EMBEDDING_MODEL"
echo "Embedding dim:   $GOOGLE_EMBEDDING_DIM"

# 调用 precompute_embeddings.py，--repo-root 指向 celery 源码
echo ""
echo "Starting precompute... (this may take a while)"
"$PYTHON_CMD" -m scripts.precompute_embeddings \
    --repo-root external/celery

echo ""
echo "=== Rebuild Complete ==="
echo "Cache file: artifacts/rag/embeddings_cache_$(echo "$PROVIDER_LABEL" | tr 'a-z' 'a-z')_$(echo "$GOOGLE_EMBEDDING_MODEL" | sed 's/[/ ]/_/g')_$GOOGLE_EMBEDDING_DIM.json"
