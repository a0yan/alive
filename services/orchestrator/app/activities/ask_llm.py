import asyncio
import json
import logging
import os
from temporalio import activity

log = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

_SYSTEM_PROMPT = """\
You are an SRE incident-response assistant. Given an infrastructure anomaly, \
you must respond with ONLY a JSON object — no markdown, no explanation — \
matching this exact schema:

{
  "root_causes": [{"label": "string", "reason": "string"}],
  "actions": [{"action": "string", "target": {"kind": "string", "name": "string"}}],
  "confidence": 0.0,
  "summary": "string"
}

Rules:
- confidence is a float 0.0-1.0 representing how certain you are.
- actions should be concrete remediation steps (scale_up, restart, alert_on_call, etc.).
- If unsure, lower confidence and add an alert_on_call action.
- Respond with valid JSON only.
"""


def _build_user_message(enriched: dict) -> str:
    context = enriched.get("context", {})
    history = context.get("history", []) if isinstance(context, dict) else []
    return (
        f"Anomaly type: {enriched.get('type')}\n"
        f"Source: {enriched.get('source') or enriched.get('raw_data', {}).get('source', 'unknown')}\n"
        f"Description: {enriched.get('description')}\n"
        f"Timestamp: {enriched.get('timestamp')}\n"
        f"Raw payload: {json.dumps(enriched.get('raw_data', {}).get('payload', {}))}\n"
        f"Recent history ({len(history)} records): {json.dumps(history, default=str)}"
    )


def _parse_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


async def _call_with_heartbeat(enriched: dict) -> dict:
    """Run LLM call in executor; heartbeat every 5s so Temporal survives crashes."""
    loop = asyncio.get_event_loop()

    if LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        def _sync_call():
            resp = client.messages.create(
                model=LLM_MODEL or "claude-haiku-4-5-20251001",
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_message(enriched)}],
            )
            return resp.content[0].text
    else:
        from openai import OpenAI
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        def _sync_call():
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_message(enriched)},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content

    task = asyncio.ensure_future(loop.run_in_executor(None, _sync_call))
    while not task.done():
        activity.heartbeat("llm_call_in_progress")
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
        except asyncio.TimeoutError:
            pass

    return _parse_response(task.result())


@activity.defn
async def ask_llm_activity(enriched: dict) -> dict:
    source = enriched.get("source") or enriched.get("raw_data", {}).get("source", "unknown")

    api_configured = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    if not api_configured:
        log.warning("No LLM API key — returning stub response for anomaly=%s", enriched.get("anomaly_id"))
        return {
            "root_causes": [{"label": "unknown", "reason": "No LLM API key configured"}],
            "actions": [{"action": "alert_on_call", "target": {"kind": "Service", "name": source}}],
            "confidence": 0.1,
            "summary": "LLM reasoning disabled — configure OPENAI_API_KEY or ANTHROPIC_API_KEY",
            "anomaly_id": enriched.get("anomaly_id"),
            "source": source,
            "type": enriched.get("type"),
        }

    try:
        result = await _call_with_heartbeat(enriched)
        log.info(
            "LLM response anomaly=%s confidence=%.2f summary=%r",
            enriched.get("anomaly_id"), result.get("confidence", 0), result.get("summary", "")[:80],
        )
        return {
            **result,
            "anomaly_id": enriched.get("anomaly_id"),
            "source": source,
            "type": enriched.get("type"),
        }
    except Exception as exc:
        log.error("LLM call failed for anomaly=%s: %s", enriched.get("anomaly_id"), exc)
        return {
            "root_causes": [{"label": "error", "reason": str(exc)}],
            "actions": [{"action": "alert_on_call", "target": {"kind": "Service", "name": source}}],
            "confidence": 0.0,
            "summary": f"LLM call failed: {exc}",
            "anomaly_id": enriched.get("anomaly_id"),
            "source": source,
            "type": enriched.get("type"),
        }
