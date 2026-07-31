"""
Quiz service for handling quiz attempts and persistence to PostgreSQL.
Manages quiz attempt storage, scoring, and mastery tracking.
"""

from typing import Optional, List, Dict, Tuple
from uuid import uuid4
from datetime import datetime
from config.database import execute_query
from services.quiz_generator import QuizGenerator
from services.question_loader import QuestionLoader
from services.mastery_service import MasteryService


class QuizService:
    """Service for quiz operations with database persistence."""

    def __init__(self, question_loader: QuestionLoader):
        """
        Initialize quiz service

        Args:
            question_loader: QuestionLoader instance
        """
        self.question_loader = question_loader
        self.generator = QuizGenerator(question_loader)
        self.mastery_service = MasteryService()
        self.sessions = {}  # In-memory cache for active sessions
    
    def start_quiz(self, user_id: str) -> Dict:
        """
        Start a new quiz session for a user.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Dictionary with session info and first question, or error
        """
        try:
            # Validate dataset
            validation = self.generator.validate_dataset()
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": f"Dataset insufficient: {validation['units_available']} units, need 6"
                }
            
            # Generate quiz
            questions, unit_codes = self.generator.generate_quiz()
            
            # Create session
            session_id = str(uuid4())
            self.sessions[session_id] = {
                "user_id": user_id,
                "questions": questions,
                "unit_codes": unit_codes,
                "answers": [],  # Store [{"question_idx": int, "selected_answer": str, "is_correct": bool, "score": int}]
                "started_at": datetime.now().isoformat(),
                "current_question_index": 0
            }
            
            # Prepare first question for response
            first_q = questions[0]
            first_question_data = {
                "question_number": 1,
                "total_questions": len(questions),
                "question_text": first_q.question_text,
                "unit": unit_codes[0],
                "bloom_level": first_q.bloom_level,
                "choices": [
                    {"id": choice.id, "text": choice.text}
                    for choice in first_q.choices
                ]
            }
            
            return {
                "success": True,
                "session_id": session_id,
                "total_questions": len(questions),
                "current_question": first_question_data
            }
        
        except ValueError as e:
            return {"success": False, "error": f"Quiz generation failed: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to start quiz: {str(e)}"}
    
    def get_question(self, session_id: str, question_index: int) -> Dict:
        """
        Get a specific question from an active quiz session.
        
        Args:
            session_id: Session ID
            question_index: Question index (0-based)
            
        Returns:
            Dictionary with question data, or error
        """
        try:
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            questions = session["questions"]
            unit_codes = session["unit_codes"]
            
            if question_index < 0 or question_index >= len(questions):
                return {"success": False, "error": "Invalid question index"}
            
            question = questions[question_index]
            
            return {
                "success": True,
                "question_number": question_index + 1,
                "total_questions": len(questions),
                "question_text": question.question_text,
                "unit": unit_codes[question_index],
                "bloom_level": question.bloom_level,
                "choices": [
                    {"id": choice.id, "text": choice.text}
                    for choice in question.choices
                ]
            }
        
        except Exception as e:
            return {"success": False, "error": f"Failed to get question: {str(e)}"}
    
    def submit_answer(self, session_id: str, question_index: int, selected_answer: str) -> Dict:
        """
        Submit an answer for a question.
        
        Args:
            session_id: Session ID
            question_index: Question index (0-based)
            selected_answer: Selected choice ID (A, B, C, or D)
            
        Returns:
            Dictionary with result, or error
        """
        try:
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            questions = session["questions"]
            
            if question_index < 0 or question_index >= len(questions):
                return {"success": False, "error": "Invalid question index"}
            
            question = questions[question_index]
            
            # Check if answer is correct
            is_correct = False
            for choice in question.choices:
                if choice.id.upper() == selected_answer.upper() and choice.is_correct:
                    is_correct = True
                    break
            
            # Calculate score for this answer
            if is_correct:
                score = self.generator.get_bloom_score(question.bloom_level)
            else:
                score = 0
            
            # Record answer
            session["answers"].append({
                "question_index": question_index,
                "selected_answer": selected_answer.upper(),
                "is_correct": is_correct,
                "score": score
            })
            
            session["current_question_index"] = question_index + 1
            
            return {
                "success": True,
                "is_correct": is_correct,
                "score_earned": score,
                "progress": {
                    "answered": len(session["answers"]),
                    "total": len(questions)
                }
            }
        
        except Exception as e:
            return {"success": False, "error": f"Failed to submit answer: {str(e)}"}
    
    def complete_quiz(self, session_id: str, user_id: str) -> Dict:
        """
        Complete a quiz and save results to database.
        
        Args:
            session_id: Session ID
            user_id: User UUID
            
        Returns:
            Dictionary with results, or error
        """
        try:
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}
            
            session = self.sessions[session_id]
            questions = session["questions"]
            unit_codes = session["unit_codes"]
            answers = session["answers"]
            
            # Calculate overall results
            total_questions = len(questions)
            correct_answers = sum(1 for a in answers if a["is_correct"])
            total_score = sum(a["score"] for a in answers)

            # Save quiz attempt to database. `passed` is a placeholder here -
            # it's finalized below once per-unit mastery has been computed.
            attempt_id = str(uuid4())
            now = datetime.now().isoformat()

            # Insert quiz attempt
            insert_attempt_query = """
            INSERT INTO quiz_attempts
            (id, user_id, score, passed, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """

            execute_query(
                insert_attempt_query,
                (
                    attempt_id,
                    user_id,
                    total_score,
                    False,
                    session.get("started_at"),
                    now
                )
            )
            
            # Insert per-question details
            for idx, (question, unit_code, answer) in enumerate(
                zip(questions, unit_codes, answers)
            ):
                # Get correct answer
                correct_choice_id = None
                for choice in question.choices:
                    if choice.is_correct:
                        correct_choice_id = choice.id
                        break
                
                detail_query = """
                INSERT INTO quiz_attempt_details
                (id, attempt_id, question_id, unit_code, bloom_level, 
                 selected_answer, correct_answer, is_correct, answered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                execute_query(
                    detail_query,
                    (
                        str(uuid4()),
                        attempt_id,
                        question.id,  # Use question ID from question object
                        unit_code,
                        question.bloom_level,
                        answer.get("selected_answer"),
                        correct_choice_id,
                        answer.get("is_correct"),
                        now
                    )
                )
            
            # Compute and persist per-unit mastery (highest correctly-answered
            # Bloom level vs. each unit's target level), then finalize the
            # overall pass/fail: PASS only if all six units are Mastered.
            unit_scores = {}
            is_passed = False
            try:
                mastery_results = self.mastery_service.compute_and_save_unit_mastery(attempt_id, user_id)
                is_passed = len(mastery_results) > 0 and all(
                    r["mastery_status"] == "Mastered" for r in mastery_results
                )
                execute_query(
                    "UPDATE quiz_attempts SET passed = %s WHERE id = %s",
                    (is_passed, attempt_id)
                )
                for r in mastery_results:
                    unit_scores[r["unit_code"]] = {
                        "score": r["unit_score"],
                        "max": 21,
                        "status": r["mastery_status"],
                        "is_mastered": r["mastery_status"] == "Mastered",
                        "unit_mastery_level": r["unit_mastery_level"],
                        "target_level": r["target_level"]
                    }
            except Exception as e:
                # Log but don't fail the entire quiz completion
                print(f"Warning: Failed to compute unit mastery for attempt {attempt_id}: {str(e)}")

            # Clean up session
            del self.sessions[session_id]

            return {
                "success": True,
                "attempt_id": attempt_id,
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "total_score": total_score,
                "max_possible_score": total_questions * 6,  # Max 6 points per question (C6)
                "is_passed": is_passed,
                "unit_mastery": unit_scores,
                "mastered_units": [u for u, d in unit_scores.items() if d["is_mastered"]],
                "remedial_units": [u for u, d in unit_scores.items() if not d["is_mastered"]]
            }
        
        except Exception as e:
            return {"success": False, "error": f"Failed to complete quiz: {str(e)}"}
    
    def get_user_quiz_history(self, user_id: str, limit: int = 10) -> Dict:
        """
        Get quiz attempt history for a user.
        
        Args:
            user_id: User UUID
            limit: Number of recent attempts to retrieve
            
        Returns:
            Dictionary with quiz history, or error
        """
        try:
            query = """
            SELECT id, started_at, completed_at, total_questions, correct_answers, total_score, pass_fail
            FROM quiz_attempts
            WHERE user_id = %s
            ORDER BY completed_at DESC
            LIMIT %s
            """
            
            results = execute_query(query, (user_id, limit), fetch=True)
            
            if not results:
                return {"success": True, "attempts": []}
            
            attempts = [
                {
                    "attempt_id": row[0],
                    "started_at": row[1],
                    "completed_at": row[2],
                    "total_questions": row[3],
                    "correct_answers": row[4],
                    "total_score": row[5],
                    "status": row[6]
                }
                for row in results
            ]
            
            return {"success": True, "attempts": attempts}
        
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve quiz history: {str(e)}"}

    def get_user_mastery_summary(self, user_id: str) -> Dict:
        """
        Get the user's mastery-level dashboard summary (for My Profile).

        Args:
            user_id: User UUID

        Returns:
            Dictionary with current_status, total_attempts, latest_attempt_date,
            and per-unit mastery data, or error
        """
        try:
            return self.mastery_service.get_user_mastery_summary(user_id)
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve mastery summary: {str(e)}"}
