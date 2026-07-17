import pytest

from app.providers.base import LLMProvider

_VALID = '{"root_causes":[],"actions":[],"confidence":0.5,"summary":"ok"}'


class _FakeProvider(LLMProvider):
    """Returns canned outputs in order; records each call's messages."""
    def __init__(self, outputs):
        super().__init__(model="fake")
        self._outputs = list(outputs)
        self.calls = []

    def _complete(self, system, messages):
        self.calls.append(messages)
        return self._outputs.pop(0)


def test_retry_recovers_from_bad_first_output():
    p = _FakeProvider(["garbage", _VALID])
    r = p.reason({"type": "HighLatency"})
    assert r.confidence == 0.5
    assert len(p.calls) == 2
    assert "previous reply was NOT valid JSON" in p.calls[1][0]["content"]


def test_no_retry_when_first_output_valid():
    p = _FakeProvider([_VALID])
    r = p.reason({"type": "HighLatency"})
    assert r.confidence == 0.5
    assert len(p.calls) == 1


def test_raises_when_both_outputs_bad():
    p = _FakeProvider(["garbage", "still garbage"])
    with pytest.raises((ValueError, Exception)):
        p.reason({"type": "HighLatency"})
