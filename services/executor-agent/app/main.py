import logging
import os

from fastapi import FastAPI
from prometheus_client import make_asgi_app, Counter, Histogram
from pydantic import BaseModel

from app.db import write_execution_result
from app.k8s_client import execute_dry_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="AIRA Executor Agent")
app.mount("/metrics", make_asgi_app())

EXECUTIONS = Counter("executor_executions_total", "Execution requests processed", ["status"])
EXECUTION_LATENCY = Histogram("executor_execution_latency_seconds", "Time to process /execute")


class ActionTarget(BaseModel):
    kind: str
    name: str


class Action(BaseModel):
    action: str
    target: ActionTarget


class ExecuteRequest(BaseModel):
    anomaly_id: str
    workflow_id: str
    actions: list[Action]
    decision: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/execute")
async def execute(req: ExecuteRequest):
    log.info(
        "Execute request anomaly=%s workflow=%s decision=%s actions=%d",
        req.anomaly_id, req.workflow_id, req.decision, len(req.actions),
    )

    diffs: list[str] = []
    results: list[dict] = []

    for action in req.actions:
        result = execute_dry_run(action.action, action.target.kind, action.target.name)
        diffs.append(result.get("diff", ""))
        results.append(result)

    first_action = req.actions[0] if req.actions else None
    action_label = (
        f"{first_action.action} {first_action.target.name}" if first_action else "none"
    )

    await write_execution_result(
        workflow_id=req.workflow_id,
        anomaly_id=req.anomaly_id,
        source="executor-agent",
        action_taken=action_label,
        diffs=diffs,
        exec_status="executed",
    )

    EXECUTIONS.labels(status="executed").inc()
    return {
        "status": "executed",
        "anomaly_id": req.anomaly_id,
        "workflow_id": req.workflow_id,
        "results": results,
    }
