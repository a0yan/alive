import json
import os
import sys
from confluent_kafka import Consumer, Producer, KafkaError
from prometheus_client import start_http_server, Counter

# Configuration
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
GROUP_ID = "anomaly-detector-group-v1"
ANOMALY_COUNTER = Counter('anomalies_detected_total', 'Total anomalies detected', ['type'])
EVENTS_PROCESSED = Counter('events_processed_total', 'Total events processed')

# 1. Setup Producer (to report anomalies)
producer_conf = {'bootstrap.servers': KAFKA_BROKER}
producer = Producer(producer_conf)

# 2. Setup Consumer (to read events)
consumer_conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': GROUP_ID,
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False  # We commit manually for safety
}
consumer = Consumer(consumer_conf)
consumer.subscribe(['ingestion.events'])

def process_event(event_json):
    """
    The Core Logic: Rules Engine
    """
    try:
        event = json.loads(event_json)
        payload = event.get('payload', {})
        EVENTS_PROCESSED.inc() 
        
        # --- RULE 1: High Latency Detection ---
        # If it's a metric and value > 2.0 (seconds)
        if event.get('type') == 'metric' and payload.get('name') == 'latency':
            val = float(payload.get('value', 0))
            if val > 2.0:
                ANOMALY_COUNTER.labels(type='HighLatency').inc() # Increment anomaly
                print(f"🚨 ANOMALY DETECTED: Latency {val}s is too high!", flush=True)
                emit_anomaly(event, "HighLatency", f"Latency value {val}s > 2.0s")

        # --- RULE 2: Error Logs ---
        if event.get('type') == 'log' and payload.get('level') == 'ERROR':
             print(f"🚨 ANOMALY DETECTED: Error Log found!", flush=True)
             emit_anomaly(event, "ErrorLog", "Error log level detected")

    except json.JSONDecodeError:
        print("Skipping malformed JSON", file=sys.stderr)
    except Exception as e:
        print(f"Error processing event: {e}", file=sys.stderr)

def emit_anomaly(original_event, anomaly_type, description):
    """
    Publishes an anomaly event to the 'anomalies.detected' topic
    """
    anomaly_event = {
        "anomaly_id": f"anom-{original_event.get('event_id', original_event.get('eventId'))}",
        "source_event_id": original_event.get('event_id', original_event.get('eventId')),
        "timestamp": original_event['timestamp'],
        "type": anomaly_type,
        "description": description,
        "raw_data": original_event
    }
    
    producer.produce(
        'anomalies.detected',
        key=original_event.get('source', 'unknown'),
        value=json.dumps(anomaly_event)
    )
    producer.flush() # Ensure it's sent immediately

def start_consumer():
    print(f"Starting Anomaly Consumer on {KAFKA_BROKER}...", flush=True)
    start_http_server(8001)  
    try:
        while True:
            # Poll for messages (wait up to 1 second)
            msg = consumer.poll(1.0)

            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    print(msg.error())
                    break

            # Process the valid message
            process_event(msg.value().decode('utf-8'))
            
            # Commit offset (mark as processed)
            consumer.commit(msg)

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()