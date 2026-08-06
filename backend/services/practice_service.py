"""
Practice service: an interactive, Test-like session over questions
recommended for the user's weakest units - same recommendation flow as
GET /api/quiz/recommended-questions (Neo4jService.get_recommended_questions).

Mirrors QuizService's in-memory session pattern (start/get_question/
submit_answer/complete) for UI/UX parity with Test, and is intentionally
kept separate from quiz_attempts/user_mastery_level - Practice never writes
mastery data, Test remains the sole source of mastery truth (see
services/mastery_service.py). This keeps the existing Test logic/flow
completely untouched.

On completion, a lightweight session summary (practice_attempts /
practice_attempt_units - see migrations/004_create_practice_attempts_table.py)
is best-effort persisted purely to back the Practice Analytics section of
the My Profile dashboard (total sessions, per-unit Knowledge Level
progression) and the Review Practice screen. A persistence failure never
breaks the practice flow itself.

Per-unit Knowledge Level is inferred by the SAME MasteryInferenceStrategy
Test uses (Manual or DBN, per the user's inference_method preference - see
MasteryService.resolve_strategy), applied unchanged to this session's own
ordered observations - across the FULL C1-C6 Bloom range (never capped at
target_level, see neo4j_service.get_recommended_questions), so every
response genuinely contributes evidence across the DBN's whole hidden-state
space. This keeps Test and Practice using one inference implementation
while writing to completely separate tables.

Session-to-session adaptivity: once a unit's Practice-inferred level meets
its target (Mastered, by the exact same rule as Test - see
MasteryService MASTERED/REMEDIAL), that unit is excluded from every
subsequent Practice session (see
MasteryService.get_practice_mastered_units_since_last_test, the single
shared implementation also used by MaterialsService and the Practice
Analytics dashboard) - Neo4j's MASTERY.mastery_status (Test-driven)
remains the sole OFFICIAL source of truth and is never written to by
Practice; this is a read-only refinement layered on top, using only the
existing practice_attempts/practice_attempt_units/quiz_attempts tables.
The Test itself is a one-time event (see QuizService.start_quiz - it can
never be retaken), so Practice is the sole ongoing mechanism for the rest
of the user's lifetime once it's done.
"""

import re
from typing import Dict, List, Optional, Tuple
from uuid import uuid4
from datetime import datetime

from config.database import execute_query
from services.neo4j_service import get_neo4j_service
from services.quiz_generator import QuizGenerator
from services.mastery_inference import bloom_level_rank
from services.mastery_service import MasteryService

# Parses an option/answer string like "B. Progress Bar" into id="B", text="Progress Bar"
_OPTION_RE = re.compile(r"^\s*([A-Za-z])[\.\)]\s*(.*)$")


def _parse_option(text: Optional[str]) -> Dict:
    match = _OPTION_RE.match(text or "")
    if match:
        return {"id": match.group(1).upper(), "text": match.group(2)}
    return {"id": "?", "text": text or ""}


def _truncate_unit_code(unit_code: Optional[str]) -> str:
    """Reduce a full unit code (e.g. 'J.620100.010.01') to its 3-segment main
    code, matching the convention used by Postgres/Test (see
    mastery_service._truncate_unit_code)."""
    parts = (unit_code or "").split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else (unit_code or "")


