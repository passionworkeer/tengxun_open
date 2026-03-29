#!/usr/bin/env python3
"""
确保当前 provider 对应的 RAG embedding cache 完整可用。

如果缓存缺失或不完整，则自动触发预计算脚本。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag.ast_chunker import chunk_repository
from rag.embedding_provider import load_embedding_cache, resolve_embedding_config
from scripts.precompute_embeddings import build_cache


def count_expected_chunks(repo_root: Path) -> tuple[int, set[str]]:
    chunks = chunk_repository(repo_root)
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    return len(chunk_ids), chunk_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure formal RAG cache is ready.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("external/celery"),
        help="Repository root to chunk and embed.",
    )
    args = parser.parse_args()

    config = resolve_embedding_config()
    total, valid_ids = count_expected_chunks(args.repo_root)
    cached = load_embedding_cache(config, valid_chunk_ids=valid_ids)
    cached_count = len(cached)

    print(
        f"[ensure_rag_cache] provider={config.provider} model={config.model} "
        f"cache={config.cache_file} cached={cached_count}/{total}"
    )
    if cached_count == total:
        print("[ensure_rag_cache] cache already complete")
        return 0

    print("[ensure_rag_cache] cache incomplete, rebuilding...")
    build_cache(args.repo_root)

    refreshed = load_embedding_cache(config, valid_chunk_ids=valid_ids)
    refreshed_count = len(refreshed)
    print(
        f"[ensure_rag_cache] rebuild finished: cached={refreshed_count}/{total} "
        f"at {config.cache_file}"
    )
    if refreshed_count != total:
        raise SystemExit(
            "RAG cache is still incomplete after rebuild. "
            "Check API quota / provider credentials and rerun."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
