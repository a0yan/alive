from temporalio import activity


@activity.defn
async def execute_activity(payload: dict) -> str:
    # Day 18: call executor-agent POST /execute; update audit_log row
    return "skipped"
