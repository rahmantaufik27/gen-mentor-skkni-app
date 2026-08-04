"""
Service for computing and persisting per-unit mastery levels, and for
serving the mastery summary consumed by the My Profile dashboard.

The actual inference (how a unit's mastery level is derived from per-question
results) is delegated to a MasteryInferenceStrategy (see mastery_inference.py)
so it can be replaced later without changing persistence, the API contract,
or the dashboard.

Which strategy runs for a given user is decided by their inference_method
preference on the `users` table (see AuthenticationService.get_inference_method),
never by user_mastery_level. Only 'Manual' has a real implementation today;
'DBN' is read and honored as the preference, but resolves to the manual
strategy until the DBN engine is built (see _resolve_strategy below).
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
from services.neo4j_service import get_neo4j_service
from services.auth_service import AuthenticationService, INFERENCE_METHOD_MANUAL

# Canonical mastery_status values written to user_mastery_level and returned by the API
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
        self.targets, self.full_unit_codes = self._load_targets()

    def _load_targets(self) -> tuple:
        """
        Load from knowledge_target.json:
        - targets: truncated unit_code (3-segment, matches Postgres) -> target_level
        - full_unit_codes: truncated unit_code -> full unit_code (4-segment, matches
          the Unit.kode property already used by the Neo4j knowledge graph)
        """
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(backend_dir, "data", "knowledge_target.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        targets = {}
        full_unit_codes = {}
        for unit in data.get("units", []):
            truncated = _truncate_unit_code(unit["unit_code"])
            targets[truncated] = unit["target_level"]
            full_unit_codes[truncated] = unit["unit_code"]
        return targets, full_unit_codes

    def _resolve_strategy(self, user_id: str) -> MasteryInferenceStrategy:
        """
        Load the user's inference_method preference from the users table
        (requirement: read from users, never from user_mastery_level) and
        resolve it to the strategy that actually runs.

        Only 'Manual' has a working implementation today. 'DBN' is read and
        acknowledged, but until the DBN engine exists it falls back to the
        manual strategy so quiz completion keeps working for every user
        regardless of their setting. Wiring in a real DBN strategy later is
        a one-line change here - no schema or UI changes needed.
        """
        try:
            user_inference_method = AuthenticationService.get_inference_method(user_id)
        except Exception as e:
            print(f"Warning: Failed to load inference_method for user {user_id}: {str(e)}")
            user_inference_method = None

        print(f"Inference method for user {user_id}: {user_inference_method or '(unset, using default)'}")

        if user_inference_method == INFERENCE_METHOD_MANUAL:
            return ManualMasteryInference()
        # Covers 'DBN' and any unset/unrecognized value - manual is the
        # only working engine today.
        return self.inference_strategy

    def compute_and_save_unit_mastery(self, attempt_id: str, user_id: str) -> List[Dict]:
        """
        Derive each unit's mastery level from quiz_attempt_details for this
        attempt, compare against knowledge_target.json, and persist one
        user_mastery_level row per unit.

        Returns:
            Per-unit results: unit_code, unit_score, unit_mastery_level,
            target_level, mastery_status.
        """
        strategy = self._resolve_strategy(user_id)

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
            unit_mastery_level = strategy.infer_unit_mastery_level(bloom_correctness)
            unit_score = sum(
                QuizGenerator.BLOOM_SCORES.get(level, 0)
                for level, correct in bloom_correctness.items() if correct
            )
            # Mastered iff the learner's highest correct Bloom level meets or
            # exceeds this unit's required target_level from knowledge_target.json
            mastery_status = (
                MASTERED if bloom_level_rank(unit_mastery_level) >= bloom_level_rank(target_level)
                else REMEDIAL
            )

            execute_query(
                """
                INSERT INTO user_mastery_level
                (id, attempt_id, user_id, unit_code, unit_score, mastery_status, unit_mastery_level)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()), attempt_id, user_id, unit_code,
                    unit_score, mastery_status, unit_mastery_level
                )
            )

            # Best-effort sync to the Neo4j knowledge graph: (User)-[:MASTERY]->(Unit),
            # MERGEd so re-syncing the same user+unit updates rather than duplicates.
            # PostgreSQL above is already committed and remains the source of truth.
            # Uses the FULL unit code (Unit.kode in the existing knowledge graph),
            # not the truncated code used internally by Postgres.
            try:
                full_unit_code = self.full_unit_codes.get(unit_code, unit_code)
                get_neo4j_service().sync_mastery(
                    user_id, full_unit_code, unit_mastery_level, mastery_status, target_level
                )
            except Exception as e:
                print(f"Warning: Failed to sync mastery for {unit_code} to Neo4j: {str(e)}")

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
