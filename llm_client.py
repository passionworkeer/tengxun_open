"""Multi-model LLM client with mock support.

Providers:
- minimax : Anthropic-compatible (MiniMax-M2.7)
- openai  : OpenAI API (GPT-4o) or OpenAI-compatible endpoint (Qwen via vLLM)
- mock    : Deterministic responses for development / CI verification

Usage:
    # Direct
    from llm_client import call_llm_simple, LLMConfig, ModelProvider, create_client

    # MiniMax
    resp = call_llm_simple("Hello", config=LLMConfig(provider=ModelProvider.MINIMAX))

    # GPT-4o
    resp = call_llm_simple("Hello", config=LLMConfig(provider=ModelProvider.OPENAI, model="gpt-4o"))

    # Mock (always works, no API key needed)
    resp = call_llm_simple("Hello", config=LLMConfig(provider=ModelProvider.MOCK))

    # From TOML
    from llm_client import load_config_from_toml, call_llm_simple
    cfg = load_config_from_toml("configs/llm.toml", "minimax")
    resp = call_llm_simple("Hello", config=cfg)
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Provider + Config
# ---------------------------------------------------------------------------

class ModelProvider(str, Enum):
    """LLM provider / API style."""
    ANTHROPIC = "anthropic"   # MiniMax, or real Anthropic
    OPENAI    = "openai"       # GPT-4o, Qwen via OpenAI-compatible endpoint
    MOCK      = "mock"         # Deterministic fake responses


@dataclass(frozen=True)
class LLMConfig:
    """Unified config for all providers."""
    provider: ModelProvider = ModelProvider.ANTHROPIC
    model: str = "MiniMax-M2.7"
    api_key_env: str = "minimax"
    api_base: str = "https://api.minimaxi.com/anthropic"
    max_tokens: int = 4096
    temperature: float = 0.0

    def get_api_key(self) -> str | None:
        if self.provider == ModelProvider.MOCK:
            return None
        key = os.environ.get(self.api_key_env)
        if not key:
            raise ValueError(
                f"Environment variable '{self.api_key_env}' is not set or empty "
                f"(required for provider={self.provider.value})"
            )
        return key

    def to_anthropic(self) -> dict[str, Any]:
        """Return (api_key, base_url) suitable for anthropic SDK."""
        return dict(api_key=self.get_api_key(), base_url=self.api_base)

    def to_openai(self) -> dict[str, Any]:
        """Return kwargs suitable for openai.OpenAI or anthropic.Anthropic."""
        return dict(api_key=self.get_api_key(), base_url=self.api_base)


# ---------------------------------------------------------------------------
# Config loading from TOML
# ---------------------------------------------------------------------------

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


def _toml_path(project_root: Path | None = None) -> Path | None:
    """Return path to configs/llm.toml, or None if not found."""
    if project_root is None:
        project_root = Path(__file__).resolve().parent
    path = project_root / "configs" / "llm.toml"
    return path if path.exists() else None


def load_config_from_toml(
    toml_path: str | Path | None = None,
    section: str = "minimax",
) -> LLMConfig:
    """Load LLMConfig from a TOML file section.

    Args:
        toml_path : Path to the TOML file.
                    If None, searches ``{project_root}/configs/llm.toml``.
        section   : Top-level TOML section to use (e.g. "minimax", "gpt4o", "qwen").
    """
    if toml_path is None:
        toml_path = _toml_path()
    if toml_path is None:
        raise FileNotFoundError(
            "llm.toml not found at configs/llm.toml relative to project root"
        )

    raw = tomllib.loads(Path(toml_path).read_text(encoding="utf-8"))
    if section not in raw:
        available = list(raw.keys())
        raise KeyError(
            f"Section '{section}' not found in {toml_path}. Available: {available}"
        )

    s = raw[section]
    api_type = s.get("api_type", "anthropic")
    provider_map = {
        "anthropic": ModelProvider.ANTHROPIC,
        "openai":    ModelProvider.OPENAI,
        "mock":      ModelProvider.MOCK,
    }
    return LLMConfig(
        provider=provider_map.get(api_type, ModelProvider.ANTHROPIC),
        model=s.get("model", "unknown"),
        api_key_env=s.get("api_key_env", "OPENAI_API_KEY"),
        api_base=s.get("api_base", "https://api.openai.com/v1"),
        max_tokens=s.get("max_tokens", 4096),
        temperature=s.get("temperature", 0.0),
    )


# ---------------------------------------------------------------------------
# Mock responses (no API needed)
# ---------------------------------------------------------------------------

# Deterministic per-case-id hash so the same case always gets the same output.
_MOCK_GOLD: dict[str, list[str]] = {
    "easy_001":  ["celery.app.base.Celery"],
    "easy_002":  ["celery.app.shared_task"],
    "easy_003":  ["celery.loaders.default.Loader"],
    "easy_004":  ["celery.concurrency.prefork.TaskPool"],
    "medium_001": ["celery.backends.rpc.RPCBackend"],
    "medium_002": ["celery.result.AsyncResult"],
    "hard_001":  ["celery.apps.worker.Worker"],
    "hard_002":  ["celery.bin.celery:main"],
}


def _mock_response(question: str, case_id: str) -> str:
    """Return a deterministic mock JSON FQN list."""
    # Use a stable hash so retries give the same answer
    rng = random.Random(hash(case_id) & 0xFFFFFFFF)
    # Occasionally return a wrong answer (20%) to simulate imperfect baseline
    if rng.random() < 0.2:
        return json.dumps(["celery.utils.misc.SomeClass"])
    fqns = _MOCK_GOLD.get(case_id, [])
    if not fqns:
        # Fallback: extract something from the question text
        return json.dumps([f"celery.generated.Symbol_{rng.randint(1, 999)}"])
    return json.dumps(fqns)


# ---------------------------------------------------------------------------
# Client creation
# ---------------------------------------------------------------------------

def create_client(config: LLMConfig = LLMConfig()) -> Any:
    """Create an SDK client for the given config."""
    if config.provider == ModelProvider.MOCK:
        return None  # mock uses no client

    if config.provider == ModelProvider.ANTHROPIC:
        import anthropic
        return anthropic.Anthropic(**config.to_anthropic())

    if config.provider == ModelProvider.OPENAI:
        try:
            import openai
        except ImportError:
            # Fall back to anthropic SDK with OpenAI-compatible base URL
            import anthropic
            return anthropic.Anthropic(**config.to_openai())
        return openai.OpenAI(**config.to_openai())

    raise ValueError(f"Unknown provider: {config.provider}")


# ---------------------------------------------------------------------------
# Text extraction from responses
# ---------------------------------------------------------------------------

def _extract_text(response: Any) -> str:
    """Pull text from an LLM response block."""
    texts: list[str] = []
    for block in response.content:
        if hasattr(block, "text"):
            texts.append(block.text)
        elif hasattr(block, "thinking"):
            texts.append(block.thinking)
        elif hasattr(block, "content"):
            texts.append(str(block.content))
    return "\n".join(texts) if texts else ""


# ---------------------------------------------------------------------------
# Core call_llm
# ---------------------------------------------------------------------------

def call_llm(
    messages: list[dict[str, str]],
    config: LLMConfig = LLMConfig(),
    system: str = "",
) -> str:
    """Call the LLM with a list of messages.

    Args:
        messages: [{"role": "user"|"assistant", "content": "..."}]
        config  : LLMConfig describing provider and model
        system  : System prompt (optional)

    Returns:
        Raw text content from the model.
    """
    if config.provider == ModelProvider.MOCK:
        # Reconstruct user message for mock routing
        user_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content = m["content"]
                break
        # Use a placeholder case_id for mock
        return _mock_response(user_content, case_id="mock")

    client = create_client(config)

    kwargs: dict[str, Any] = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    if config.provider == ModelProvider.ANTHROPIC:
        response = client.messages.create(**kwargs)
        return _extract_text(response)

    if config.provider == ModelProvider.OPENAI:
        # openai SDK uses messages directly
        response = client.chat.completions.create(**kwargs)
        # openai response: response.choices[0].message.content
        return response.choices[0].message.content or ""

    raise ValueError(f"Unknown provider: {config.provider}")


def call_llm_simple(
    user_prompt: str,
    system_prompt: str = "",
    config: LLMConfig = LLMConfig(),
) -> str:
    """Convenience wrapper: single user message."""
    messages = [{"role": "user", "content": user_prompt}]
    return call_llm(messages, config, system=system_prompt)


# ---------------------------------------------------------------------------
# Convenience: named presets
# ---------------------------------------------------------------------------

def minimax_config() -> LLMConfig:
    """MiniMax-M2.7 via Anthropic-compatible API."""
    return load_config_from_toml(section="minimax")


def gpt4o_config() -> LLMConfig:
    """GPT-4o via OpenAI API."""
    return load_config_from_toml(section="gpt4o")


def qwen_config() -> LLMConfig:
    """Qwen3.5-9B via OpenAI-compatible endpoint (vLLM / Qwen-Turbo)."""
    return load_config_from_toml(section="qwen")


def mock_config() -> LLMConfig:
    """Always-works mock config (no API key needed)."""
    return LLMConfig(provider=ModelProvider.MOCK)
