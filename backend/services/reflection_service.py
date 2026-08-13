"""
Learning Reflection service.

Standalone module for the Learning Reflection feature. Two responsibilities:

  1. Serve the reflection QUESTION CONFIG from data/reflection_questions.json
     (the single source of truth for question text/keys/types). Questions may
     change dynamically - only the stable question_key is ever persisted, never
     the text, so stored answers stay valid across wording changes.

  2. CRUD a user's ANSWERS in its own user_reflections table (one row per
     user+question_key, upserted on edit). Every query is scoped to user_id, so
     one user can never read or write another user's reflection data.

Additive and independent: it reads/writes only its own table and its own config
file; nothing else in the app has to change for it to work.
"""

import json
import os
from typing import Dict, Optional

from config.database import execute_query

# question_key -> question config, built once from the JSON on first use.
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "reflection_questions.json",
)


class ReflectionService:
    """Config-backed reflection questions + per-user answer storage."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or _CONFIG_PATH
        self._config = None  # lazy-loaded

    # -- Config ------------------------------------------------------------

    def _load_config(self) -> Dict:
        if self._config is None:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        return self._config

    def get_questions(self) -> Dict:
        """
        Return the reflection question configuration (sections + questions),
        exactly as authored in data/reflection_questions.json.
        """
        try:
            config = self._load_config()
            return {"success": True, **config}
        except Exception as e:
            return {"success": False, "error": f"Failed to load reflection questions: {str(e)}"}

    def _question_index(self) -> Dict[str, Dict]:
        """Flatten config to {question_key: question_dict} for validation/typing."""
        index = {}
        for section in self._load_config().get("sections", []):
            for q in section.get("questions", []):
                index[q["key"]] = q
        return index

    # -- Answers -----------------------------------------------------------

    def get_answers(self, user_id: str) -> Dict:
        """
        Return all of a user's saved answers keyed by question_key. Scoped to
        user_id, so it only ever returns that user's own reflections.

        Returns:
            {"success": True, "answers": {question_key: {answer_text,
             answer_number, created_at, updated_at}}}
        """
        try:
            rows = execute_query(
                """
                SELECT question_key, answer_text, answer_number, created_at, updated_at
                FROM user_reflections WHERE user_id = %s
                """,
                (user_id,),
                fetch=True,
            ) or []
            answers = {
                qkey: {
                    "answer_text": answer_text,
                    "answer_number": answer_number,
                    "created_at": created_at.isoformat() if created_at else None,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                }
                for qkey, answer_text, answer_number, created_at, updated_at in rows
            }
            return {"success": True, "answers": answers}
        except Exception as e:
            return {"success": False, "error": f"Failed to load reflection answers: {str(e)}"}

    def save_answer(
        self,
        user_id: str,
        question_key: str,
        answer_text: Optional[str] = None,
        answer_number: Optional[int] = None,
    ) -> Dict:
        """
        Create or update (upsert) a user's answer to one configured question.

        Validates question_key against the config and enforces the question's
        type (a 'rating' question requires a numeric answer within its
        min/max; a 'text' question requires non-empty text).
        """
        try:
            index = self._question_index()
            question = index.get(question_key)
            if not question:
                return {"success": False, "error": f"Unknown question_key '{question_key}'"}

            qtype = question.get("type", "text")
            norm_text: Optional[str] = None
            norm_number: Optional[int] = None

            if qtype == "rating":
                if answer_number is None:
                    return {"success": False, "error": "A numeric answer is required for this question"}
                try:
                    norm_number = int(answer_number)
                except (TypeError, ValueError):
                    return {"success": False, "error": "Answer must be a whole number"}
                lo, hi = int(question.get("min", 1)), int(question.get("max", 5))
                if not (lo <= norm_number <= hi):
                    return {"success": False, "error": f"Answer must be between {lo} and {hi}"}
            else:
                norm_text = (answer_text or "").strip()
                if not norm_text:
                    return {"success": False, "error": "Answer cannot be empty"}

            execute_query(
                """
                INSERT INTO user_reflections (user_id, question_key, answer_text, answer_number)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, question_key)
                DO UPDATE SET answer_text = EXCLUDED.answer_text,
                              answer_number = EXCLUDED.answer_number,
                              updated_at = NOW()
                """,
                (user_id, question_key, norm_text, norm_number),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to save reflection answer: {str(e)}"}

    def delete_answer(self, user_id: str, question_key: str) -> Dict:
        """Delete a single answer for this user + question_key (scoped to the user)."""
        if not question_key:
            return {"success": False, "error": "question_key is required"}
        try:
            execute_query(
                "DELETE FROM user_reflections WHERE user_id = %s AND question_key = %s",
                (user_id, question_key),
            )
            return {"success": True, "deleted": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete reflection answer: {str(e)}"}
