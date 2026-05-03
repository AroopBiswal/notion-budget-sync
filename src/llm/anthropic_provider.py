"""Anthropic (Claude) LLM provider."""
import json
from .base import LLMProvider

MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete_json(self, system: str, user: str) -> dict:
        msg = self._client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system + "\n\nRespond with valid JSON only. No explanation, no markdown.",
            messages=[{"role": "user", "content": user}],
        )
        return json.loads(msg.content[0].text)
