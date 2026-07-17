import json
import logging
import os
import time

from confluent_kafka import Consumer, Producer, KafkaError
from prometheus_client import start_http_server, Counter, Gauge, Histogram

from .llm_client import reason, provider_ready, LLM_PROVIDER, LLM_MODEL
from .schema import AnomalyEvent

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ─── Configuration ──────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")
GROUP_ID     = "llm-reasoner-group-v1"
BATCH_SIZE   = int(os.getenv("CONSUMER_BATCH_SIZE", "50"))

# Provider-aware readiness: key-less providers (ollama) count as configured.
_API_KEY_CONFIGURED = provider_ready()

# ─── Prometheus Metrics ─────────────────────────────────────────────────────────
LLM_REQUESTS   = Counter('llm_requests_total', 'LLM calls attempted', ['provider', 'status'])
LLM_LATENCY    = Histogram(
    'llm_latency_seconds',
    'End-to-end LLM call latency',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    labelnames=['provider'],
)
LLM_CONFIDENCE = Gauge('llm_confidence_score', 'Confidence score from last LLM response')
ANOMALIES_RECEIVED = Counter('llm_anomalies_received_total', 'Anomaly events consumed')

# ─── Kafka Producer ─────────────────────────────────────────────────────────────
producer = Producer({
    'bootstrap.servers': KAFKA_BROKER,
    'queue.buffering.max.messages': 10000,
    'linger.ms': 5,
})

# ─── Kafka Consumer ─────────────────────────────────────────────────────────────
consumer = Consumer({
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': GROUP_ID,
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,
    'max.poll.interval.ms': 600000,   # LLM calls can be slow — allow up to 10 min per batch
    'session.timeout.ms': 30000,
    'heartbeat.interval.ms': 10000,
})
consumer.subscribe(['anomalies.detected'])


def delivery_report(err, msg):
    if err is not None:
        log.error("Failed to deliver to %s: %s", msg.topic(), err)


def process_anomaly(raw: str) -> None:
    """Calls LLM for a single anomaly, validates response, produces to llm.responses."""
    ANOMALIES_RECEIVED.inc()

    try:
        anomaly = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Skipping malformed anomaly JSON")
        return

    # Validate wire format
    try:
        AnomalyEvent.model_validate(anomaly)
    except Exception as e:
        log.warning("Anomaly event failed schema validation: %s", e)
        return

    if not _API_KEY_CONFIGURED:
        log.debug("No LLM API key configured — skipping reasoning for anomaly_id=%s",
                  anomaly.get('anomaly_id'))
        return

    start = time.monotonic()
    try:
        response = reason(anomaly)
        elapsed = time.monotonic() - start

        LLM_REQUESTS.labels(provider=LLM_PROVIDER, status='success').inc()
        LLM_LATENCY.labels(provider=LLM_PROVIDER).observe(elapsed)
        LLM_CONFIDENCE.set(response.confidence)

        log.info(
            "LLM reasoned anomaly_id=%s provider=%s confidence=%.2f latency=%.2fs summary=%r",
            anomaly.get('anomaly_id'), LLM_PROVIDER, response.confidence, elapsed,
            response.summary[:80],
        )

        # Wire format: snake_case, AIRA schema v1
        output = {
            "anomaly_id":   anomaly.get('anomaly_id'),
            "source":       anomaly.get('raw_data', {}).get('source', 'unknown'),
            "timestamp":    anomaly.get('timestamp'),
            "root_causes":  [rc.model_dump() for rc in response.root_causes],
            "actions":      [a.model_dump()  for a  in response.actions],
            "confidence":   response.confidence,
            "summary":      response.summary,
        }
        producer.produce(
            'llm.responses',
            key=anomaly.get('anomaly_id', 'unknown'),
            value=json.dumps(output),
            callback=delivery_report,
        )

    except KeyError as e:
        # Missing API key in env — already logged at startup
        LLM_REQUESTS.labels(provider=LLM_PROVIDER, status='no_key').inc()
        log.error("LLM API key missing: %s", e)
    except Exception as e:
        elapsed = time.monotonic() - start
        LLM_REQUESTS.labels(provider=LLM_PROVIDER, status='error').inc()
        LLM_LATENCY.labels(provider=LLM_PROVIDER).observe(elapsed)
        log.error("LLM call failed for anomaly_id=%s: %s",
                  anomaly.get('anomaly_id'), e)


def start_reasoner() -> None:
    log.info(
        "Starting LLM Reasoner | broker=%s provider=%s model=%s api_key=%s",
        KAFKA_BROKER, LLM_PROVIDER, LLM_MODEL,
        "configured" if _API_KEY_CONFIGURED else "NOT SET — reasoning disabled",
    )
    start_http_server(8082)

    try:
        while True:
            msgs = consumer.consume(num_messages=BATCH_SIZE, timeout=1.0)

            if not msgs:
                producer.poll(0)
                continue

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    log.error("Kafka consumer error: %s", msg.error())
                    continue
                process_anomaly(msg.value().decode('utf-8'))

            consumer.commit(asynchronous=False)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        producer.flush(timeout=5)
        log.info("LLM Reasoner shut down cleanly")
