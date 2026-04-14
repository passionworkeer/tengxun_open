"""
Unified embedding provider client supporting multiple backends.

Supports two providers:
    - **Google**: Vertex AI / Generative Language API (gemini-embedding-001)
    - **ModelScope**: Qwen3-Embedding-8B via the ModelScope OpenAI-compatible API

Each provider has its own cache file format. The appropriate provider is
selected at runtime via the `EMBEDDING_PROVIDER` environment variable or
by detecting the presence of `GOOGLE_API_KEY` / `MODELSCOPE_API_KEY`.

Exports:
    EmbeddingConfig, EmbeddingProviderClient
    resolve_embedding_config, load_embedding_cache, save_embedding_cache
"""

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
    """Configuration for an embedding provider.

    Attributes:
        provider: Provider name — ``"google"`` or ``"modelscope"``.
        model: Model identifier (e.g. ``"models/gemini-embedding-001"``).
        dimension: Embedding vector dimension. Must match the model's output
            dimensionality to use cached embeddings correctly.
        api_key_env: Name of the environment variable that holds the API key
            (e.g. ``"GOOGLE_API_KEY"`` or ``"MODELSCOPE_API_KEY"``).
        api_key: The resolved API key value.
        cache_file: Path to the on-disk embedding cache file. Format differs
            between providers: ModelScope uses a flat dict, Google uses a
            ``{"_meta": {...}, "embeddings": {...}}`` envelope.
        request_timeout: HTTP request timeout in seconds (default 120 s).
    """

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
    """Convert a string into a safe filesystem name.

    Replaces runs of non-alphanumeric characters with a single underscore,
    strips leading/trailing underscores, and lowercases the result.

    Args:
        value: Arbitrary string (e.g. a model name).

    Returns:
        A lowercase, underscore-only slug suitable for use in filenames.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def _default_google_cache_file(model: str, dimension: int) -> Path:
    """Build the default cache file path for a Google embedding model.

    The path is derived from the model name (slugified) and the embedding
    dimension so that caches for different model configurations do not
    collide.

    Args:
        model: Full model path string, e.g. ``"models/gemini-embedding-001"``.
        dimension: Embedding vector dimension.

    Returns:
        Path under ``artifacts/rag/`` named
        ``embeddings_cache_google_{slug}_{dimension}.json``.
    """
    model_slug = _slugify(model.removeprefix("models/"))
    return Path(f"artifacts/rag/embeddings_cache_google_{model_slug}_{dimension}.json")


def resolve_embedding_config() -> EmbeddingConfig:
    """Resolve an :class:`EmbeddingConfig` from environment variables.

    The provider is determined in the following priority:

    1. ``EMBEDDING_PROVIDER`` environment variable (``"google"`` or ``"modelscope"``).
    2. ``"google"`` if ``GOOGLE_API_KEY`` is set.
    3. ``"modelscope"`` as a fallback.

    Provider-specific model, dimension, and cache-file settings are read from
    the corresponding environment variables or fall back to the module-level
    defaults.

    Returns:
        A fully-populated :class:`EmbeddingConfig` instance. The ``api_key``
        field may be empty if no matching environment variable was found;
        check :meth:`EmbeddingProviderClient.available` before making requests.
    """
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
    """Load cached embeddings from the file specified in *config*.

    If the cache file does not exist or was produced by a different
    provider / model / dimension, an empty dict is returned so that
    callers treat the cache as invalid without having to catch exceptions.

    Args:
        config: :class:`EmbeddingConfig` describing the expected provider,
            model, dimension, and cache file location.
        valid_chunk_ids: If provided, only embeddings whose chunk ID is in
            this set are returned. Use this to filter out stale entries when
            the codebase has changed since the cache was written.

    Returns:
        A dict mapping ``chunk_id -> embedding list[float]``. Returns an
        empty dict when the cache is absent, mismatched, or corrupted.
    """
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
    """Persist *embeddings* to the cache file specified in *config*.

    The parent directory is created if it does not exist. The file format
    is chosen based on the provider: ModelScope uses a flat ``dict`` (legacy
    compatibility), while all other providers use an envelope with a
    ``_meta`` field so that future loads can validate provider/model/dimension
    match.

    Args:
        config: :class:`EmbeddingConfig` describing the target cache file.
        embeddings: Dict mapping ``chunk_id -> embedding list[float]`` to write.
    """
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
    """Unified client for generating text embeddings via Google or ModelScope.

    The client dispatches to the appropriate backend based on
    :attr:`EmbeddingConfig.provider`. It is safe to instantiate even when
    no API key is set; use :meth:`available` to check readiness before
    calling :meth:`batch_embed` or :meth:`embed_query`.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        """Initialise the client with the given *config*.

        Args:
            config: :class:`EmbeddingConfig` resolved from environment.
                Must not be ``None``; pass a manually-constructed config if
                you want to override defaults.
        """
        self.config = config
        self._client = None

    def available(self) -> bool:
        """Return ``True`` when a non-empty API key is present in *config*.

        Always returns ``False`` for a freshly-constructed config unless the
        corresponding environment variable was set.
        """
        return bool(self.config.api_key)

    def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: List of text strings to embed. Empty strings are skipped.

        Returns:
            A parallel list of embedding vectors (each a ``list[float]``),
            in the same order as *texts*. Vectors have length
            :attr:`EmbeddingConfig.dimension`.

        Raises:
            RuntimeError: If the underlying API call fails (network error,
                authentication failure, quota exceeded, etc.).
        """
        if self.config.provider == "google":
            return self._google_batch_embed(texts)
        return self._modelscope_batch_embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """Generate an embedding vector for a single query string.

        This is a convenience wrapper around :meth:`batch_embed` with a
        single-element list. Prefer it for ad-hoc single queries to avoid
        the overhead of :meth:`batch_embed`.

        Args:
            text: The query string to embed.

        Returns:
            An embedding vector of length :attr:`EmbeddingConfig.dimension`.
        """
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
        """Call the ModelScope OpenAI-compatible embeddings API.

        Uses :meth:`_ensure_modelscope_client` to lazily initialise the
        ``openai.OpenAI`` client pointing at the ModelScope base URL.

        Args:
            texts: List of texts to embed.

        Returns:
            Parallel list of embedding vectors.

        Raises:
            RuntimeError: If the API returns a malformed response
                (e.g. ``resp.data is None``).
        """
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
        """Send a signed request to a Google Generative Language API endpoint.

        Constructs the URL from :attr:`EmbeddingConfig.model` and the
        ``method`` argument (e.g. ``"embedContent"`` or ``"batchEmbedContents"``),
        then POSTs the JSON *payload* with the API key appended as a query
        parameter.

        Args:
            method: API method name, either ``"embedContent"`` or
                ``"batchEmbedContents"``.
            payload: JSON-serialisable request body.

        Returns:
            The parsed JSON response dict.

        Raises:
            RuntimeError: If the HTTP response status code is non-2xx.
                The exception message includes the HTTP status and the
                decoded error body.
        """
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
        """Generate an embedding for a single text via the Google ``embedContent`` API.

        Args:
            text: The text string to embed.

        Returns:
            Embedding vector as a flat list of floats.
        """
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
        """Generate embeddings for a batch of texts via the Google ``batchEmbedContents`` API.

        All texts are packed into a single ``batchEmbedContents`` request,
        which is more efficient than calling :meth:`_google_single_embed`
        repeatedly.

        Args:
            texts: List of text strings to embed.

        Returns:
            Parallel list of embedding vectors, in the same order as *texts*.
        """
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
