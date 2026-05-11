import os
from temporalio import activity


CONFIDENCE_THRESHOLD = float(os.getenv("ANOMALY_CONFIDENCE_THRESHOLD", "0.8"))


@activity.defn
async def decide_activity(llm_response: dict) -> str:
    # Day 17: write pending_approval row to audit_log when confidence is low
    confidence = llm_response.get("confidence", 0.0)
    if confidence >= CONFIDENCE_THRESHOLD:
        return "auto_execute"
    return "pending_approval"
