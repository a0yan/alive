import json
import logging
import os
import threading
import time
from confluent_kafka import Consumer, Producer, KafkaError, TopicPartition
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ─── OpenTelemetry Setup ───────────────────────────────────────────────────────
_otel_endpoint = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://jaeger:4317')
_provider = TracerProvider()
_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=_otel_endpoint))
)
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("anomaly-detector")
_propagator = TraceContextTextMapPropagator()

# ─── Configuration ─────────────────────────────────────────────────────────────
KAFKA_BROKER      = os.getenv("KAFKA_BROKER", "kafka:29092")
LATENCY_THRESHOLD = float(os.getenv("LATENCY_THRESHOLD", "2.0"))
DETECTION_MODE    = os.getenv("DETECTION_MODE", "rule-only")   # rule-only | ml-only | hybrid
MODEL_PATH        = os.getenv("MODEL_PATH", "/app/models/isolation_forest.pkl")
GROUP_ID          = "anomaly-detector-group-v1"
BATCH_SIZE        = int(os.getenv("CONSUMER_BATCH_SIZE", "500"))   # messages per poll

# ─── Prometheus Metrics ────────────────────────────────────────────────────────
ANOMALY_COUNTER   = Counter('anomalies_detected_total', 'Total anomalies detected', ['type'])
EVENTS_PROCESSED  = Counter('events_processed_total', 'Total events processed')
DLQ_COUNTER       = Counter('events_dlq_total', 'Events routed to dead-letter queue', ['reason'])
DETECTION_MODE_INFO = Gauge('detection_mode_info', 'Current detection mode', ['mode'])
DETECTION_MODE_INFO.labels(mode=DETECTION_MODE).set(1)

# Histogram lets Grafana show p50/p95/p99 processing latency — far more useful than a counter
PROCESSING_LATENCY = Histogram(
    'event_processing_duration_seconds',
    'Time to process a single event through the rules engine',
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
)

# Consumer lag — updated every 30s by background thread; key operational metric for load tests
CONSUMER_LAG = Gauge(
    'kafka_consumer_lag_total',
    'Total consumer lag across all partitions of ingestion.events',
)

# ─── Kafka Producer ────────────────────────────────────────────────────────────
producer = Producer({
    'bootstrap.servers': KAFKA_BROKER,
    # Buffer up to 10k anomaly messages in memory before sending — anomalies are rare,
    # so this is mainly to prevent blocking on the hot consumer path
    'queue.buffering.max.messages': 10000,
    'queue.buffering.max.kbytes': 16384,
    'batch.num.messages': 100,
    'linger.ms': 5,
})

# ─── Kafka Consumer ────────────────────────────────────────────────────────────
consumer = Consumer({
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': GROUP_ID,
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,          # Manual batch commit for durability
    # Fetch at least 64 KB before returning (reduces round-trips at high throughput)
    'fetch.min.bytes': 65536,
    # But don't wait more than 500ms if there's less data — keeps latency bounded
    'fetch.max.wait.ms': 500,
    # 4 MB per partition per fetch — headroom for burst traffic
    'max.partition.fetch.bytes': 4194304,
    # Must process BATCH_SIZE messages and commit within this window
    'max.poll.interval.ms': 300000,
    'session.timeout.ms': 30000,
    'heartbeat.interval.ms': 10000,
})
consumer.subscribe(['ingestion.events'])

# ─── ML Model (lazy-loaded on first use) ──────────────────────────────────────
_model = None


def get_model():
    """Loads the Isolation Forest model once; returns None if unavailable."""
    global _model
    if _model is not None:
        return _model
    try:
        import joblib
        _model = joblib.load(MODEL_PATH)
        log.info("Loaded ML model from %s", MODEL_PATH)
    except FileNotFoundError:
        log.warning("ML model not found at %s — ML detection disabled", MODEL_PATH)
    except Exception as e:
        log.error("Failed to load ML model: %s", e)
    return _model


# ─── Delivery Callback ─────────────────────────────────────────────────────────
def delivery_report(err, msg):
    if err is not None:
        log.error("Failed to deliver message to %s: %s", msg.topic(), err)


# ─── Rules Engine ──────────────────────────────────────────────────────────────
def process_event(event_json: str) -> None:
    """Evaluates a single event against all active detection rules."""
    start = time.monotonic()

    try:
        event = json.loads(event_json)
        payload = event.get('payload', {})
        event_id = event.get('event_id', 'unknown')
        EVENTS_PROCESSED.inc()

        # ── RULE 1: High Latency (rule-only and hybrid) ──────────────────────
        if event.get('type') == 'metric' and payload.get('name') == 'latency':
            try:
                val = float(payload.get('value', 0))
            except (TypeError, ValueError):
                log.warning("Non-numeric latency in event_id=%s", event_id)
                return

            if DETECTION_MODE in ('rule-only', 'hybrid') and val > LATENCY_THRESHOLD:
                _emit_and_count(event, "HighLatency",
                                f"Latency {val:.2f}s > threshold {LATENCY_THRESHOLD}s")

            # ── ML: Isolation Forest (ml-only and hybrid) ───────────────────
            if DETECTION_MODE in ('ml-only', 'hybrid'):
                metadata_size = len(json.dumps(payload.get('metadata', {})))
                model = get_model()
                if model is not None:
                    pred = model.predict([[val, metadata_size]])
                    if pred[0] == -1:   # -1 = anomaly per sklearn IsolationForest
                        # Only emit if rule didn't already (avoids duplicate anomalies in hybrid)
                        if not (DETECTION_MODE == 'hybrid' and val > LATENCY_THRESHOLD):
                            _emit_and_count(event, "MLAnomaly",
                                            f"Isolation Forest flagged latency={val:.3f}s "
                                            f"metadata_size={metadata_size}B")

        # ── RULE 2: Error Logs ───────────────────────────────────────────────
        if event.get('type') == 'log' and payload.get('level') == 'ERROR':
            _emit_and_count(event, "ErrorLog", "Error log level detected")

    except json.JSONDecodeError:
        log.warning("Skipping malformed JSON — routing to DLQ")
        _send_to_dlq(event_json, reason="malformed_json")
    except Exception as e:
        log.error("Unexpected error processing event: %s", e)
        _send_to_dlq(event_json, reason="processing_error")
    finally:
        PROCESSING_LATENCY.observe(time.monotonic() - start)


