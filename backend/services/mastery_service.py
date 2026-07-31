"""
Service for computing and persisting per-unit mastery levels, and for
serving the mastery summary consumed by the My Profile dashboard.

The actual inference (how a unit's mastery level is derived from per-question
results) is delegated to a MasteryInferenceStrategy (see mastery_inference.py)
so it can be replaced later without changing persistence, the API contract,
or the dashboard.
"""

import json
import os
from typing import Dict, List, Optional
from uuid import uuid4
from config.database import execute_query
from services.mastery_inference import (
    MasteryInferenceStrategy,
    ManualMasteryInference,
    bloom_level_rank,
)
from services.quiz_generator import QuizGenerator

MASTERED = "Mastered"
REMEDIAL = "Remedial"


def _truncate_unit_code(unit_code: str) -> str:
    """Reduce a full unit code (e.g. 'J.620100.010.01') to its 3-segment main code."""
    parts = unit_code.split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else unit_code


def _normalize_status(status: Optional[str]) -> str:
    """Normalize a mastery_status value (handles legacy 'MASTERED'/'REMEDIAL' rows)."""
    return MASTERED if (status or "").strip().upper() == "MASTERED" else REMEDIAL


class MasteryService:
    """Computes/persists per-unit mastery levels and reads back dashboard summaries."""

    def __init__(self, inference_strategy: Optional[MasteryInferenceStrategy] = None):
        self.inference_strategy = inference_strategy or ManualMasteryInference()
        self.targets = self._load_targets()

    def _load_targets(self) -> Dict[str, str]:
        """Load unit_code -> target_level (Bloom) from knowledge_target.json."""
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(backend_dir, "data", "knowledge_target.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            _truncate_unit_code(unit["unit_code"]): unit["target_level"]
            for unit in data.get("units", [])
        }

    def compute_and_save_unit_mastery(self, attempt_id: str, user_id: str) -> List[Dict]:
        """
        Derive each unit's mastery level from quiz_attempt_details for this
        attempt, compare against knowledge_target.json, and persist one
        user_mastery_level row per unit.

        Returns:
            Per-unit results: unit_code, unit_score, unit_mastery_level,
            target_level, mastery_status.
        """
        rows = execute_query(
            "SELECT unit_code, bloom_level, is_correct FROM quiz_attempt_details WHERE attempt_id = %s",
            (attempt_id,),
            fetch=True
        ) or []

        by_unit: Dict[str, Dict[str, bool]] = {}
        for unit_code, bloom_level, is_correct in rows:
            by_unit.setdefault(unit_code, {})[bloom_level.upper()] = bool(is_correct)

        results = []
        for unit_code, target_level in self.targets.items():
            bloom_correctness = by_unit.get(unit_code, {})
            unit_mastery_level = self.inference_strategy.infer_unit_mastery_level(bloom_correctness)
            unit_score = sum(
                QuizGenerator.BLOOM_SCORES.get(level, 0)
                for level, correct in bloom_correctness.items() if correct
            )
            mastery_status = (
                MASTERED if bloom_level_rank(unit_mastery_level) >= bloom_level_rank(target_level)
                else REMEDIAL
            )

            execute_query(
                """
                INSERT INTO user_mastery_level
                (id, attempt_id, user_id, unit_code, unit_score, mastery_status, unit_mastery_level, method)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()), attempt_id, user_id, unit_code,
                    unit_score, mastery_status, unit_mastery_level, self.inference_strategy.method_name
                )
            )

            results.append({
                "unit_code": unit_code,
                "unit_score": unit_score,
                "unit_mastery_level": unit_mastery_level,
                "target_level": target_level,
                "mastery_status": mastery_status
            })

        return results

    def get_user_mastery_summary(self, user_id: str) -> Dict:
        """
        Build the My Profile mastery dashboard payload for a user.

        Always returns all units from knowledge_target.json, defaulting any
        unit missing from the latest attempt to unit_score=0 / Remedial, so
        the dashboard renders unconditionally even for a user who has never
        taken a quiz.
        """
        attempt_rows = execute_query(
            """
            SELECT id, completed_at, passed FROM quiz_attempts
            WHERE user_id = %s
            ORDER BY completed_at DESC NULLS LAST, started_at DESC
            LIMIT 1
            """,
            (user_id,),
            fetch=True
        )
        latest_attempt = attempt_rows[0] if attempt_rows else None

        total_attempts_rows = execute_query(
            "SELECT COUNT(*) FROM quiz_attempts WHERE user_id = %s",
            (user_id,),
            fetch=True
        )
        total_attempts = total_attempts_rows[0][0] if total_attempts_rows else 0

        unit_rows_by_code: Dict[str, Dict] = {}
        if latest_attempt:
            attempt_id = latest_attempt[0]
            mastery_rows = execute_query(
                """
                SELECT unit_code, unit_score, unit_mastery_level, mastery_status
                FROM user_mastery_level
                WHERE attempt_id = %s
                """,
                (attempt_id,),
                fetch=True
            ) or []
            for unit_code, unit_score, unit_mastery_level, mastery_status in mastery_rows:
                unit_rows_by_code[unit_code] = {
                    "unit_score": unit_score,
                    "unit_mastery_level": unit_mastery_level,
                    "mastery_status": _normalize_status(mastery_status)
                }

        units = []
        for unit_code, target_level in self.targets.items():
            row = unit_rows_by_code.get(unit_code)
            if row:
                units.append({
                    "unit_code": unit_code,
                    "unit_score": row["unit_score"],
                    "unit_mastery_level": row["unit_mastery_level"],
                    "target_level": target_level,
                    "mastery_status": row["mastery_status"]
                })
            else:
                units.append({
                    "unit_code": unit_code,
                    "unit_score": 0,
                    "unit_mastery_level": None,
                    "target_level": target_level,
                    "mastery_status": REMEDIAL
                })

        current_status = "PASS" if (latest_attempt and latest_attempt[2]) else "FAIL"

        return {
            "success": True,
            "has_attempts": latest_attempt is not None,
            "total_attempts": total_attempts,
            "latest_attempt_date": latest_attempt[1].isoformat() if (latest_attempt and latest_attempt[1]) else None,
            "current_status": current_status,
            "units": units
        }
