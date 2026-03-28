#!/usr/bin/env python3
"""
Pre-compute provider-aware embeddings for all chunks in the Celery repo.

Default provider selection:
- `EMBEDDING_PROVIDER=google` + `GOOGLE_API_KEY`
- otherwise `MODELSCOPE_API_KEY`

Cache is provider-aware and can be stopped/restarted safely.

Usage: python3 scripts/precompute_embeddings.py
"""

import json
import os
import re
import time
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────
BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "10"))
BATCH_DELAY = float(os.environ.get("EMBED_BATCH_DELAY", "3.0"))  # seconds between batches
SAVE_EVERY = 5  # save cache every N batches
MAX_RETRIES = int(os.environ.get("EMBED_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("EMBED_RETRY_DELAY", "10.0"))
MAX_CHARS = int(os.environ.get("EMBED_MAX_CHARS", "2000"))  # chars per chunk
REPO_ROOT = Path("external/celery")

sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.ast_chunker import chunk_repository
from rag.embedding_provider import (
    EmbeddingConfig,
    EmbeddingProviderClient,
    load_embedding_cache,
    resolve_embedding_config,
    save_embedding_cache,
)


_RETRY_DELAY_PATTERN = re.compile(r'"retryDelay":\s*"(\d+)s"')


class FatalQuotaError(RuntimeError):
    pass


def _extract_retry_delay(exc: Exception) -> float | None:
    match = _RETRY_DELAY_PATTERN.search(str(exc))
    if not match:
        return None
    return float(match.group(1))


def _effective_batch_delay(config: EmbeddingConfig) -> float:
    if "EMBED_BATCH_DELAY" in os.environ:
        return BATCH_DELAY
    if config.provider != "google":
        return BATCH_DELAY
    # Google free tier effectively allows about 100 embedded texts / minute.
    return max(BATCH_DELAY, (BATCH_SIZE / 100.0) * 60.0)


def _effective_save_every(config: EmbeddingConfig) -> int:
    if "EMBED_SAVE_EVERY" in os.environ:
        return max(1, int(os.environ["EMBED_SAVE_EVERY"]))
    if config.provider == "google":
        return 1
    return SAVE_EVERY


def _is_fatal_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "today's quota" in text
        or "exceeded your current quota" in text
        or "requestsperday" in text
        or "perdayperuserperprojectpermodel" in text
    )


def embed_batch(
    config: EmbeddingConfig,
    client: EmbeddingProviderClient,
    texts: list[str],
    chunk_ids: list[str],
) -> dict[str, list[float]]:
    """Returns {chunk_id: embedding} for successfully embedded items."""
    for attempt in range(MAX_RETRIES):
        try:
            embeddings = client.batch_embed(texts)
            if not embeddings:
                raise RuntimeError("empty embedding response")
            result = {}
            for cid, emb in zip(chunk_ids, embeddings):
                result[cid] = emb
            return result
        except Exception as exc:
            err_text = str(exc).lower()
            if "inappropriate content" in err_text:
                if len(texts) == 1:
                    print(
                        f"  [SKIP] content safety blocked chunk {chunk_ids[0]}",
                        flush=True,
                    )
                    return {}
                mid = len(texts) // 2
                print(
                    f"  [SPLIT] content safety on batch size {len(texts)}, bisecting",
                    flush=True,
                )
                left = embed_batch(config, client, texts[:mid], chunk_ids[:mid])
                right = embed_batch(config, client, texts[mid:], chunk_ids[mid:])
                merged = dict(left)
                merged.update(right)
                return merged
            if _is_fatal_quota_error(exc):
                raise FatalQuotaError(str(exc)) from exc
            wait = RETRY_DELAY * (attempt + 1)
            retry_after = _extract_retry_delay(exc)
            if retry_after is not None:
                wait = max(wait, retry_after + 1)
            print(
                f"  [RETRY {attempt + 1}/{MAX_RETRIES}] {exc} — waiting {wait}s",
                flush=True,
            )
            time.sleep(wait)
    return {}


def truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    return text if len(text) <= max_chars else text[:max_chars]


def main() -> None:
    config = resolve_embedding_config()
    client = EmbeddingProviderClient(config)
    if not client.available():
        raise RuntimeError(
            f"{config.api_key_env} environment variable not set for provider {config.provider}"
        )

    print("=== Embedding Pre-compute ===")
    print(f"Provider: {config.provider}")
    print(f"Model: {config.model}")
    print(f"Batch size: {BATCH_SIZE}")
    batch_delay = _effective_batch_delay(config)
    save_every = _effective_save_every(config)
    print(f"Batch delay: {batch_delay}s")
    print(f"Save every: {save_every} batch(es)")
    print(f"Max chars/chunk: {MAX_CHARS}")
    print(f"Dimension: {config.dimension}")
    print(f"Cache: {config.cache_file}")
    print()

    cache = load_embedding_cache(config)
    print(f"Loaded {len(cache)} cached embeddings from {config.cache_file}")

    # Load all chunks
    chunks = chunk_repository(REPO_ROOT)
    chunk_texts = {
        c.chunk_id: truncate(f"{c.symbol} {c.signature} {c.content}") for c in chunks
    }
    all_ids = list(chunk_texts.keys())
    total = len(all_ids)

    missing = [cid for cid in all_ids if cid not in cache]
    print(f"Total chunks: {total}")
    print(f"Cached: {len(cache)}")
    print(f"To embed: {len(missing)}")
    print()

    if not missing:
        print("All embeddings already cached!")
        return

    # Process in batches
    batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
    t0 = time.time()

    for batch_idx, batch_ids in enumerate(batches):
        batch_texts = [chunk_texts[cid] for cid in batch_ids]
        elapsed_start = time.time() - t0

        try:
            result = embed_batch(config, client, batch_texts, batch_ids)
        except FatalQuotaError as exc:
            save_embedding_cache(config, cache)
            print(f"Cache saved: {len(cache)} embeddings")
            print(
                f"\nStopped due to provider daily quota exhaustion.\n{exc}",
                flush=True,
            )
            return

        if result:
            cache.update(result)
            rate = len(cache) / (time.time() - t0)
            remaining = total - len(cache)
            eta = remaining / rate if rate > 0 else 0
            print(
                f"  [{elapsed_start / 60:.1f}min] "
                f"Batch {batch_idx + 1}/{len(batches)}: +{len(result)} "
                f"(total={len(cache)}/{total}, ETA={eta / 60:.1f}min)"
            )
        else:
            print(
                f"  [{elapsed_start / 60:.1f}min] "
                f"Batch {batch_idx + 1}/{len(batches)}: FAILED after {MAX_RETRIES} retries"
            )

        # Save periodically
        if (batch_idx + 1) % save_every == 0:
            save_embedding_cache(config, cache)
            print(f"Cache saved: {len(cache)} embeddings")

        # Rate limit guard
        if batch_delay:
            time.sleep(batch_delay)

    # Final save
    save_embedding_cache(config, cache)
    total_time = time.time() - t0
    print(f"\nDone! {len(cache)}/{total} embeddings in {total_time / 60:.1f}min")
    print(f"Cache: {config.cache_file}")


if __name__ == "__main__":
    main()
