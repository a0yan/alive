"""OpenAI-compatible provider — covers OpenAI, Groq, Together AI, Ollama, HuggingFace."""
from .base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    def __init__(self, model: str, base_url: str, api_key: str, json_mode: str | None):
        super().__init__(model)
        self.base_url = base_url
        self.api_key = api_key
        self.json_mode = json_mode

    def _complete(self, system: str, messages: list[dict]) -> str:
        from openai import OpenAI  # lazy: keeps unit tests SDK-free
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs = {}
        if self.json_mode == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=0.2,
            **kwargs,
        )
        return resp.choices[0].message.content
