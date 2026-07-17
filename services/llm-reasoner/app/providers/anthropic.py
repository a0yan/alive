"""Native Anthropic provider (distinct message format: system kwarg)."""
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str):
        super().__init__(model)
        self.api_key = api_key

    def _complete(self, system: str, messages: list[dict]) -> str:
        import anthropic  # lazy: keeps unit tests SDK-free
        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=512,
            system=system,
            messages=messages,
        )
        return resp.content[0].text
