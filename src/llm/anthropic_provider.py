"""Anthropic (Claude) LLM provider."""
import json
import logging
from .base import LLMProvider

log = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5-20251001"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def complete_json(self, system: str, user: str) -> dict:
        msg = self._client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system + "\n\nRespond with JSON only.",
            messages=[{"role": "user", "content": user}],
        )
        text = msg.content[0].text if msg.content else ""
        if not text.strip():
            raise RuntimeError(
                f"LLM returned empty response (stop_reason={msg.stop_reason})"
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Strip markdown fences if the model added them despite instructions
            stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            log.debug("LLM raw response: %s", text)
            return json.loads(stripped)
