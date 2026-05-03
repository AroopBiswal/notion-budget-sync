"""LLM provider abstraction."""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def complete_json(self, system: str, user: str) -> dict:
        """Send a prompt and return a parsed JSON dict."""
        ...
