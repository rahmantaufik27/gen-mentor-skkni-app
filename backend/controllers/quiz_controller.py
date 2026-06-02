"""
Controllers for quiz API endpoints.
"""

from services.quiz_service import QuizService


class QuizController:
    """Controller for quiz operations"""

    def __init__(self, quiz_service: QuizService):
        """
        Initialize quiz controller
        
        Args:
            quiz_service: QuizService instance
        """
        self.quiz_service = quiz_service

    def start_quiz(self, user_id: str) -> dict:
        """
        Start a new quiz session
        
        Args:
            user_id: ID of the user starting the quiz
        
        Returns:
            Dictionary with session info and first question
        """
        try:
            return self.quiz_service.start_quiz(user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_question(self, session_id: str, question_index: int) -> dict:
        """
        Get a specific question from a session
        
        Args:
            session_id: ID of the session
            question_index: Index of the question (0-based)
            
        Returns:
            Dictionary with question data
        """
        try:
            return self.quiz_service.get_question(session_id, question_index)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def submit_answer(self, session_id: str, question_index: int, selected_answer: str) -> dict:
        """
        Submit an answer for a question
        
        Args:
            session_id: ID of the session
            question_index: Index of the question (0-based)
            selected_answer: Selected choice ID (A, B, C, or D)
            
        Returns:
            Dictionary with result
        """
        try:
            return self.quiz_service.submit_answer(session_id, question_index, selected_answer)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def complete_quiz(self, session_id: str, user_id: str) -> dict:
        """
        Complete quiz and save results
        
        Args:
            session_id: ID of the session
            user_id: ID of the user
            
        Returns:
            Dictionary with results
        """
        try:
            return self.quiz_service.complete_quiz(session_id, user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_user_quiz_history(self, user_id: str, limit: int = 10) -> dict:
        """
        Get user quiz history
        
        Args:
            user_id: ID of the user
            limit: Number of attempts to retrieve
            
        Returns:
            Dictionary with quiz history
        """
        try:
            return self.quiz_service.get_user_quiz_history(user_id, limit)
        except Exception as e:
            return {"success": False, "error": str(e)}
