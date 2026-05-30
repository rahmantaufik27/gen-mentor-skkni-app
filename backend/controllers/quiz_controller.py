"""
Controllers for quiz API endpoints.
"""

from services.question_loader import QuestionLoader
from services.session_manager import QuizSessionManager
from services.session_storage import SessionStorage


class QuizController:
    """Controller for quiz operations"""

    def __init__(self, question_loader: QuestionLoader, session_manager: QuizSessionManager, storage: SessionStorage):
        """
        Initialize quiz controller
        
        Args:
            question_loader: QuestionLoader instance
            session_manager: QuizSessionManager instance
            storage: SessionStorage instance
        """
        self.question_loader = question_loader
        self.session_manager = session_manager
        self.storage = storage

    def start_quiz(self) -> dict:
        """
        Start a new quiz session
        
        Returns:
            Dictionary with session info and first question
        """
        try:
            session = self.session_manager.create_session()

            # Get first question
            first_question = self.session_manager.get_question_for_session(
                session.session_id, 0
            )

            return {
                "success": True,
                "session_id": session.session_id,
                "total_questions": len(session.questions),
                "first_question": first_question
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

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
            question = self.session_manager.get_question_for_session(
                session_id, question_index
            )

            if not question:
                return {
                    "success": False,
                    "error": "Question not found"
                }

            progress = self.session_manager.get_session_progress(session_id)

            return {
                "success": True,
                "question_index": question_index,
                "question": question,
                "progress": progress
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def submit_answer(self, session_id: str, question_id: str, choice_id: str) -> dict:
        """
        Submit an answer for a question
        
        Args:
            session_id: ID of the session
            question_id: ID of the question
            choice_id: ID of the chosen answer
            
        Returns:
            Dictionary with result
        """
        try:
            success = self.session_manager.submit_answer(
                session_id, question_id, choice_id
            )

            if not success:
                return {
                    "success": False,
                    "error": "Failed to submit answer"
                }

            progress = self.session_manager.get_session_progress(session_id)

            return {
                "success": True,
                "progress": progress,
                "is_completed": progress["is_completed"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_progress(self, session_id: str) -> dict:
        """
        Get quiz progress
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with progress info
        """
        try:
            progress = self.session_manager.get_session_progress(session_id)

            if not progress:
                return {
                    "success": False,
                    "error": "Session not found"
                }

            return {
                "success": True,
                "progress": progress
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def complete_quiz(self, session_id: str) -> dict:
        """
        Complete and submit quiz
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with results
        """
        try:
            result = self.session_manager.complete_session(session_id)

            if not result:
                return {
                    "success": False,
                    "error": "Session not found"
                }

            # Save result to JSON
            self.storage.save_result(result)

            return {
                "success": True,
                "result": result.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_results(self, session_id: str) -> dict:
        """
        Get quiz results
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with results
        """
        try:
            result = self.session_manager.get_results(session_id)

            if not result:
                return {
                    "success": False,
                    "error": "Results not found"
                }

            return {
                "success": True,
                "result": result.to_dict()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_all_results(self) -> dict:
        """
        Get all quiz results from storage
        
        Returns:
            Dictionary with all results
        """
        try:
            results = self.storage.get_all_results()
            summary = self.storage.get_results_summary()

            return {
                "success": True,
                "results": results,
                "summary": summary
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_results_summary(self) -> dict:
        """
        Get summary statistics of all quiz results
        
        Returns:
            Dictionary with summary stats
        """
        try:
            summary = self.storage.get_results_summary()

            return {
                "success": True,
                "summary": summary
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
