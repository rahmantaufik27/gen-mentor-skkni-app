"""
Service for persisting quiz sessions and results to JSON files.
"""

import json
import os
from typing import Optional, List
from datetime import datetime
from models.model import QuizResult


class SessionStorage:
    """Service for storing quiz sessions and results to JSON"""

    def __init__(self, storage_dir: str):
        """
        Initialize session storage
        
        Args:
            storage_dir: Path to storage directory
        """
        self.storage_dir = storage_dir
        self.results_file = os.path.join(storage_dir, "quiz_results.json")
        self.sessions_dir = os.path.join(storage_dir, "sessions")

        # Create directories if they don't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(self.sessions_dir, exist_ok=True)

        # Initialize results file if it doesn't exist
        if not os.path.exists(self.results_file):
            self._save_results([])

    def save_result(self, result: QuizResult) -> bool:
        """
        Save quiz result to JSON
        
        Args:
            result: QuizResult object
            
        Returns:
            True if saved successfully
        """
        try:
            results = self._load_results()
            results.append(result.to_dict())
            self._save_results(results)

            # Also save individual result
            result_filename = f"{result.session_id}.json"
            result_path = os.path.join(self.sessions_dir, result_filename)

            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

            return True
        except Exception as e:
            print(f"Error saving result: {e}")
            return False

    def get_result(self, session_id: str) -> Optional[dict]:
        """
        Get a quiz result by session ID
        
        Args:
            session_id: ID of the session
            
        Returns:
            Result dictionary or None if not found
        """
        try:
            result_filename = f"{session_id}.json"
            result_path = os.path.join(self.sessions_dir, result_filename)

            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as f:
                    return json.load(f)

            return None
        except Exception as e:
            print(f"Error getting result: {e}")
            return None

    def get_all_results(self) -> List[dict]:
        """
        Get all quiz results
        
        Returns:
            List of result dictionaries
        """
        try:
            return self._load_results()
        except Exception as e:
            print(f"Error getting all results: {e}")
            return []

    def get_results_summary(self) -> dict:
        """
        Get summary statistics of all quiz results
        
        Returns:
            Dictionary with summary statistics
        """
        results = self.get_all_results()

        if not results:
            return {
                "total_quizzes": 0,
                "passed": 0,
                "failed": 0,
                "average_score": 0,
                "total_correct_answers": 0,
                "total_wrong_answers": 0
            }

        passed = sum(1 for r in results if r.get("is_passed", False))
        failed = len(results) - passed
        total_correct = sum(r.get("correct_answers", 0) for r in results)
        total_wrong = sum(r.get("wrong_answers", 0) for r in results)
        average_score = sum(r.get("score_percentage", 0) for r in results) / len(results)

        return {
            "total_quizzes": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / len(results) * 100), 2) if results else 0,
            "average_score": round(average_score, 2),
            "total_correct_answers": total_correct,
            "total_wrong_answers": total_wrong
        }

    def _load_results(self) -> List[dict]:
        """Load all results from JSON file"""
        try:
            if os.path.exists(self.results_file):
                with open(self.results_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading results: {e}")

        return []

    def _save_results(self, results: List[dict]) -> None:
        """Save results to JSON file"""
        with open(self.results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    def clear_all_sessions(self) -> bool:
        """
        Clear all stored sessions (for cleanup/testing)
        
        Returns:
            True if cleared successfully
        """
        try:
            # Clear results file
            self._save_results([])

            # Clear individual session files
            for filename in os.listdir(self.sessions_dir):
                if filename.endswith(".json"):
                    os.remove(os.path.join(self.sessions_dir, filename))

            return True
        except Exception as e:
            print(f"Error clearing sessions: {e}")
            return False
