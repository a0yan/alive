"""
AIRA end-to-end integration smoke test.

Verifies the full pipeline: POST event → Kafka ingestion.events →
anomaly detector → Kafka anomalies.detected.

Usage:
    python tooling/integration_test.py [--api http://localhost:8080] [--broker localhost:9092]

Exit 0 = pass, 1 = fail.
"""
import argparse
import json
import sys
import time
import uuid
import requests
from confluent_kafka import Consumer, KafkaError


TIMEOUT_SECONDS = 30
TOPIC = "anomalies.detected"


def post_event(api_url: str, event: dict) -> str:
    """POST event to ingestion API. Returns event_id from response."""
    resp = requests.post(
        f"{api_url}/v1/events",
        json=event,
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    assert data.get("status") == "accepted", f"Unexpected status: {data}"
    return data["event_id"]


def wait_for_anomaly(broker: str, event_id: str, timeout: int) -> dict:
    """Poll anomalies.detected until an anomaly for event_id arrives or timeout."""
    consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": f"integration-test-{uuid.uuid4()}",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([TOPIC])

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise RuntimeError(f"Kafka error: {msg.error()}")
            anomaly = json.loads(msg.value().decode())
            if anomaly.get("source_event_id") == event_id:
                return anomaly
    finally:
        consumer.close()

    raise TimeoutError(
        f"No anomaly for event_id={event_id} seen within {timeout}s"
    )


def assert_anomaly_schema(anomaly: dict, expected_type: str) -> None:
    """Validate anomaly matches AIRA schema v1."""
    required = ["anomaly_id", "source_event_id", "timestamp", "type", "description", "raw_data"]
    missing = [f for f in required if f not in anomaly]
    assert not missing, f"Missing fields in anomaly: {missing}"
    assert anomaly["anomaly_id"].startswith("anom-"), \
        f"anomaly_id should start with 'anom-', got: {anomaly['anomaly_id']}"
    assert anomaly["type"] == expected_type, \
        f"Expected type={expected_type}, got={anomaly['type']}"
    assert isinstance(anomaly["raw_data"], dict), "raw_data must be a dict"
    print(f"  ✓ Schema valid — anomaly_id={anomaly['anomaly_id']} type={anomaly['type']}")


def run_test(name: str, fn):
    print(f"\n[TEST] {name}")
    try:
        fn()
        print(f"  ✓ PASS")
        return True
    except Exception as exc:
        print(f"  ✗ FAIL: {exc}", file=sys.stderr)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AIRA integration smoke test")
    parser.add_argument("--api",     default="http://localhost:8080", help="Ingestion API base URL")
    parser.add_argument("--broker",  default="localhost:9092",        help="Kafka broker address")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_SECONDS)
    args = parser.parse_args()

    print(f"AIRA Integration Test")
    print(f"  API:    {args.api}")
    print(f"  Broker: {args.broker}")
    print(f"  Timeout per test: {args.timeout}s")

    results = []

    # ── Test 1: High-latency metric triggers HighLatency anomaly ──────────────
    def test_high_latency():
        event_id = post_event(args.api, {
            "source": "integration-test-service",
            "type": "metric",
            "payload": {
                "name": "latency",
                "value": 4.5,
                "metadata": {"test": "high_latency"},
            },
        })
        print(f"  Posted event_id={event_id}")
        anomaly = wait_for_anomaly(args.broker, event_id, args.timeout)
        assert_anomaly_schema(anomaly, "HighLatency")
        assert float(anomaly["raw_data"]["payload"]["value"]) > 2.0, \
            "raw_data should contain original latency value"

    results.append(run_test("High-latency metric → HighLatency anomaly", test_high_latency))

    # ── Test 2: ERROR log triggers ErrorLog anomaly ────────────────────────────
    def test_error_log():
        event_id = post_event(args.api, {
            "source": "integration-test-service",
            "type": "log",
            "payload": {
                "level": "ERROR",
                "message": "Integration test: upstream timeout",
                "metadata": {"test": "error_log"},
            },
        })
        print(f"  Posted event_id={event_id}")
        anomaly = wait_for_anomaly(args.broker, event_id, args.timeout)
        assert_anomaly_schema(anomaly, "ErrorLog")

    results.append(run_test("ERROR log → ErrorLog anomaly", test_error_log))

    # ── Test 3: Normal event does NOT trigger anomaly ─────────────────────────
    def test_no_anomaly_for_normal():
        test_id = str(uuid.uuid4())
        # Send a normal-latency event
        event_id = post_event(args.api, {
            "source": "integration-test-normal",
            "type": "metric",
            "payload": {
                "name": "latency",
                "value": 0.1,
                "metadata": {"test": test_id},
            },
        })
        print(f"  Posted event_id={event_id}")
        # Poll briefly; verify no anomaly with this event_id
        consumer = Consumer({
            "bootstrap.servers": args.broker,
            "group.id": f"integration-no-anomaly-{uuid.uuid4()}",
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        })
        consumer.subscribe([TOPIC])
        deadline = time.monotonic() + 5  # 5s is enough — anomaly would arrive in <2s
        found = False
        try:
            while time.monotonic() < deadline:
                msg = consumer.poll(0.5)
                if msg and not msg.error():
                    anomaly = json.loads(msg.value().decode())
                    if anomaly.get("source_event_id") == event_id:
                        found = True
                        break
        finally:
            consumer.close()
        assert not found, f"Normal event {event_id} unexpectedly triggered anomaly"
        print(f"  ✓ No anomaly produced for normal-latency event")

    results.append(run_test("Normal-latency metric → no anomaly", test_no_anomaly_for_normal))

    # ── Test 4: Malformed event → 400 from ingestion API ─────────────────────
    def test_invalid_event():
        resp = requests.post(
            f"{args.api}/v1/events",
            json={"type": "metric"},  # missing required 'source'
            timeout=5,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        print(f"  ✓ Ingestion returned 400 for missing 'source'")

    results.append(run_test("Missing 'source' → 400 from ingestion", test_invalid_event))

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{total} passed")

    if passed == total:
        print("✓ All integration tests passed")
        sys.exit(0)
    else:
        print(f"✗ {total - passed} test(s) failed", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
