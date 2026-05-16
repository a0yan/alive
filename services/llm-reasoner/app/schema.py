"""
Pydantic models for the AIRA LLM response schema (v1).
All Kafka messages use snake_case field names.
"""
from pydantic import BaseModel, Field


class RootCause(BaseModel):
    label: str
    reason: str


class ActionTarget(BaseModel):
    kind: str    # e.g. "Deployment", "Service"
    name: str    # e.g. "payment-service"


class RemediationAction(BaseModel):
    action: str          # e.g. "scale_up", "restart", "alert"
    target: ActionTarget


class LLMResponse(BaseModel):
    root_causes: list[RootCause]
    actions: list[RemediationAction]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str


class AnomalyEvent(BaseModel):
    """Wire format consumed from anomalies.detected (AIRA Schema v1)."""
    anomaly_id: str
    source_event_id: str
    source: str = "unknown"   # top-level source added in Day 20 integration fix
    timestamp: str
    type: str
    description: str
    raw_data: dict
