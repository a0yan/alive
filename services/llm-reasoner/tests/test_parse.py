import pytest
from pydantic import ValidationError

from app.providers.base import parse_response

_VALID = (
    '{"root_causes":[{"label":"db","reason":"slow"}],'
    '"actions":[{"action":"scale_up","target":{"kind":"Deployment","name":"db"}}],'
    '"confidence":0.7,"summary":"ok"}'
)


def test_parses_clean_json():
    r = parse_response(_VALID)
    assert r.confidence == 0.7
    assert r.summary == "ok"


def test_strips_json_fence():
    r = parse_response("```json\n" + _VALID + "\n```")
    assert r.confidence == 0.7


def test_strips_bare_fence():
    r = parse_response("```\n" + _VALID + "\n```")
    assert r.confidence == 0.7


def test_rejects_bad_json():
    with pytest.raises((ValidationError, ValueError)):
        parse_response("not json at all")


def test_rejects_schema_violation():
    with pytest.raises(ValidationError):
        parse_response('{"root_causes":[],"actions":[],"confidence":1.5,"summary":"x"}')
