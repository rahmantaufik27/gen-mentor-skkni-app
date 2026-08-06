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
from services.neo4j_service import get_neo4j_service


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
        self.neo4j_service = get_neo4j_service()
        # In-memory cache for active (in-progress) sessions only - not persisted,
        # so an in-progress quiz is lost if the server restarts. Completed
        # attempts are durable (written to Postgres in complete_quiz()).
        self.sessions = {}
    
    def start_quiz(self, user_id: str) -> Dict:
        """
        Start a new quiz session for a user. A Test is taken exactly ONCE,
        ever - refuses to start a second one if the user already has a
        completed attempt, regardless of pass/fail (see utils/gating.py on
        the frontend for the matching UI-side rule; this is the
        server-side enforcement of the same one-time rule). Practice is
        the sole ongoing mechanism afterward.

        Args:
            user_id: UUID of the user

        Returns:
            Dictionary with session info and first question, or error
        """
        try:
            existing_attempt = execute_query(
                "SELECT id FROM quiz_attempts WHERE user_id = %s AND completed_at IS NOT NULL LIMIT 1",
                (user_id,),
                fetch=True,
            )
            if existing_attempt:
                return {
                    "success": False,
                    "error": "You have already completed your Test - it can only be taken once. Head to Practice to keep improving.",
                }

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
        Get quiz attempt history for a user, including a detailed
        per-question review for each attempt (question number, unit,
        Bloom/Knowledge Level, the learner's answer, correctness) - the
        same shape Practice's Review Practice uses (see
        PracticeService._build_review), so Test History and Practice
        Review share one consistent layout on the frontend.

        quiz_attempt_details has no explicit sequence column, so each
        attempt's original question order is recovered deterministically
        from QuizGenerator.PREFERRED_UNITS + BLOOM_LEVELS - the exact
        fixed order generate_quiz() used to build it in the first place.

        Args:
            user_id: User UUID
            limit: Number of recent attempts to retrieve

        Returns:
            Dictionary with attempts: [{attempt_id, started_at,
            completed_at, total_questions, correct_answers, total_score,
            status, review}], or error
        """
        try:
            query = """
            SELECT id, started_at, completed_at, score, passed
            FROM quiz_attempts
            WHERE user_id = %s
            ORDER BY completed_at DESC NULLS LAST, started_at DESC
            LIMIT %s
            """
            results = execute_query(query, (user_id, limit), fetch=True)

            if not results:
                return {"success": True, "attempts": []}

            unit_order = {unit: i for i, unit in enumerate(QuizGenerator.PREFERRED_UNITS)}
            bloom_order = {level: i for i, level in enumerate(QuizGenerator.BLOOM_LEVELS)}

            attempts = []
            for attempt_id, started_at, completed_at, score, passed in results:
                detail_rows = execute_query(
                    """
                    SELECT question_id, unit_code, bloom_level, selected_answer, correct_answer, is_correct
                    FROM quiz_attempt_details
                    WHERE attempt_id = %s
                    """,
                    (attempt_id,),
                    fetch=True,
                ) or []
                detail_rows.sort(key=lambda r: (
                    unit_order.get(r[1], len(unit_order)),
                    bloom_order.get((r[2] or "").upper(), len(bloom_order)),
                ))

                review = []
                correct_answers = 0
                for idx, (question_id, unit_code, bloom_level, selected_answer, _correct_answer, is_correct) in enumerate(detail_rows):
                    if is_correct:
                        correct_answers += 1
                    question = self.question_loader.get_question_by_id(question_id)
                    selected_choice = next((c for c in question.choices if c.id == selected_answer), None) if question else None
                    user_answer = f"{selected_choice.id}. {selected_choice.text}" if selected_choice else (selected_answer or "-")
                    review.append({
                        "question_number": idx + 1,
                        "unit_code": unit_code,
                        "bloom_level": bloom_level,
                        "user_answer": user_answer,
                        "is_correct": bool(is_correct),
                    })

                attempts.append({
                    "attempt_id": attempt_id,
                    "started_at": started_at.isoformat() if started_at else None,
                    "completed_at": completed_at.isoformat() if completed_at else None,
                    "total_questions": len(detail_rows),
                    "correct_answers": correct_answers,
                    "total_score": score,
                    "status": "PASS" if passed else "FAIL",
                    "review": review,
                })

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

    def get_unit_code_map(self) -> Dict:
        """
        Get the truncated -> full unit_code map (static/global, not
        user-specific) so the frontend can display full unit codes
        consistently (e.g. 'J.620100.005.02') wherever a unit_code appears.

        Returns:
            Dictionary with a "unit_codes" map, or error
        """
        try:
            return {"success": True, "unit_codes": self.mastery_service.get_unit_code_map()}
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve unit code map: {str(e)}"}

    def get_recommended_questions(self, user_id: str) -> Dict:
        """
        Get practice questions recommended from the Neo4j knowledge graph:
        questions (Evaluation nodes) for Remedial units at the user's current
        knowledge level for that unit. The existing knowledge graph already
        holds full question text/options (it was built from the same
        question bank), so no separate lookup is needed here - which option
        is correct is intentionally left out of the response.

        Args:
            user_id: User UUID

        Returns:
            Dictionary with a "questions" list, or error
        """
        try:
            recommendations = self.neo4j_service.get_recommended_questions(user_id)

            questions = [
                {
                    "id": rec.get("question_id"),
                    "question_text": rec.get("question_text"),
                    "unit": rec.get("unit_code"),
                    "bloom_level": rec.get("bloom_level"),
                    "options": rec.get("options", []),
                    "mastery_status": rec.get("mastery_status"),
                    "target_level": rec.get("target_level"),
                }
                for rec in recommendations
            ]

            return {"success": True, "questions": questions}
        except Exception as e:
            return {"success": False, "error": f"Failed to retrieve recommended questions: {str(e)}"}
