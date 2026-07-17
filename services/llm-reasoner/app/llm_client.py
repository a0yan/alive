"""
Provider-agnostic LLM client.
Maps LLM_PROVIDER to a concrete provider via REGISTRY, with env overrides for
model (LLM_MODEL) and base URL (LLM_BASE_URL). Public API: reason(anomaly).
"""
import logging
import os
from dataclasses import dataclass
from functools import lru_cache

from .providers.base import LLMProvider
from .providers.openai_compat import OpenAICompatProvider
from .providers.anthropic import AnthropicProvider
from .schema import LLMResponse

log = logging.getLogger(__name__)

# Kept importable for consumer.py logging/metric labels (unchanged behaviour).
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


@dataclass(frozen=True)
class ProviderSpec:
    adapter: type[LLMProvider]
    base_url: str | None       # None for native SDK (anthropic)
    key_env: str | None        # None for key-less (ollama)
    default_model: str
    json_mode: str | None      # "json_object" where supported, else None


REGISTRY: dict[str, ProviderSpec] = {
    "openai":      ProviderSpec(OpenAICompatProvider, "https://api.openai.com/v1",            "OPENAI_API_KEY",    "gpt-4o-mini",                      "json_object"),
    "groq":        ProviderSpec(OpenAICompatProvider, "https://api.groq.com/openai/v1",       "GROQ_API_KEY",      "llama-3.1-8b-instant",             "json_object"),
    "together":    ProviderSpec(OpenAICompatProvider, "https://api.together.xyz/v1",          "TOGETHER_API_KEY",  "meta-llama/Llama-3-8b-chat-hf",    None),
    "ollama":      ProviderSpec(OpenAICompatProvider, "http://host.docker.internal:11434/v1", None,                "mistral",                          None),
    "huggingface": ProviderSpec(OpenAICompatProvider, "https://router.huggingface.co/v1",     "HF_TOKEN",          "meta-llama/Llama-3.1-8B-Instruct", None),
    "anthropic":   ProviderSpec(AnthropicProvider,    None,                                   "ANTHROPIC_API_KEY", "claude-haiku-4-5-20251001",        None),
}


def _build_provider(name: str) -> LLMProvider:
    if name not in REGISTRY:
        raise ValueError(f"Unknown LLM_PROVIDER {name!r}. Valid: {', '.join(REGISTRY)}")
    spec = REGISTRY[name]
    model = os.getenv("LLM_MODEL") or spec.default_model
    base_url = os.getenv("LLM_BASE_URL") or spec.base_url

    if spec.key_env:
        api_key = os.environ[spec.key_env]   # KeyError if unset → consumer counts no_key
        if not api_key:
            raise KeyError(spec.key_env)
    else:
        api_key = "ollama"                   # placeholder; openai SDK needs non-empty key

    if spec.adapter is AnthropicProvider:
        return AnthropicProvider(model=model, api_key=api_key)
    return OpenAICompatProvider(
        model=model, base_url=base_url, api_key=api_key, json_mode=spec.json_mode
    )


def provider_ready() -> bool:
    """True when the configured provider can be built: known name, and either
    key-less (ollama) or its API key env var is set and non-empty."""
    name = os.getenv("LLM_PROVIDER", "openai")
    spec = REGISTRY.get(name)
    if spec is None:
        return False
    return spec.key_env is None or bool(os.getenv(spec.key_env))


@lru_cache(maxsize=1)
def get_provider() -> LLMProvider:
    name = os.getenv("LLM_PROVIDER", "openai")
    provider = _build_provider(name)
    log.info("LLM provider initialised: %s (model=%s)", name, provider.model)
    return provider


def reason(anomaly: dict) -> LLMResponse:
    """Route to the configured provider and return a validated LLMResponse."""
    return get_provider().reason(anomaly)
