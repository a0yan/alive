from temporalio import activity


@activity.defn
async def enrich_activity(anomaly: dict) -> dict:
    # Day 16: query audit_log for last 5 anomalies from same source
    return {"context": "placeholder", "source": anomaly.get("source", "unknown")}