def _emit_and_count(original_event: dict, anomaly_type: str, description: str) -> None:
    ANOMALY_COUNTER.labels(type=anomaly_type).inc()
    log.info("ANOMALY type=%s event_id=%s desc=%s",
             anomaly_type, original_event.get('event_id'), description)
    emit_anomaly(original_event, anomaly_type, description)


def emit_anomaly(original_event: dict, anomaly_type: str, description: str) -> None:
    """Publishes an anomaly event to anomalies.detected — fire and forget."""
    event_id = original_event.get('event_id')
    anomaly_event = {
        "anomaly_id": f"anom-{event_id}",
        "source_event_id": event_id,
        "source": original_event.get('source', 'unknown'),
        "timestamp": original_event.get('timestamp'),
        "type": anomaly_type,
        "description": description,
        "raw_data": original_event,
    }
    producer.produce(
        'anomalies.detected',
        key=original_event.get('source', 'unknown'),
        value=json.dumps(anomaly_event),
        callback=delivery_report,
    )
    # No flush() here — batched for throughput; final flush in shutdown


def _send_to_dlq(event_json: str, reason: str) -> None:
    """Routes unprocessable events to a dead-letter queue for inspection/replay."""
    DLQ_COUNTER.labels(reason=reason).inc()
    try:
        producer.produce(
            'ingestion.events.dlq',
            value=event_json,
            callback=delivery_report,
        )
    except Exception as e:
        log.error("Failed to send to DLQ: %s", e)


# ─── Consumer Lag Poller ───────────────────────────────────────────────────────
def _poll_consumer_lag() -> None:
    """Background thread: updates CONSUMER_LAG gauge every 30s via watermark offsets."""
    lag_consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': GROUP_ID,
        'enable.auto.commit': False,
    })
    while True:
        try:
            metadata = lag_consumer.list_topics('ingestion.events', timeout=5)
            partitions = [
                TopicPartition('ingestion.events', p)
                for p in metadata.topics.get('ingestion.events', type('', (), {'partitions': {}})()).partitions
            ]
            if partitions:
                committed = lag_consumer.committed(partitions, timeout=5)
                total_lag = 0
                for tp in committed:
                    lo, hi = lag_consumer.get_watermark_offsets(tp, timeout=3)
                    offset = tp.offset if tp.offset >= 0 else lo
                    total_lag += max(0, hi - offset)
                CONSUMER_LAG.set(total_lag)
        except Exception as exc:
            log.debug("Lag poll error (non-fatal): %s", exc)
        time.sleep(30)


# ─── Main Consumer Loop ────────────────────────────────────────────────────────
def start_consumer() -> None:
    log.info("Starting Anomaly Consumer | broker=%s mode=%s threshold=%.1f batch=%d",
             KAFKA_BROKER, DETECTION_MODE, LATENCY_THRESHOLD, BATCH_SIZE)
    start_http_server(8001)

    lag_thread = threading.Thread(target=_poll_consumer_lag, daemon=True)
    lag_thread.start()

    try:
        while True:
            # Batch poll: fetch up to BATCH_SIZE messages in one call.
            # One commit per batch instead of one commit per message —
            # at 50k events/sec this cuts Kafka coordinator load by ~500x.
            msgs = consumer.consume(num_messages=BATCH_SIZE, timeout=1.0)

            if not msgs:
                producer.poll(0)   # trigger delivery callbacks even when idle
                continue

            for msg in msgs:
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    log.error("Kafka consumer error: %s", msg.error())
                    continue
                # Extract W3C trace context from Kafka headers so this span
                # links back to the ingestion span produced by the Java OTel agent.
                headers = dict(msg.headers() or [])
                carrier = {
                    k: v.decode() if isinstance(v, bytes) else v
                    for k, v in headers.items()
                }
                ctx = _propagator.extract(carrier)
                with tracer.start_as_current_span(
                    "anomaly_detector.process_event",
                    context=ctx,
                    kind=trace.SpanKind.CONSUMER,
                ):
                    process_event(msg.value().decode('utf-8'))

            # Single commit covers the entire batch — at-least-once semantics
            consumer.commit(asynchronous=False)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        producer.flush(timeout=5)
        log.info("Consumer shut down cleanly")
