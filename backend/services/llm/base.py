"""
Provider-agnostic LLM interface.

This is the single seam the rest of the app depends on. Swapping the local
Ollama model for another local model or a cloud API (e.g. OpenAI/ChatGPT)
means writing one new LLMProvider subclass and pointing the factory (see
services/llm/__init__.py) at it - ChatbotService, the controller, the route,
and the frontend never change.

Nothing here (or anywhere under services/llm/) touches the database, Neo4j,
the user model, recommendations, or adaptive-learning logic - the chatbot is
a deliberately standalone learning assistant.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class LLMProviderError(Exception):
    """
    Raised when the underlying provider can't produce a reply (unreachable,
    model missing, timeout, malformed response, ...). Callers translate this
    into a user-facing message rather than a stack trace.
    """


class LLMProvider(ABC):
    """A minimal chat-completion contract every provider must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for logs/debugging, e.g. 'ollama:qwen2.5:1.5b'."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """
        Cheap reachability check - True if the provider is ready to serve a
        chat request right now. Must never raise; return False on any error.
        """
        raise NotImplementedError

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Given a conversation as an ordered list of
        {"role": "system"|"user"|"assistant", "content": str} dicts, return
        the assistant's reply text.

        Raises:
            LLMProviderError: if the provider is unavailable or fails.
        """
        raise NotImplementedError
