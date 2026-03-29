"""
Provider-agnostic LLM client.
Reads LLM_PROVIDER (openai | anthropic) from env and routes accordingly.
Both providers return a validated LLMResponse or raise on failure.
"""
import json
import logging
import os

from .schema import LLMResponse

log = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL    = os.getenv("LLM_MODEL", "gpt-4o-mini")

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
- confidence is a float 0.0–1.0 representing how certain you are.
- actions should be concrete remediation steps (scale_up, restart, alert_on_call, etc.).
- If unsure, lower confidence and add an alert_on_call action.
- Respond with valid JSON only — no prose outside the JSON.
"""


def _build_user_message(anomaly: dict) -> str:
    return (
        f"Anomaly type: {anomaly.get('type')}\n"
        f"Source: {anomaly.get('raw_data', {}).get('source', 'unknown')}\n"
        f"Description: {anomaly.get('description')}\n"
        f"Timestamp: {anomaly.get('timestamp')}\n"
        f"Raw payload: {json.dumps(anomaly.get('raw_data', {}).get('payload', {}))}"
    )


def _parse_response(content: str) -> LLMResponse:
    """Strip markdown fences if the model adds them, then validate schema."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return LLMResponse.model_validate_json(content)


def call_openai(anomaly: dict) -> LLMResponse:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_message(anomaly)},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return _parse_response(resp.choices[0].message.content)


def call_anthropic(anomaly: dict) -> LLMResponse:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=LLM_MODEL or "claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_message(anomaly)}],
    )
    return _parse_response(resp.content[0].text)


def reason(anomaly: dict) -> LLMResponse:
    """Route to the configured LLM provider and return a validated LLMResponse."""
    if LLM_PROVIDER == "anthropic":
        return call_anthropic(anomaly)
    return call_openai(anomaly)
