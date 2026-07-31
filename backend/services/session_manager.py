"""
Service for managing quiz sessions.
"""

import uuid
import random
from typing import List, Optional
from datetime import datetime
from models.model import Question, QuizSession, UserAnswer, QuizResult


class QuizSessionManager:
    """Manager for quiz sessions and quiz operations"""

    TOTAL_QUESTIONS = 30
    PASSING_PERCENTAGE = 75  # 75% = 23 out of 30

    def __init__(self, question_loader):
        """
        Initialize session manager
        
        Args:
            question_loader: QuestionLoader instance
        """
        self.question_loader = question_loader
        self.sessions: dict = {}  # In-memory session storage

    def create_session(self, user_id: str = None) -> QuizSession:
        """
        Create a new quiz session with randomized questions
        
        Args:
            user_id: ID of the user creating the session
        
        Returns:
            QuizSession object
        """
        session_id = str(uuid.uuid4())

        # Load all questions
        all_questions = self.question_loader.load_questions()

        # Randomize and select exactly TOTAL_QUESTIONS
        if len(all_questions) < self.TOTAL_QUESTIONS:
            selected_questions = all_questions
        else:
            selected_questions = random.sample(all_questions, self.TOTAL_QUESTIONS)

        # Create session
        session = QuizSession(
            session_id=session_id,
            questions=selected_questions,
            user_answers=[],
            started_at=datetime.now().isoformat(),
            is_completed=False
        )

        # Store session
        self.sessions[session_id] = session

        return session

    def get_session(self, session_id: str) -> Optional[QuizSession]:
        """
        Get a session by ID
        
        Args:
            session_id: ID of the session
            
        Returns:
            QuizSession or None if not found
        """
        return self.sessions.get(session_id)

    def submit_answer(
        self,
        session_id: str,
        question_id: str,
        choice_id: str
    ) -> bool:
        """
        Submit an answer for a question in a session
        
        Args:
            session_id: ID of the session
            question_id: ID of the question
            choice_id: ID of the chosen answer
            
        Returns:
            True if answer was successfully recorded
        """
        session = self.get_session(session_id)
        if not session or session.is_completed:
            return False

        # Validate answer
        is_correct = self.question_loader.validate_question_answer(
            question_id, choice_id
        )

        # Record answer
        user_answer = UserAnswer(
            question_id=question_id,
            selected_choice_id=choice_id,
            is_correct=is_correct,
            answered_at=datetime.now().isoformat()
        )

        session.user_answers.append(user_answer)

        # Auto-complete session if all questions are answered
        if len(session.user_answers) == len(session.questions):
            self.complete_session(session_id)

        return True

    def complete_session(self, session_id: str) -> Optional[QuizResult]:
        """
        Complete a quiz session and calculate results
        
        Args:
            session_id: ID of the session
            
        Returns:
            QuizResult object
        """
        session = self.get_session(session_id)
        if not session:
            return None

        # Mark session as completed
        session.is_completed = True
        session.completed_at = datetime.now().isoformat()

        # Calculate results
        result = self._calculate_results(session)

        return result

    def get_results(self, session_id: str) -> Optional[QuizResult]:
        """
        Get quiz results for a completed session
        
        Args:
            session_id: ID of the session
            
        Returns:
            QuizResult object
        """
        session = self.get_session(session_id)
        if not session or not session.is_completed:
            return None

        return self._calculate_results(session)

    def _calculate_results(self, session: QuizSession) -> QuizResult:
        """
        Calculate quiz results from a session
        
        Args:
            session: QuizSession to calculate results for
            
        Returns:
            QuizResult object
        """
        total_questions = len(session.questions)
        correct_answers = sum(1 for a in session.user_answers if a.is_correct)
        wrong_answers = total_questions - correct_answers

        # Calculate percentage
        if total_questions > 0:
            score_percentage = (correct_answers / total_questions) * 100
        else:
            score_percentage = 0

        # Determine pass/fail
        is_passed = score_percentage >= self.PASSING_PERCENTAGE

        # Build detailed answer review
        answers = []
        for user_answer in session.user_answers:
            question = self.question_loader.get_question_by_id(user_answer.question_id)
            if question:
                # Find the selected choice
                selected_choice = None
                correct_choice = None
                for choice in question.choices:
                    if choice.id == user_answer.selected_choice_id:
                        selected_choice = choice
                    if choice.is_correct:
                        correct_choice = choice

                answers.append({
                    "question_id": user_answer.question_id,
                    "question_text": question.question_text,
                    "category": question.category,
                    "difficulty": question.difficulty,
                    "your_answer": selected_choice.text if selected_choice else "Not answered",
                    "correct_answer": correct_choice.text if correct_choice else "Unknown",
                    "is_correct": user_answer.is_correct,
                    "explanation": question.explanation,
                })

        result = QuizResult(
            session_id=session.session_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
            wrong_answers=wrong_answers,
            score_percentage=round(score_percentage, 2),
            is_passed=is_passed,
            completed_at=session.completed_at or datetime.now().isoformat(),
            answers=answers
        )

        return result

    def get_session_progress(self, session_id: str) -> dict:
        """
        Get progress information for a session
        
        Args:
            session_id: ID of the session
            
        Returns:
            Dictionary with progress information
        """
        session = self.get_session(session_id)
        if not session:
            return None

        total = len(session.questions)
        answered = len(session.user_answers)

        return {
            "session_id": session_id,
            "total_questions": total,
            "answered_questions": answered,
            "remaining_questions": total - answered,
            "progress_percentage": (answered / total * 100) if total > 0 else 0,
            "is_completed": session.is_completed
        }

    def get_question_for_session(self, session_id: str, question_index: int) -> Optional[dict]:
        """
        Get a specific question from a session
        
        Args:
            session_id: ID of the session
            question_index: Index of the question (0-based)
            
        Returns:
            Question data as dictionary
        """
        session = self.get_session(session_id)
        if not session or question_index >= len(session.questions):
            return None

        question = session.questions[question_index]
        
        # Reconstruct options dengan format asli questions.json
        options_formatted = []
        choice_labels = ["a)", "b)", "c)", "d)"]
        for idx, choice in enumerate(question.choices):
            # options_formatted.append(f"{choice_labels[idx]} {choice.text}")
            options_formatted.append(f"{choice.text}")
        
        return {
            "id": question.id,
            "question": question.question_text,        # ← BENAR: "question"
            "options": options_formatted,               # ← BENAR: "options" dengan format "a) ...", "b) ...", dll
            "category": question.category,
            "difficulty": question.difficulty,
            "correct_answer": question.choices[0].id if any(c.is_correct for c in question.choices) else None,  # Map back to letter
            "bloom_level": self._map_difficulty_to_bloom(question.difficulty),  # NEW
            "unit": question.category,                 # Map category back to unit
            "answer_type": question.answer_type,
            "choices": [{"id": c.id, "text": c.text} for c in question.choices]  # Keep for backend compatibility
        }

    def _map_difficulty_to_bloom(self, difficulty: str) -> str:
        """Map difficulty back to bloom_level format"""
        if difficulty == "easy":
            return "C1"
        elif difficulty == "medium":
            return "C3"
        else:
            return "C5"

    def get_all_session_questions(self, session_id: str) -> List[dict]:
        """
        Get all questions for a session (without answers exposed)
        
        Args:
            session_id: ID of the session
            
        Returns:
            List of question dictionaries
        """
        session = self.get_session(session_id)
        if not session:
            return []

        questions = []
        for question in session.questions:
            questions.append({
                "id": question.id,
                "question_text": question.question_text,
                "category": question.category,
                "difficulty": question.difficulty,
                "choices": [
                    {
                        "id": c.id,
                        "text": c.text
                    }
                    for c in question.choices
                ],
                "answer_type": question.answer_type
            })

        return questions
