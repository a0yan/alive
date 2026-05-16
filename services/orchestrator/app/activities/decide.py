import logging
import os
from temporalio import activity
from app.db import get_pool

log = logging.getLogger(__name__)
CONFIDENCE_THRESHOLD = float(os.getenv("ANOMALY_CONFIDENCE_THRESHOLD", "0.8"))


@activity.defn
async def decide_activity(llm_response: dict) -> str:
    confidence = llm_response.get("confidence", 0.0)
    anomaly_id = llm_response.get("anomaly_id", "unknown")
    status = "auto_executed" if confidence >= CONFIDENCE_THRESHOLD else "pending_approval"

    info = activity.info()
    first_action = llm_response.get("actions", [{}])[0]
    action_taken = f"{first_action.get('action', '')} {first_action.get('target', {}).get('name', '')}".strip()

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log
              (workflow_id, anomaly_id, source, anomaly_type,
               llm_summary, confidence, action_taken, action_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            info.workflow_id,
            anomaly_id,
            llm_response.get("source", "unknown"),
            llm_response.get("type", "unknown"),
            llm_response.get("summary", ""),
            confidence,
            action_taken or None,
            status,
        )

    log.info("Decision anomaly=%s status=%s confidence=%.2f", anomaly_id, status, confidence)
    return status
