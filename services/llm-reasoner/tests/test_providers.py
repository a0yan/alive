import sys
import types

from app.providers.openai_compat import OpenAICompatProvider

_VALID = '{"root_causes":[],"actions":[],"confidence":0.6,"summary":"ok"}'


def _fake_openai_module(capture):
    mod = types.ModuleType("openai")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=self._create)
            )

        def _create(self, **kwargs):
            capture["create"] = kwargs
            msg = types.SimpleNamespace(content=_VALID)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    mod.OpenAI = FakeOpenAI
    return mod


def test_openai_passes_base_url_and_key(monkeypatch):
    capture = {}
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_module(capture))
    p = OpenAICompatProvider(model="m", base_url="http://x/v1", api_key="k", json_mode="json_object")
    r = p.reason({"type": "HighLatency"})
    assert capture["init"] == {"api_key": "k", "base_url": "http://x/v1"}
    assert capture["create"]["model"] == "m"
    assert capture["create"]["response_format"] == {"type": "json_object"}
    assert r.confidence == 0.6


def test_openai_omits_response_format_when_no_json_mode(monkeypatch):
    capture = {}
    monkeypatch.setitem(sys.modules, "openai", _fake_openai_module(capture))
    p = OpenAICompatProvider(model="m", base_url="http://x/v1", api_key="k", json_mode=None)
    p.reason({"type": "HighLatency"})
    assert "response_format" not in capture["create"]


from app.providers.anthropic import AnthropicProvider


def _fake_anthropic_module(capture):
    mod = types.ModuleType("anthropic")

    class FakeAnthropic:
        def __init__(self, **kwargs):
            capture["init"] = kwargs
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            capture["create"] = kwargs
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=_VALID)])

    mod.Anthropic = FakeAnthropic
    return mod


def test_anthropic_passes_system(monkeypatch):
    from app.providers.base import SYSTEM_PROMPT
    capture = {}
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic_module(capture))
    p = AnthropicProvider(model="claude", api_key="ak")
    r = p.reason({"type": "HighLatency"})
    assert capture["init"] == {"api_key": "ak"}
    assert capture["create"]["system"] == SYSTEM_PROMPT
    assert capture["create"]["model"] == "claude"
    assert r.confidence == 0.6
