"""
Shared LLM provider primitives: system prompt, message building, response
parsing, and the LLMProvider ABC with a one-shot reformat-retry template.
"""
import json
import logging
from abc import ABC, abstractmethod

from pydantic import ValidationError

from ..schema import LLMResponse

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
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


def build_user_message(anomaly: dict) -> str:
    return (
        f"Anomaly type: {anomaly.get('type')}\n"
        f"Source: {anomaly.get('raw_data', {}).get('source', 'unknown')}\n"
        f"Description: {anomaly.get('description')}\n"
        f"Timestamp: {anomaly.get('timestamp')}\n"
        f"Raw payload: {json.dumps(anomaly.get('raw_data', {}).get('payload', {}))}"
    )


def parse_response(content: str) -> LLMResponse:
    """Strip markdown fences if the model adds them, then validate schema."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return LLMResponse.model_validate_json(content)


class LLMProvider(ABC):
    """Base class. Subclasses implement _complete; reason() handles parse + retry."""

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def _complete(self, system: str, messages: list[dict]) -> str:
        """Return the raw model text for the given system prompt + messages."""
        raise NotImplementedError

    def reason(self, anomaly: dict) -> LLMResponse:
        user_msg = build_user_message(anomaly)
        raw = self._complete(SYSTEM_PROMPT, [{"role": "user", "content": user_msg}])
        try:
            return parse_response(raw)
        except (ValidationError, ValueError) as e:
            log.warning("LLM output not valid JSON (%s); retrying once with correction", e)
            correction = (
                user_msg
                + "\n\nYour previous reply was NOT valid JSON:\n" + raw
                + "\n\nReturn ONLY the JSON object, nothing else."
            )
            raw2 = self._complete(SYSTEM_PROMPT, [{"role": "user", "content": correction}])
            return parse_response(raw2)
