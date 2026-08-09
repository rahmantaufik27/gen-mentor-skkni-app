"""
Standalone learning-assistant chat service.

Deliberately independent from the rest of the system: it never reads or
writes the database, Neo4j, the user model, recommendations, or any
adaptive-learning state. It only prepends a fixed learning-assistant system
prompt and forwards the conversation to a pluggable LLMProvider
(see services/llm/). The full conversation history is supplied by the caller
each turn - the service itself is stateless.
"""

from typing import Dict, List, Optional

from services.llm import LLMProvider, LLMProviderError, get_llm_provider

DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly, patient learning assistant for students studying "
    "software development and web programming (SKKNI competency units). "
    "Explain concepts clearly and concisely, prefer simple concrete examples, "
    "and encourage the learner. When code helps, show short, well-formatted "
    "snippets. If a question is ambiguous, ask a brief clarifying question. "
    "If you are unsure or a question is outside your knowledge, say so honestly "
    "rather than guessing. Keep replies focused and student-friendly."
)

# Guardrail so a runaway/pasted history can't be forwarded to the model wholesale.
MAX_HISTORY_MESSAGES = 40


class ChatbotService:
    """Turns a conversation into a single assistant reply via an LLMProvider."""

    def __init__(self, provider: Optional[LLMProvider] = None, system_prompt: Optional[str] = None):
        # Resolve the provider lazily: an unavailable Ollama at startup must
        # not prevent the Flask app (or any other feature) from booting.
        self._provider = provider
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = get_llm_provider()
        return self._provider

    def is_available(self) -> bool:
        """True if the underlying provider is reachable. Never raises."""
        try:
            return self.provider.is_available()
        except Exception:
            return False

    def chat(self, messages: List[Dict[str, str]]) -> Dict:
        """
        Args:
            messages: conversation so far as
                [{"role": "user"|"assistant", "content": str}, ...] - most
                recent last. A leading system message, if any, is ignored;
                this service always uses its own system prompt.

        Returns:
            {"success": True, "reply": str, "provider": str} on success, or
            {"success": False, "error": str} with a user-facing message.
        """
        conversation = self._sanitize(messages)
        if not conversation:
            return {"success": False, "error": "Please type a message to start the conversation."}

        full = [{"role": "system", "content": self.system_prompt}] + conversation
        try:
            reply = self.provider.chat(full)
            return {"success": True, "reply": reply, "provider": self.provider.name}
        except LLMProviderError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"The assistant is unavailable right now: {e}"}

    @staticmethod
    def _sanitize(messages: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        """Keep only well-formed user/assistant turns, capped to the most recent MAX_HISTORY_MESSAGES."""
        clean: List[Dict[str, str]] = []
        for m in messages or []:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = (m.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                clean.append({"role": role, "content": content})
        return clean[-MAX_HISTORY_MESSAGES:]
