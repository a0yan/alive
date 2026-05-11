import asyncio
import json
import logging
import os

from confluent_kafka import Consumer, KafkaError
from temporalio.client import Client
from temporalio.worker import Worker

from app.activities.ask_llm import ask_llm_activity
from app.activities.decide import decide_activity
from app.activities.enrich import enrich_activity
from app.activities.execute import execute_activity
from app.workflows.incident_workflow import IncidentWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal:7233")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:29092")
TASK_QUEUE = "incident-queue"


async def kafka_trigger(client: Client) -> None:
    """Consume anomalies.detected; start IncidentWorkflow for each message."""
    loop = asyncio.get_event_loop()
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BROKER,
            "group.id": "orchestrator",
            "auto.offset.reset": "latest",
        }
    )
    consumer.subscribe(["anomalies.detected"])
    log.info("Kafka trigger listening on anomalies.detected")

    try:
        while True:
            msg = await loop.run_in_executor(None, lambda: consumer.poll(1.0))
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    log.error("Kafka error: %s", msg.error())
                continue

            try:
                anomaly = json.loads(msg.value().decode("utf-8"))
                anomaly_id = anomaly.get("anomaly_id", "unknown")
                log.info("Starting workflow for anomaly %s", anomaly_id)
                await client.start_workflow(
                    IncidentWorkflow.run,
                    anomaly,
                    id=f"incident-{anomaly_id}",
                    task_queue=TASK_QUEUE,
                )
            except Exception:
                log.exception("Failed to start workflow for message")
    finally:
        consumer.close()


async def main() -> None:
    log.info("Connecting to Temporal at %s", TEMPORAL_HOST)
    client = await Client.connect(TEMPORAL_HOST)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[IncidentWorkflow],
        activities=[enrich_activity, ask_llm_activity, decide_activity, execute_activity],
    )

    log.info("Orchestrator worker started on queue '%s'", TASK_QUEUE)
    await asyncio.gather(worker.run(), kafka_trigger(client))


if __name__ == "__main__":
    asyncio.run(main())
