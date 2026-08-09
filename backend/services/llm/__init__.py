"""
LLM provider package - the modular seam behind the chatbot.

get_llm_provider() is the ONE place that decides which concrete provider the
app uses. Today it's Ollama (local qwen2.5:1.5b); switching to another local
model or a cloud API (e.g. OpenAI/ChatGPT) is a matter of adding a subclass
and one branch here (or setting the LLM_PROVIDER env var) - nothing
downstream changes.
"""

import os

from services.llm.base import LLMProvider, LLMProviderError
from services.llm.ollama_provider import OllamaProvider

__all__ = ["LLMProvider", "LLMProviderError", "OllamaProvider", "get_llm_provider"]


def get_llm_provider() -> LLMProvider:
    """
    Return the configured LLM provider.

    Selected via the LLM_PROVIDER env var (default: "ollama"). Add new
    providers by importing the subclass and adding a branch below.
    """
    provider = os.environ.get("LLM_PROVIDER", "ollama").strip().lower()

    if provider == "ollama":
        return OllamaProvider()

    # Future providers plug in here, e.g.:
    #   if provider == "openai":
    #       from services.llm.openai_provider import OpenAIProvider
    #       return OpenAIProvider()

    raise LLMProviderError(f"Unknown LLM provider '{provider}' (set LLM_PROVIDER).")
