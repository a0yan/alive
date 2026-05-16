import logging
from temporalio import activity
from app.db import get_pool

log = logging.getLogger(__name__)


@activity.defn
async def enrich_activity(anomaly: dict) -> dict:
    source = anomaly.get("source") or anomaly.get("raw_data", {}).get("source", "unknown")
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT anomaly_type, action_taken, action_status, confidence, created_at
            FROM audit_log
            WHERE source = $1
            ORDER BY created_at DESC
            LIMIT 5
            """,
            source,
        )
    history = [
        {
            "anomaly_type": r["anomaly_type"],
            "action_taken": r["action_taken"],
            "action_status": r["action_status"],
            "confidence": r["confidence"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    log.info(
        "Enriched anomaly=%s source=%s history_count=%d",
        anomaly.get("anomaly_id"), source, len(history),
    )
    return {"source": source, "history": history}
