import logging
import os
import httpx
from temporalio import activity
from app.db import get_pool

log = logging.getLogger(__name__)
EXECUTOR_URL = os.getenv("EXECUTOR_URL", "http://executor-agent:8090")


@activity.defn
async def execute_activity(payload: dict) -> str:
    decision = payload.get("decision", "skipped")
    anomaly_id = payload.get("anomaly_id", "unknown")
    info = activity.info()

    if decision not in ("auto_executed", "approved"):
        log.info("Skipping execution for anomaly=%s decision=%s", anomaly_id, decision)
        return "skipped"

    actions = payload.get("actions", [])
    if not actions:
        return "no_actions"

    exec_status = "executor_error"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{EXECUTOR_URL}/execute",
                json={
                    "anomaly_id": anomaly_id,
                    "workflow_id": info.workflow_id,
                    "actions": actions,
                    "decision": decision,
                },
            )
            resp.raise_for_status()
            exec_status = resp.json().get("status", "executed")
            log.info("Executor response anomaly=%s status=%s", anomaly_id, exec_status)
    except Exception as exc:
        log.error("Executor call failed anomaly=%s: %s", anomaly_id, exc)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE audit_log
            SET action_status = $1, resolved_at = now()
            WHERE workflow_id = $2
            """,
            exec_status,
            info.workflow_id,
        )

    return exec_status
