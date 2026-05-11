from temporalio import activity


@activity.defn
async def ask_llm_activity(enriched: dict) -> dict:
    # Day 16: produce to llm.requests, poll llm.responses with heartbeat
    return {
        "root_causes": [{"label": "stub", "reason": "placeholder"}],
        "actions": [{"action": "restart", "target": {"kind": "Deployment", "name": "stub"}}],
        "confidence": 0.9,
        "summary": "Stub LLM response — real implementation in Day 16",
    }
