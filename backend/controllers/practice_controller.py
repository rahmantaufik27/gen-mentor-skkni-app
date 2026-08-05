"""
Controllers for practice-session API endpoints.

Thin pass-through to PracticeService, matching QuizController's convention
of normalizing exceptions into {"success": False, "error": ...}.
"""

from services.practice_service import PracticeService


class PracticeController:
    """Controller for practice-session operations."""

    def __init__(self, practice_service: PracticeService):
        """
        Initialize practice controller

        Args:
            practice_service: PracticeService instance
        """
        self.practice_service = practice_service

    def start_practice(self, user_id: str) -> dict:
        """
        Start a new practice session

        Args:
            user_id: ID of the user starting practice

        Returns:
            Dictionary with session info and first question
        """
        try:
            return self.practice_service.start_practice(user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_question(self, session_id: str, question_index: int) -> dict:
        """
        Get a specific question from a practice session

        Args:
            session_id: ID of the session
            question_index: Index of the question (0-based)

        Returns:
            Dictionary with question data
        """
        try:
            return self.practice_service.get_question(session_id, question_index)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def submit_answer(self, session_id: str, question_index: int, selected_answer: str) -> dict:
        """
        Submit an answer for a practice question

        Args:
            session_id: ID of the session
            question_index: Index of the question (0-based)
            selected_answer: Selected choice ID (A, B, C, or D)

        Returns:
            Dictionary with result
        """
        try:
            return self.practice_service.submit_answer(session_id, question_index, selected_answer)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def complete_practice(self, session_id: str) -> dict:
        """
        Complete a practice session

        Args:
            session_id: ID of the session

        Returns:
            Dictionary with results
        """
        try:
            return self.practice_service.complete_practice(session_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_practice_analytics(self, user_id: str) -> dict:
        """
        Get the current user's Practice Analytics dashboard payload

        Args:
            user_id: ID of the user

        Returns:
            Dictionary with total_sessions and per-unit progression
        """
        try:
            return self.practice_service.get_practice_analytics(user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}
