"""
Controller for chatbot endpoints.

Thin pass-through to ChatbotService, matching the QuizController/
MaterialsController convention of normalizing exceptions into
{"success": False, "error": ...}.
"""

from services.chatbot_service import ChatbotService


class ChatbotController:
    """Controller for the standalone learning-assistant chatbot."""

    def __init__(self, chatbot_service: ChatbotService):
        self.chatbot_service = chatbot_service

    def chat(self, messages) -> dict:
        """Produce an assistant reply for the given conversation."""
        try:
            return self.chatbot_service.chat(messages)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def health(self) -> dict:
        """Report whether the underlying LLM provider is reachable."""
        try:
            return {"success": True, "available": self.chatbot_service.is_available()}
        except Exception as e:
            return {"success": False, "error": str(e)}
