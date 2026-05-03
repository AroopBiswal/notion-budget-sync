"""Return the configured LLM provider based on available API keys."""
from .base import LLMProvider
from ..config import ANTHROPIC_API_KEY, OPENAI_API_KEY


def get_provider() -> LLMProvider:
    if ANTHROPIC_API_KEY:
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(ANTHROPIC_API_KEY)
    if OPENAI_API_KEY:
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(OPENAI_API_KEY)
    raise RuntimeError(
        "No LLM provider configured. "
        "Set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
    )
