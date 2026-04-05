"""
Rule engine unit tests — AIRA anomaly consumer.
All tests run against process_event() with a mocked Kafka producer.
No broker required.
"""
import json
import sys
from unittest.mock import MagicMock, patch, call

# ─── Mock heavy dependencies before any app import ────────────────────────────
sys.modules.setdefault('confluent_kafka', MagicMock())
sys.modules.setdefault('prometheus_client', MagicMock())

from app.consumer import process_event  # noqa: E402  (must come after mocks)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _metric_event(latency: float, source: str = "test-service") -> str:
    return json.dumps({
        "event_id": "evt-001",
        "source": source,
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": latency},
    })


def _log_event(level: str) -> str:
    return json.dumps({
        "event_id": "evt-002",
        "source": "auth-service",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "log",
        "payload": {"level": level, "message": "something happened"},
    })


def _produced_topics(mock_producer) -> list[str]:
    """Return list of Kafka topics that produce() was called with."""
    return [c.kwargs.get('topic') or c.args[0]
            for c in mock_producer.produce.call_args_list]


def _produced_anomaly_types(mock_producer) -> list[str]:
    """Parse each anomalies.detected message and return their type fields."""
    types = []
    for c in mock_producer.produce.call_args_list:
        topic = c.kwargs.get('topic') or c.args[0]
        if topic == 'anomalies.detected':
            value = c.kwargs.get('value') or c.args[1]
            types.append(json.loads(value)['type'])
    return types


# ─── Latency rule tests ────────────────────────────────────────────────────────

def test_latency_below_threshold_no_anomaly():
    """0.3s latency — well below 2.0s threshold — must not emit an anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_metric_event(0.3))
        anomaly_calls = [c for c in mock_producer.produce.call_args_list
                         if (c.kwargs.get('topic') or c.args[0]) == 'anomalies.detected']
        assert anomaly_calls == []


def test_latency_at_threshold_no_anomaly():
    """Exactly at threshold (2.0s) must not trigger — rule is strictly greater than."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_metric_event(2.0))
        anomaly_calls = [c for c in mock_producer.produce.call_args_list
                         if (c.kwargs.get('topic') or c.args[0]) == 'anomalies.detected']
        assert anomaly_calls == []


def test_latency_above_threshold_emits_high_latency():
    """2.5s latency > 2.0s threshold must emit a HighLatency anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_metric_event(2.5))
        types = _produced_anomaly_types(mock_producer)
        assert "HighLatency" in types


def test_high_latency_anomaly_id_format():
    """Emitted anomaly_id must follow the anom-<event_id> pattern."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_metric_event(3.0))
        for c in mock_producer.produce.call_args_list:
            topic = c.kwargs.get('topic') or c.args[0]
            if topic == 'anomalies.detected':
                payload = json.loads(c.kwargs.get('value') or c.args[1])
                assert payload['anomaly_id'] == 'anom-evt-001'


# ─── Log rule tests ────────────────────────────────────────────────────────────

def test_error_log_emits_anomaly():
    """type=log with level=ERROR must emit an ErrorLog anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_log_event("ERROR"))
        types = _produced_anomaly_types(mock_producer)
        assert "ErrorLog" in types


def test_info_log_no_anomaly():
    """type=log with level=INFO must not emit any anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_log_event("INFO"))
        anomaly_calls = [c for c in mock_producer.produce.call_args_list
                         if (c.kwargs.get('topic') or c.args[0]) == 'anomalies.detected']
        assert anomaly_calls == []


def test_warn_log_no_anomaly():
    """type=log with level=WARN must not emit any anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event(_log_event("WARN"))
        anomaly_calls = [c for c in mock_producer.produce.call_args_list
                         if (c.kwargs.get('topic') or c.args[0]) == 'anomalies.detected']
        assert anomaly_calls == []


# ─── Resilience tests ─────────────────────────────────────────────────────────

def test_malformed_json_no_crash():
    """Malformed JSON must not raise — routes to DLQ instead."""
    with patch('app.consumer.producer') as mock_producer:
        process_event("{not valid json{{")   # must not raise
        topics = _produced_topics(mock_producer)
        assert 'ingestion.events.dlq' in topics


def test_malformed_json_does_not_produce_anomaly():
    """Malformed JSON must not produce a false anomaly."""
    with patch('app.consumer.producer') as mock_producer:
        process_event("{bad}")
        assert 'anomalies.detected' not in _produced_topics(mock_producer)


def test_non_numeric_latency_no_crash():
    """String latency value must log a warning and return — no crash, no anomaly."""
    event = json.dumps({
        "event_id": "evt-003",
        "source": "svc",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        "payload": {"name": "latency", "value": "bad"},
    })
    with patch('app.consumer.producer') as mock_producer:
        process_event(event)   # must not raise
        assert 'anomalies.detected' not in _produced_topics(mock_producer)


def test_missing_payload_no_crash():
    """Event with no payload key must not crash — treats payload as {}."""
    event = json.dumps({
        "event_id": "evt-004",
        "source": "svc",
        "timestamp": "2024-01-01T00:00:00Z",
        "type": "metric",
        # payload key intentionally absent
    })
    with patch('app.consumer.producer') as mock_producer:
        process_event(event)   # must not raise
        assert 'anomalies.detected' not in _produced_topics(mock_producer)


def test_empty_string_no_crash():
    """Empty input must not crash — routes to DLQ."""
    with patch('app.consumer.producer') as mock_producer:
        process_event("")   # must not raise
        assert 'ingestion.events.dlq' in _produced_topics(mock_producer)
