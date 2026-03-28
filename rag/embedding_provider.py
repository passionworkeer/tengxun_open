from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MODELSCOPE_MODEL = "Qwen/Qwen3-Embedding-8B"
DEFAULT_MODELSCOPE_DIM = 4096
DEFAULT_MODELSCOPE_CACHE_FILE = Path("artifacts/rag/embeddings_cache.json")

DEFAULT_GOOGLE_MODEL = "models/gemini-embedding-001"
DEFAULT_GOOGLE_DIM = 3072


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model: str
    dimension: int
    api_key_env: str
    api_key: str
    cache_file: Path
    request_timeout: float = 120.0

    @property
    def provider_label(self) -> str:
        return f"{self.provider}:{self.model}"


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def _default_google_cache_file(model: str, dimension: int) -> Path:
    model_slug = _slugify(model.removeprefix("models/"))
    return Path(f"artifacts/rag/embeddings_cache_google_{model_slug}_{dimension}.json")


def resolve_embedding_config() -> EmbeddingConfig:
    provider = os.environ.get("EMBEDDING_PROVIDER", "").strip().lower()
    if provider not in {"google", "modelscope"}:
        provider = "google" if os.environ.get("GOOGLE_API_KEY") else "modelscope"

    if provider == "google":
        model = os.environ.get("GOOGLE_EMBEDDING_MODEL", DEFAULT_GOOGLE_MODEL).strip()
        dimension = int(os.environ.get("GOOGLE_EMBEDDING_DIM", str(DEFAULT_GOOGLE_DIM)))
        cache_default = _default_google_cache_file(model, dimension)
        cache_file = Path(os.environ.get("EMBEDDING_CACHE_FILE", str(cache_default)))
        api_key_env = "GOOGLE_API_KEY"
    else:
        model = os.environ.get("MODELSCOPE_EMBEDDING_MODEL", DEFAULT_MODELSCOPE_MODEL).strip()
        dimension = int(
            os.environ.get("MODELSCOPE_EMBEDDING_DIM", str(DEFAULT_MODELSCOPE_DIM))
        )
        cache_file = Path(
            os.environ.get("EMBEDDING_CACHE_FILE", str(DEFAULT_MODELSCOPE_CACHE_FILE))
        )
        api_key_env = "MODELSCOPE_API_KEY"

    return EmbeddingConfig(
        provider=provider,
        model=model,
        dimension=dimension,
        api_key_env=api_key_env,
        api_key=os.environ.get(api_key_env, ""),
        cache_file=cache_file,
        request_timeout=float(os.environ.get("EMBEDDING_REQUEST_TIMEOUT", "120")),
    )


def load_embedding_cache(
    config: EmbeddingConfig,
    *,
    valid_chunk_ids: set[str] | None = None,
) -> dict[str, list[float]]:
    if not config.cache_file.exists():
        return {}

    raw = json.loads(config.cache_file.read_text(encoding="utf-8"))
    embeddings: dict[str, list[float]]

    if isinstance(raw, dict) and "_meta" in raw and "embeddings" in raw:
        meta = raw.get("_meta", {})
        if meta.get("provider") != config.provider or meta.get("model") != config.model:
            return {}
        if int(meta.get("dimension", 0)) != config.dimension:
            return {}
        embeddings = raw.get("embeddings", {})
    elif (
        isinstance(raw, dict)
        and config.provider == "modelscope"
        and config.cache_file == DEFAULT_MODELSCOPE_CACHE_FILE
    ):
        embeddings = raw
    else:
        return {}

    if valid_chunk_ids is None:
        return embeddings
    return {cid: emb for cid, emb in embeddings.items() if cid in valid_chunk_ids}


def save_embedding_cache(config: EmbeddingConfig, embeddings: dict[str, list[float]]) -> None:
    config.cache_file.parent.mkdir(parents=True, exist_ok=True)

    if config.provider == "modelscope" and config.cache_file == DEFAULT_MODELSCOPE_CACHE_FILE:
        payload: Any = embeddings
    else:
        payload = {
            "_meta": {
                "provider": config.provider,
                "model": config.model,
                "dimension": config.dimension,
            },
            "embeddings": embeddings,
        }

    config.cache_file.write_text(json.dumps(payload), encoding="utf-8")


class EmbeddingProviderClient:
    def __init__(self, config: EmbeddingConfig) -> None:
        self.config = config
        self._client = None

    def available(self) -> bool:
        return bool(self.config.api_key)

    def batch_embed(self, texts: list[str]) -> list[list[float]]:
        if self.config.provider == "google":
            return self._google_batch_embed(texts)
        return self._modelscope_batch_embed(texts)

    def embed_query(self, text: str) -> list[float]:
        if self.config.provider == "google":
            return self._google_single_embed(text)
        return self._modelscope_batch_embed([text])[0]

    def _ensure_modelscope_client(self) -> Any:
        if self._client is not None:
            return self._client
        import openai

        self._client = openai.OpenAI(
            base_url="https://api-inference.modelscope.cn/v1",
            api_key=self.config.api_key,
        )
        return self._client

    def _modelscope_batch_embed(self, texts: list[str]) -> list[list[float]]:
        client = self._ensure_modelscope_client()
        resp = client.embeddings.create(
            model=self.config.model,
            input=texts,
            encoding_format="float",
            timeout=self.config.request_timeout,
        )
        if resp.data is None:
            raise RuntimeError("resp.data is None")
        return [item.embedding for item in resp.data]

    def _google_request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        model_path = (
            self.config.model
            if self.config.model.startswith("models/")
            else f"models/{self.config.model}"
        )
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"{model_path}:{method}?key={self.config.api_key}"
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google embedding error {exc.code}: {body}") from exc

    def _google_single_embed(self, text: str) -> list[float]:
        model_path = (
            self.config.model
            if self.config.model.startswith("models/")
            else f"models/{self.config.model}"
        )
        payload: dict[str, Any] = {
            "model": model_path,
            "content": {"parts": [{"text": text}]},
        }
        if self.config.dimension != DEFAULT_GOOGLE_DIM:
            payload["outputDimensionality"] = self.config.dimension

        data = self._google_request("embedContent", payload)
        return data.get("embedding", {}).get("values", [])

    def _google_batch_embed(self, texts: list[str]) -> list[list[float]]:
        model_path = (
            self.config.model
            if self.config.model.startswith("models/")
            else f"models/{self.config.model}"
        )
        requests_payload: list[dict[str, Any]] = []
        for text in texts:
            item: dict[str, Any] = {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
            }
            if self.config.dimension != DEFAULT_GOOGLE_DIM:
                item["outputDimensionality"] = self.config.dimension
            requests_payload.append(item)

        data = self._google_request(
            "batchEmbedContents",
            {"requests": requests_payload},
        )
        embeddings = data.get("embeddings", [])
        return [item.get("values", []) for item in embeddings]
