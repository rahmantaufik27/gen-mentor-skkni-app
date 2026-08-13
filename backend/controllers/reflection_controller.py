"""
Controller for Learning Reflection endpoints.

Thin pass-through to ReflectionService, matching the other controllers'
convention of normalizing exceptions into {"success": False, "error": ...}.
"""

from typing import Dict, Optional

from services.reflection_service import ReflectionService


class ReflectionController:
    """Controller for reflection questions + answers."""

    def __init__(self, reflection_service: ReflectionService):
        self.reflection_service = reflection_service

    def get_questions(self) -> Dict:
        try:
            return self.reflection_service.get_questions()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_answers(self, user_id: str) -> Dict:
        try:
            return self.reflection_service.get_answers(user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_answer(self, user_id: str, question_key: str, answer_text: Optional[str] = None, answer_number: Optional[int] = None) -> Dict:
        try:
            return self.reflection_service.save_answer(user_id, question_key, answer_text, answer_number)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_answer(self, user_id: str, question_key: str) -> Dict:
        try:
            return self.reflection_service.delete_answer(user_id, question_key)
        except Exception as e:
            return {"success": False, "error": str(e)}
