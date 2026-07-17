"""Native Anthropic provider (distinct message format: system kwarg)."""
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Adapter for the native Anthropic Messages API."""

    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self.api_key = api_key

    def _complete(self, system: str, messages: list[dict]) -> str:
        # lazy import: keeps unit tests SDK-free
        import anthropic  # pylint: disable=import-outside-toplevel,import-error
        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system,
            messages=messages,
        )
        return resp.content[0].text
