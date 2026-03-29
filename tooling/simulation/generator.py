import time
import requests
import json
import random
import uuid
import csv
import os

API_URL = os.getenv("API_URL", "http://localhost:8080/v1/events")
SERVICES = ["payment-service", "order-service", "user-service"]

# Relative to this file's location so it works regardless of cwd
CSV_FILE = os.path.join(os.path.dirname(__file__), "..", "training_data.csv")

# Anomaly rates
LATENCY_ANOMALY_RATE = float(os.getenv("LATENCY_ANOMALY_RATE", "0.05"))   # 5% high-latency spikes
ERROR_LOG_RATE       = float(os.getenv("ERROR_LOG_RATE",        "0.03"))   # 3% error logs

LOG_LEVELS_NORMAL = ["INFO", "DEBUG", "WARN"]
ERROR_MESSAGES = [
    "Connection timeout to database",
    "Failed to process payment: upstream error",
    "Null pointer exception in order handler",
    "Redis cache miss rate exceeded threshold",
]
INFO_MESSAGES = [
    "Request processed successfully",
    "Cache hit for user session",
    "Order dispatched to fulfillment",
    "Payment authorized",
]


def make_metric_event(source, latency, metadata):
    return {
        "event_id": str(uuid.uuid4()),
        "source": source,
        "type": "metric",
        "payload": {
            "name": "latency",
            "value": latency,
            "metadata": metadata,
        },
    }


def make_log_event(source, level, message, metadata):
    return {
        "event_id": str(uuid.uuid4()),
        "source": source,
        "type": "log",
        "payload": {
            "level": level,
            "message": message,
            "metadata": metadata,
        },
    }


def run_simulation():
    csv_path = os.path.abspath(CSV_FILE)
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, "a", newline="") as csvfile:
        fieldnames = ["latency", "metadata_size", "source_id"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        print(f"Generator started. Saving training data to {csv_path}")
        print(f"Latency anomaly rate: {LATENCY_ANOMALY_RATE*100:.0f}%  "
              f"Error log rate: {ERROR_LOG_RATE*100:.0f}%")

        source_mapping = {"payment-service": 1, "order-service": 2, "user-service": 3}

        while True:
            source = random.choice(SERVICES)
            metadata = {"region": "us-east-1", "env": "dev"}
            metadata_size = len(json.dumps(metadata))
            source_id = source_mapping.get(source, 0)
            roll = random.random()

            # --- Metric event (always sent) ---
            if roll < LATENCY_ANOMALY_RATE:
                latency = round(random.uniform(2.0, 5.0), 3)   # anomaly spike
            else:
                latency = round(random.uniform(0.1, 0.5), 3)   # normal range

            metric_event = make_metric_event(source, latency, metadata)

            # Save features for ML training
            writer.writerow({
                "latency": latency,
                "metadata_size": metadata_size,
                "source_id": source_id,
            })
            csvfile.flush()

            # --- Log event (sampled separately) ---
            if roll < ERROR_LOG_RATE:
                log_event = make_log_event(
                    source, "ERROR", random.choice(ERROR_MESSAGES), metadata
                )
            else:
                log_event = make_log_event(
                    source, random.choice(LOG_LEVELS_NORMAL),
                    random.choice(INFO_MESSAGES), metadata
                )

            # --- Send both events ---
            for event in [metric_event, log_event]:
                try:
                    requests.post(API_URL, json=event, timeout=2)
                except requests.exceptions.RequestException:
                    print("API unreachable, CSV still being saved.")

            anomaly_marker = " [ANOMALY]" if latency > 2.0 or roll < ERROR_LOG_RATE else ""
            print(f"{source}  latency={latency:.3f}s  "
                  f"log={log_event['payload']['level']}{anomaly_marker}")

            time.sleep(0.1)


if __name__ == "__main__":
    run_simulation()
