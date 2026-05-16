"""
Assert Kafka consumer group lag < 1000 after a load test.

Usage:
    python tooling/k6/check_consumer_lag.py [--broker kafka:29092] [--max-lag 1000]

Exit code 0 = pass, 1 = fail.
"""
import argparse
import sys
import time

from confluent_kafka.admin import AdminClient
from confluent_kafka import Consumer, TopicPartition


CONSUMER_GROUP = "anomaly-detector-group-v1"
TOPIC = "ingestion.events"


def get_consumer_lag(broker: str) -> dict[int, int]:
    """Returns {partition: lag} for CONSUMER_GROUP on TOPIC."""
    admin = AdminClient({"bootstrap.servers": broker})

    # Fetch committed offsets for the consumer group
    consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": "lag-checker-tmp",
    })

    # Get topic metadata to find all partitions
    metadata = consumer.list_topics(TOPIC, timeout=10)
    if TOPIC not in metadata.topics:
        consumer.close()
        raise RuntimeError(f"Topic '{TOPIC}' not found on broker {broker}")

    partitions = [
        TopicPartition(TOPIC, p)
        for p in metadata.topics[TOPIC].partitions
    ]

    # Fetch committed offsets for the monitored group
    # (need a separate consumer bound to that group)
    group_consumer = Consumer({
        "bootstrap.servers": broker,
        "group.id": CONSUMER_GROUP,
        "enable.auto.commit": False,
    })
    committed = group_consumer.committed(partitions, timeout=10)
    group_consumer.close()

    # Fetch high-water marks (end offsets)
    lags: dict[int, int] = {}
    for tp in committed:
        lo, hi = consumer.get_watermark_offsets(tp, timeout=5)
        committed_offset = tp.offset if tp.offset >= 0 else lo
        lags[tp.partition] = max(0, hi - committed_offset)

    consumer.close()
    return lags


def main() -> None:
    parser = argparse.ArgumentParser(description="Assert Kafka consumer lag < threshold")
    parser.add_argument("--broker",  default="localhost:9092", help="Kafka broker address")
    parser.add_argument("--max-lag", type=int, default=1000,   help="Maximum acceptable total lag")
    parser.add_argument("--wait",    type=int, default=0,      help="Seconds to wait before checking (let consumer catch up)")
    args = parser.parse_args()

    if args.wait > 0:
        print(f"Waiting {args.wait}s for consumer to catch up…")
        time.sleep(args.wait)

    print(f"Checking lag for group='{CONSUMER_GROUP}' topic='{TOPIC}' broker='{args.broker}'")

    try:
        lags = get_consumer_lag(args.broker)
    except Exception as exc:
        print(f"ERROR: Could not fetch consumer lag: {exc}", file=sys.stderr)
        sys.exit(1)

    total_lag = sum(lags.values())

    print(f"\n{'Partition':<12} {'Lag':>10}")
    print("-" * 24)
    for partition, lag in sorted(lags.items()):
        flag = " ⚠" if lag > args.max_lag // max(len(lags), 1) else ""
        print(f"{partition:<12} {lag:>10}{flag}")
    print("-" * 24)
    print(f"{'TOTAL':<12} {total_lag:>10}")
    print()

    if total_lag <= args.max_lag:
        print(f"✓ PASS — total lag {total_lag} <= {args.max_lag}")
        sys.exit(0)
    else:
        print(f"✗ FAIL — total lag {total_lag} > {args.max_lag}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
