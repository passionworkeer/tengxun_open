#!/usr/bin/env python3
"""
Pre-compute Qwen3-Embedding-8B embeddings for all chunks in the Celery repo.

Saves to artifacts/rag/embeddings_cache.json. Can be stopped and restarted;
already-computed embeddings are loaded from cache.

Usage: python3 scripts/precompute_embeddings.py

Rate limits: ModelScope throttles bulk embedding. This script:
- Batches 25 items per request (safe under 8192 token limit)
- Adds 2s delay between batches to avoid 429s
- Saves cache after every 5 batches (125 chunks)
- Retries failed batches up to 3 times with 10s backoff

8086 chunks / 25 per batch * ~8s per batch = ~43 min with 2s delays.
Run in background: nohup python3 scripts/precompute_embeddings.py &
"""

import json
import os
import time
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────
MODEL = "Qwen/Qwen3-Embedding-8B"
BATCH_SIZE = 25
BATCH_DELAY = 2.0  # seconds between batches (rate limit guard)
SAVE_EVERY = 5  # save cache every N batches
MAX_RETRIES = 3
RETRY_DELAY = 10.0
MAX_CHARS = 2000  # chars per chunk (token budget)
CACHE_FILE = Path("artifacts/rag/embeddings_cache.json")
REPO_ROOT = Path("external/celery")

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from rag.ast_chunker import chunk_repository


def build_client() -> OpenAI:
    api_key = os.environ.get("MODELSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("MODELSCOPE_API_KEY environment variable not set")
    return OpenAI(
        base_url="https://api-inference.modelscope.cn/v1",
        api_key=api_key,
    )


def load_cache() -> dict[str, list[float]]:
    if CACHE_FILE.exists():
        try:
            raw = json.loads(CACHE_FILE.read_text())
            print(f"Loaded {len(raw)} cached embeddings from {CACHE_FILE}")
            return raw
        except Exception as e:
            print(f"Cache load failed: {e}, starting fresh")
    return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache))
    print(f"Cache saved: {len(cache)} embeddings")


def embed_batch(
    client: OpenAI, texts: list[str], chunk_ids: list[str]
) -> dict[str, list[float]]:
    """Returns {chunk_id: embedding} for successfully embedded items."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.embeddings.create(
                model=MODEL,
                input=texts,
                encoding_format="float",
            )
            if resp.data is None:
                raise RuntimeError("resp.data is None (rate limited)")
            result = {}
            for item in resp.data:
                cid = chunk_ids[item.index]
                result[cid] = item.embedding
            return result
        except Exception as exc:
            wait = RETRY_DELAY * (attempt + 1)
            print(
                f"  [RETRY {attempt + 1}/{MAX_RETRIES}] {exc} — waiting {wait}s",
                flush=True,
            )
            time.sleep(wait)
    return {}


def truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    return text if len(text) <= max_chars else text[:max_chars]


def main() -> None:
    print(f"=== Qwen3-Embedding-8B Pre-compute ===")
    print(f"Model: {MODEL}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Batch delay: {BATCH_DELAY}s")
    print(f"Max chars/chunk: {MAX_CHARS}")
    print(f"Cache: {CACHE_FILE}")
    print()

    client = build_client()
    cache = load_cache()

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

        result = embed_batch(client, batch_texts, batch_ids)

        if result:
            cache.update(result)
            rate = len(cache) / (time.time() - t0)
            remaining = len(missing) - len(cache)
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
        if (batch_idx + 1) % SAVE_EVERY == 0:
            save_cache(cache)

        # Rate limit guard
        if batch_delay := BATCH_DELAY:
            time.sleep(batch_delay)

    # Final save
    save_cache(cache)
    total_time = time.time() - t0
    print(f"\nDone! {len(cache)}/{total} embeddings in {total_time / 60:.1f}min")
    print(f"Cache: {CACHE_FILE}")


if __name__ == "__main__":
    main()