class PracticeService:
    """Service for practice-session operations."""

    def __init__(self, neo4j_service=None, mastery_service=None):
        self.neo4j_service = neo4j_service or get_neo4j_service()
        self.mastery_service = mastery_service or MasteryService()
        self.sessions = {}  # In-memory only, same pattern/caveats as QuizService.sessions

    def start_practice(self, user_id: str) -> Dict:
        """
        Build a practice session from the user's recommended questions -
        Remedial units only (see neo4j_service.get_recommended_questions,
        which filters on the MASTERY relationship's mastery_status,
        excluding Mastered units), across the full C1-C6 range for each.

        On top of that, units the learner has already reached target on
        IN PRACTICE since their Test are excluded too (see
        MasteryService.get_practice_mastered_units_since_last_test) - e.g.
        if Unit A is inferred Mastered in Practice session 1, it won't
        appear in session 2 (the Test itself can't be retaken to reset
        this - see QuizService.start_quiz).

        Returns:
            Dictionary with session info and first question, or error.
            On failure, includes all_mastered (True only when every unit
            is genuinely Mastered per Test - see _no_questions_response)
            so the frontend can show an accurate message distinct from
            other reasons the pool might be empty.
        """
        try:
            records = self.neo4j_service.get_recommended_questions(user_id)

            practice_mastered = self.mastery_service.get_practice_mastered_units_since_last_test(user_id)
            excluded_by_practice = False
            if practice_mastered:
                filtered = [r for r in records if _truncate_unit_code(r.get("unit_code")) not in practice_mastered]
                excluded_by_practice = len(filtered) < len(records)
                records = filtered

            if not records:
                return self._no_questions_response(user_id, excluded_by_practice=excluded_by_practice)

            questions = []
            for rec in records:
                options = [_parse_option(opt) for opt in (rec.get("options") or [])]
                correct = _parse_option(rec.get("correct_answer_text"))
                questions.append({
                    "question_id": rec.get("question_id"),
                    "question_text": rec.get("question_text"),
                    "unit_code": rec.get("unit_code"),
                    "bloom_level": rec.get("bloom_level"),
                    "options": options,
                    "correct_option_id": correct["id"],
                })

            session_id = str(uuid4())
            self.sessions[session_id] = {
                "user_id": user_id,
                "questions": questions,
                "answers": [],  # [{"question_index", "selected_answer", "is_correct", "score"}]
                "started_at": datetime.now().isoformat(),
            }

            return {
                "success": True,
                "session_id": session_id,
                "total_questions": len(questions),
                "current_question": self._public_question(questions[0], 0, len(questions)),
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to start practice: {str(e)}"}

    def _no_questions_response(self, user_id: str, excluded_by_practice: bool = False) -> Dict:
        """
        Build the error response for an empty recommended-questions pool,
        distinguishing three real cases so the frontend can show an
        accurate message instead of always claiming "great job". The Test
        is a one-time event (see QuizService.start_quiz) - none of these
        messages ever point the learner back at "another Test", since
        there isn't one; Practice is the sole ongoing mechanism once the
        Test is done:
        - Every unit is genuinely Mastered per Test (has_attempts and all
          units' mastery_status == "Mastered") -> all_mastered=True, a
          congratulatory message with no further CTA.
        - Some Remedial units remain per Test, but every one of them was
          already excluded by MasteryService.get_practice_mastered_units_since_last_test
          (excluded_by_practice=True) -> distinct message noting they're
          already at target for now.
        - Any other reason (e.g. a Remedial unit with no eligible question
          data) -> an honest "try again later" message.
        """
        try:
            summary = self.mastery_service.get_user_mastery_summary(user_id)
            all_mastered = bool(
                summary.get("success") and summary.get("has_attempts")
                and summary.get("units")
                and all(u.get("mastery_status") == "Mastered" for u in summary["units"])
            )
        except Exception:
            all_mastered = False

        if all_mastered:
            return {
                "success": False,
                "all_mastered": True,
                "error": (
                    "All your units are currently Mastered - congratulations! "
                    "There are no Practice recommendations right now."
                ),
            }
        if excluded_by_practice:
            return {
                "success": False,
                "all_mastered": False,
                "error": (
                    "You've already reached target level in Practice for your remaining "
                    "Remedial units. Great progress - check back after practicing your "
                    "other units, or come back to this one again soon."
                ),
            }
        return {
            "success": False,
            "all_mastered": False,
            "error": "No practice questions are available for your units right now. Please try again later.",
        }

    @staticmethod
    def _public_question(question: Dict, index: int, total: int) -> Dict:
        """Question shape sent to the client - never includes correct_option_id."""
        return {
            "question_number": index + 1,
            "total_questions": total,
            "question_text": question["question_text"],
            "unit": question["unit_code"],
            "bloom_level": question["bloom_level"],
            "choices": [{"id": o["id"], "text": o["text"]} for o in question["options"]],
        }

    def get_question(self, session_id: str, question_index: int) -> Dict:
        """
        Get a specific question from an active practice session.

        Returns:
            Dictionary with question data, or error
        """
        try:
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}

            questions = self.sessions[session_id]["questions"]
            if question_index < 0 or question_index >= len(questions):
                return {"success": False, "error": "Invalid question index"}

            return {"success": True, **self._public_question(questions[question_index], question_index, len(questions))}
        except Exception as e:
            return {"success": False, "error": f"Failed to get question: {str(e)}"}

    def submit_answer(self, session_id: str, question_index: int, selected_answer: str) -> Dict:
        """
        Submit an answer for a question, checked server-side against the
        correct option resolved at start_practice() time.

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
            is_correct = selected_answer.upper() == question["correct_option_id"]
            score = QuizGenerator.BLOOM_SCORES.get(question["bloom_level"], 0) if is_correct else 0

            session["answers"].append({
                "question_index": question_index,
                "selected_answer": selected_answer.upper(),
                "is_correct": is_correct,
                "score": score,
            })

            return {
                "success": True,
                "is_correct": is_correct,
                "score_earned": score,
                "progress": {
                    "answered": len(session["answers"]),
                    "total": len(questions),
                },
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to submit answer: {str(e)}"}

    def complete_practice(self, session_id: str) -> Dict:
        """
        Finish a practice session and return the summary, the per-question
        Review Practice table, and each covered unit's inferred Knowledge
        Level. Never touches mastery_status/quiz_attempts - Test remains
        the sole source of mastery truth. The session summary/unit levels
        are saved separately (see _save_practice_attempt) on a best-effort
        basis purely for the Practice Analytics dashboard and Review
        Practice screen; a failure there never breaks this response.

        Returns:
            Dictionary with results, review, and unit_mastery, or error
        """
        try:
            if session_id not in self.sessions:
                return {"success": False, "error": "Session not found"}

            session = self.sessions[session_id]
            user_id = session["user_id"]
            questions = session["questions"]
            answers = session["answers"]

            total_questions = len(questions)
            correct_answers = sum(1 for a in answers if a["is_correct"])
            total_score = sum(a["score"] for a in answers)
            max_possible_score = sum(QuizGenerator.BLOOM_SCORES.get(q["bloom_level"], 0) for q in questions)

            review = self._build_review(questions, answers)

            unit_mastery: Dict[str, Optional[str]] = {}
            try:
                unit_mastery = self._save_practice_attempt(
                    user_id, questions, answers, total_questions, correct_answers, total_score, max_possible_score
                )
            except Exception as e:
                print(f"Warning: Failed to save practice attempt summary for user {user_id}: {str(e)}")

            del self.sessions[session_id]

            return {
                "success": True,
                "total_questions": total_questions,
                "correct_answers": correct_answers,
                "total_score": total_score,
                "max_possible_score": max_possible_score,
                "review": review,
                "unit_mastery": unit_mastery,
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to complete practice: {str(e)}"}

    @staticmethod
    def _build_review(questions: List[Dict], answers: List[Dict]) -> List[Dict]:
        """
        Per-question Review Practice rows, in quiz order: question number,
        unit, the question's own Bloom/Knowledge Level, the learner's
        answer, and correctness.
        """
        answers_by_index = {a["question_index"]: a for a in answers}
        review = []
        for idx, question in enumerate(questions):
            answer = answers_by_index.get(idx)
            selected_id = answer["selected_answer"] if answer else None
            selected_option = next((o for o in question["options"] if o["id"] == selected_id), None)
            review.append({
                "question_number": idx + 1,
                "unit_code": _truncate_unit_code(question["unit_code"]),
                "bloom_level": question["bloom_level"],
                "user_answer": f"{selected_option['id']}. {selected_option['text']}" if selected_option else "-",
                "is_correct": bool(answer and answer["is_correct"]),
            })
        return review

    def _save_practice_attempt(
        self, user_id: str, questions: List[Dict], answers: List[Dict],
        total_questions: int, correct_answers: int, total_score: int, max_possible_score: int,
    ) -> Dict[str, Optional[str]]:
        """
        Infer each covered unit's Knowledge Level via the SAME
        MasteryInferenceStrategy Test uses (Manual or DBN - see
        MasteryService.resolve_strategy), then persist a session summary to
        practice_attempts / practice_attempt_units (see
        migrations/004_create_practice_attempts_table.py). A session
        snapshot only, distinct from and never written to
        user_mastery_level.

        Each unit's observations are its own answered questions in quiz
        order (may repeat the same Bloom level - Practice, unlike Test,
        can serve several questions at one unit's current level in a
        single session) - kept fully separate per unit via
        strategy.new_instance_for_unit(unit_code), so no unit's
        observations/state ever mix with another's.

        Returns:
            {unit_code: inferred_level} for every unit covered this
            session (level is None only if that unit's strategy found
            nothing to infer from, e.g. Manual with zero correct answers).
        """
        observations_by_unit: Dict[str, List[Tuple[str, bool]]] = {}
        answers_by_index = {a["question_index"]: a for a in answers}
        for idx, question in enumerate(questions):
            answer = answers_by_index.get(idx)
            if not answer:
                continue
            unit_code = _truncate_unit_code(question["unit_code"])
            observations_by_unit.setdefault(unit_code, []).append((question["bloom_level"], answer["is_correct"]))

        strategy = self.mastery_service.resolve_strategy(user_id)
        unit_mastery: Dict[str, Optional[str]] = {}
        for unit_code, observations in observations_by_unit.items():
            unit_strategy = strategy.new_instance_for_unit(unit_code)
            unit_mastery[unit_code] = unit_strategy.infer_from_observations(observations)

        attempt_id = str(uuid4())
        execute_query(
            """
            INSERT INTO practice_attempts
            (id, user_id, total_questions, correct_answers, total_score, max_possible_score)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (attempt_id, user_id, total_questions, correct_answers, total_score, max_possible_score),
        )
        for unit_code, level in unit_mastery.items():
            if level is None:
                continue
            execute_query(
                """
                INSERT INTO practice_attempt_units (id, practice_attempt_id, unit_code, unit_mastery_level)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid4()), attempt_id, unit_code, level),
            )

        return unit_mastery

    def get_practice_analytics(self, user_id: str) -> Dict:
        """
        Build the Practice Analytics dashboard payload for a user: total
        completed sessions and the per-unit Knowledge Level progression
        (one point per session per unit covered) for the line chart.

        Returns:
            Dictionary with total_sessions and a progression list of
            {completed_at, unit_code, unit_mastery_level, level_rank}
        """
        try:
            total_rows = execute_query(
                "SELECT COUNT(*) FROM practice_attempts WHERE user_id = %s",
                (user_id,),
                fetch=True,
            )
            total_sessions = total_rows[0][0] if total_rows else 0

            rows = execute_query(
                """
                SELECT pa.completed_at, pau.unit_code, pau.unit_mastery_level
                FROM practice_attempts pa
                JOIN practice_attempt_units pau ON pau.practice_attempt_id = pa.id
                WHERE pa.user_id = %s
                ORDER BY pa.completed_at ASC
                """,
                (user_id,),
                fetch=True,
            ) or []

            progression = [
                {
                    "completed_at": completed_at.isoformat() if completed_at else None,
                    "unit_code": unit_code,
                    "unit_mastery_level": unit_mastery_level,
                    "level_rank": bloom_level_rank(unit_mastery_level),
                }
                for completed_at, unit_code, unit_mastery_level in rows
            ]

            return {"success": True, "total_sessions": total_sessions, "progression": progression}
        except Exception as e:
            return {"success": False, "error": f"Failed to load practice analytics: {str(e)}"}
