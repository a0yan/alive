import pytest

from app.providers.openai_compat import OpenAICompatProvider
from app.providers.anthropic import AnthropicProvider


@pytest.fixture
def client():
    import app.llm_client as c
    c.get_provider.cache_clear()
    yield c
    c.get_provider.cache_clear()


def test_openai_resolves(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    p = client.get_provider()
    assert isinstance(p, OpenAICompatProvider)
    assert p.base_url == "https://api.openai.com/v1"
    assert p.model == "gpt-4o-mini"
    assert p.json_mode == "json_object"


def test_anthropic_resolves(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    p = client.get_provider()
    assert isinstance(p, AnthropicProvider)
    assert p.model == "claude-haiku-4-5-20251001"


def test_base_url_override(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:9999/v1")
    p = client.get_provider()
    assert p.base_url == "http://localhost:9999/v1"


def test_model_override(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    p = client.get_provider()
    assert p.model == "gpt-4o"


def test_unknown_provider_raises(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        client.get_provider()


def test_ollama_needs_no_key(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    p = client.get_provider()
    assert p.api_key == "ollama"
    assert p.base_url == "http://host.docker.internal:11434/v1"
    assert p.model == "mistral"
    assert p.json_mode is None


def test_missing_key_raises(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(KeyError):
        client.get_provider()
