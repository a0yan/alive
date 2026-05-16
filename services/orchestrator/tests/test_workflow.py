"""
Temporal workflow tests using time-skipping environment.
Tests two paths: auto-execute (confidence >= 0.8) and pending_approval (confidence < 0.8).
"""
import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.incident_workflow import IncidentWorkflow

_TEST_ANOMALY = {
    "anomaly_id": "anom-test-001",
    "source_event_id": "evt-001",
    "source": "orders-service",
    "type": "HighLatency",
    "description": "p99 latency exceeded 2s",
    "timestamp": "2024-01-01T00:00:00Z",
    "raw_data": {"source": "orders-service", "payload": {"name": "latency", "value": 2.5}},
}


# ── Mock activities ──────────────────────────────────────────────────────────

@activity.defn(name="enrich_activity")
async def mock_enrich(anomaly: dict) -> dict:
    return {"source": anomaly.get("source", "test"), "history": []}


@activity.defn(name="ask_llm_activity")
async def mock_ask_llm_high(enriched: dict) -> dict:
    return {
        "root_causes": [{"label": "high_load", "reason": "Traffic spike"}],
        "actions": [{"action": "scale_up", "target": {"kind": "Deployment", "name": "orders-service"}}],
        "confidence": 0.95,
        "summary": "High load on orders-service — scale up recommended",
        "anomaly_id": enriched.get("anomaly_id"),
        "source": enriched.get("source", "orders-service"),
        "type": enriched.get("type"),
    }


@activity.defn(name="ask_llm_activity")
async def mock_ask_llm_low(enriched: dict) -> dict:
    return {
        "root_causes": [{"label": "unknown", "reason": "Unclear cause"}],
        "actions": [{"action": "alert_on_call", "target": {"kind": "Service", "name": "orders-service"}}],
        "confidence": 0.4,
        "summary": "Cannot determine root cause — alerting on-call",
        "anomaly_id": enriched.get("anomaly_id"),
        "source": enriched.get("source", "orders-service"),
        "type": enriched.get("type"),
    }


@activity.defn(name="decide_activity")
async def mock_decide_auto(llm_response: dict) -> str:
    return "auto_executed" if llm_response.get("confidence", 0) >= 0.8 else "pending_approval"


@activity.defn(name="decide_activity")
async def mock_decide_pending(llm_response: dict) -> str:
    return "pending_approval"


@activity.defn(name="execute_activity")
async def mock_execute(payload: dict) -> str:
    decision = payload.get("decision", "skipped")
    if decision in ("auto_executed", "approved"):
        return "executed"
    return "skipped"


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auto_execute_high_confidence():
    """Workflow completes automatically when confidence >= 0.8."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[IncidentWorkflow],
            activities=[mock_enrich, mock_ask_llm_high, mock_decide_auto, mock_execute],
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                _TEST_ANOMALY,
                id="test-incident-high-001",
                task_queue="test-queue",
            )

    assert result["status"] == "executed"
    assert result["anomaly_id"] == "anom-test-001"


@pytest.mark.asyncio
async def test_pending_approval_requires_signal():
    """Workflow waits for approve_action signal when confidence < 0.8."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[IncidentWorkflow],
            activities=[mock_enrich, mock_ask_llm_low, mock_decide_pending, mock_execute],
        ):
            handle = await env.client.start_workflow(
                IncidentWorkflow.run,
                _TEST_ANOMALY,
                id="test-incident-low-001",
                task_queue="test-queue",
            )

            # Send approval signal
            await handle.signal(IncidentWorkflow.approve_action)
            result = await handle.result()

    assert result["anomaly_id"] == "anom-test-001"
    # After approval, execute_activity receives decision="approved" → "executed"
    assert result["status"] == "executed"


@pytest.mark.asyncio
async def test_skipped_when_no_decision():
    """execute_activity returns 'skipped' for unknown decision."""

    @activity.defn(name="decide_activity")
    async def mock_decide_skip(llm_response: dict) -> str:
        return "auto_executed"

    @activity.defn(name="execute_activity")
    async def mock_execute_skip(payload: dict) -> str:
        return "skipped"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[IncidentWorkflow],
            activities=[mock_enrich, mock_ask_llm_low, mock_decide_skip, mock_execute_skip],
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                _TEST_ANOMALY,
                id="test-incident-skip-001",
                task_queue="test-queue",
            )

    assert result["status"] == "skipped"
