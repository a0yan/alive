"""
Schema contract tests — AIRA Schema v1.
Guards against eventId/event_id field name regressions.
"""
import json
from unittest.mock import MagicMock, patch

# Patch out Kafka + Prometheus before importing the module
import sys
sys.modules.setdefault('confluent_kafka', MagicMock())
sys.modules.setdefault('prometheus_client', MagicMock())

with patch('prometheus_client.Counter', MagicMock(return_value=MagicMock())), \
     patch('prometheus_client.Gauge',   MagicMock(return_value=MagicMock())), \
     patch('prometheus_client.Histogram', MagicMock(return_value=MagicMock())):
    from app.consumer import emit_anomaly


def _capture_anomaly(event: dict) -> dict:
    """Runs emit_anomaly and returns the anomaly payload that would be produced."""
    captured = {}

    def fake_produce(topic, key=None, value=None, callback=None):
        captured['topic'] = topic
        captured['payload'] = json.loads(value)

    with patch('app.consumer.producer') as mock_producer:
        mock_producer.produce.side_effect = fake_produce
        emit_anomaly(event, "HighLatency", "test description")

    return captured['payload']


def test_snake_case_event_id_produces_correct_anomaly_id():
    """Event with snake_case event_id (AIRA Schema v1) must produce anom-<uuid>."""
    event = {
        "event_id": "abc-123",
        "source": "payment-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": 3.0},
    }
    anomaly = _capture_anomaly(event)
    assert anomaly["anomaly_id"] == "anom-abc-123"
    assert anomaly["source_event_id"] == "abc-123"


def test_missing_event_id_produces_anom_none():
    """
    Documents the pre-fix behavior: missing event_id → anomaly_id = 'anom-None'.
    This test exists to catch any regression that silently loses the event_id.
    """
    event = {
        "source": "orders-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": 3.0},
        # event_id intentionally absent
    }
    anomaly = _capture_anomaly(event)
    assert anomaly["anomaly_id"] == "anom-None"


def test_anomaly_contains_original_event_as_raw_data():
    """raw_data must be the full original event — needed by downstream LLM reasoner."""
    event = {
        "event_id": "xyz-789",
        "source": "checkout-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "log",
        "payload": {"level": "ERROR", "message": "connection refused"},
    }
    anomaly = _capture_anomaly(event)
    assert anomaly["raw_data"] == event


def test_anomaly_type_and_description_propagated():
    event = {
        "event_id": "evt-001",
        "source": "auth-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": 5.0},
    }
    anomaly = _capture_anomaly(event)
    assert anomaly["type"] == "HighLatency"
    assert "test description" in anomaly["description"]


def test_anomaly_topic_is_anomalies_detected():
    """Anomalies must be produced to the correct Kafka topic."""
    event = {
        "event_id": "evt-002",
        "source": "payment-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": 3.0},
    }
    captured = {}

    def fake_produce(topic, key=None, value=None, callback=None):
        captured['topic'] = topic

    with patch('app.consumer.producer') as mock_producer:
        mock_producer.produce.side_effect = fake_produce
        emit_anomaly(event, "HighLatency", "desc")

    assert captured['topic'] == 'anomalies.detected'
