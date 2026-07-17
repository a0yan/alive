"""
Unit tests for consumer.process_anomaly — Kafka and Prometheus are faked so
these run without infrastructure.
"""
import json
import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault('confluent_kafka', MagicMock())
sys.modules.setdefault('prometheus_client', MagicMock())

from app.consumer import process_anomaly  # noqa: E402
import app.consumer as consumer_mod  # noqa: E402
from app.schema import LLMResponse  # noqa: E402

_ANOMALY = {
    "anomaly_id": "anom-1",
    "source_event_id": "evt-1",
    "source": "orders-service",
    "timestamp": "2026-01-01T00:00:00Z",
    "type": "HighLatency",
    "description": "latency 3.2s above threshold",
    "raw_data": {"source": "orders-service", "payload": {"name": "latency", "value": 3.2}},
}

_RESPONSE = LLMResponse(
    root_causes=[{"label": "db", "reason": "slow query"}],
    actions=[{"action": "scale_up", "target": {"kind": "Deployment", "name": "db"}}],
    confidence=0.9,
    summary="db overloaded",
)


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(consumer_mod, "_API_KEY_CONFIGURED", True)


def test_malformed_json_skipped(monkeypatch, ready):
    called = MagicMock()
    monkeypatch.setattr(consumer_mod, "reason", called)
    process_anomaly("{not json")
    called.assert_not_called()


def test_schema_violation_skipped(monkeypatch, ready):
    called = MagicMock()
    monkeypatch.setattr(consumer_mod, "reason", called)
    process_anomaly(json.dumps({"anomaly_id": "x"}))  # missing required fields
    called.assert_not_called()


def test_no_provider_configured_skips_reasoning(monkeypatch):
    monkeypatch.setattr(consumer_mod, "_API_KEY_CONFIGURED", False)
    called = MagicMock()
    monkeypatch.setattr(consumer_mod, "reason", called)
    process_anomaly(json.dumps(_ANOMALY))
    called.assert_not_called()


def test_success_produces_llm_response(monkeypatch, ready):
    monkeypatch.setattr(consumer_mod, "reason", lambda a: _RESPONSE)
    fake_producer = MagicMock()
    monkeypatch.setattr(consumer_mod, "producer", fake_producer)

    process_anomaly(json.dumps(_ANOMALY))

    fake_producer.produce.assert_called_once()
    args, kwargs = fake_producer.produce.call_args
    assert args[0] == "llm.responses"
    out = json.loads(kwargs["value"])
    assert out["anomaly_id"] == "anom-1"
    assert out["source"] == "orders-service"
    assert out["confidence"] == 0.9
    assert out["root_causes"][0]["label"] == "db"
    assert out["actions"][0]["target"]["name"] == "db"


def test_missing_key_counted_not_raised(monkeypatch, ready):
    def boom(a):
        raise KeyError("OPENAI_API_KEY")
    monkeypatch.setattr(consumer_mod, "reason", boom)
    fake_producer = MagicMock()
    monkeypatch.setattr(consumer_mod, "producer", fake_producer)
    process_anomaly(json.dumps(_ANOMALY))  # must not raise
    fake_producer.produce.assert_not_called()


def test_llm_error_counted_not_raised(monkeypatch, ready):
    def boom(a):
        raise RuntimeError("provider down")
    monkeypatch.setattr(consumer_mod, "reason", boom)
    fake_producer = MagicMock()
    monkeypatch.setattr(consumer_mod, "producer", fake_producer)
    process_anomaly(json.dumps(_ANOMALY))  # must not raise
    fake_producer.produce.assert_not_called()
