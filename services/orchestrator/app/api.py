import logging
import os
from fastapi import FastAPI, HTTPException
from temporalio.client import Client
from app.db import get_pool

log = logging.getLogger(__name__)
app = FastAPI(title="AIRA Orchestrator API")

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal:7233")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/approve/{anomaly_id}")
async def approve(anomaly_id: str, approved_by: str = "dashboard"):
    workflow_id = f"incident-{anomaly_id}"
    try:
        client = await Client.connect(TEMPORAL_HOST)
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("approve_action")

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE audit_log SET approved_by = $1, action_status = 'approved' WHERE workflow_id = $2",
                approved_by,
                workflow_id,
            )

        log.info("Approved workflow=%s by=%s", workflow_id, approved_by)
        return {"status": "approved", "workflow_id": workflow_id}
    except Exception as exc:
        log.error("Approval failed workflow=%s: %s", workflow_id, exc)
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/pending")
async def pending_approvals():
    """Return audit_log rows awaiting human approval."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT workflow_id, anomaly_id, source, anomaly_type,
                   llm_summary, confidence, action_taken, created_at
            FROM audit_log
            WHERE action_status = 'pending_approval'
            ORDER BY created_at DESC
            LIMIT 50
            """
        )
    return [dict(r) for r in rows]
