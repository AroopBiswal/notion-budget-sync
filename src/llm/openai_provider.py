"""OpenAI LLM provider."""
import json
from .base import LLMProvider

MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)

    def complete_json(self, system: str, user: str) -> dict:
        resp = self._client.chat.completions.create(
            model=MODEL,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = resp.choices[0].message.content or ""
        if not text.strip():
            raise RuntimeError("LLM returned empty response")
        return json.loads(text)
