"""
Service for computing and persisting per-unit mastery levels, and for
serving the mastery summary consumed by the My Profile dashboard.

The actual inference (how a unit's mastery level is derived from per-question
results) is delegated to a MasteryInferenceStrategy (see mastery_inference.py)
so it can be replaced later without changing persistence, the API contract,
or the dashboard.

Which strategy runs for a given user is decided by their inference_method
preference on the `users` table (see AuthenticationService.get_inference_method),
never by user_mastery_level. 'Manual' runs the rule-based strategy; 'DBN'
runs a per-unit Dynamic Bayesian Network (Forward Algorithm over
data/dbn_config.json's prior/transition/emission) - see resolve_strategy
below. resolve_strategy() is also called by PracticeService (Practice runs
the exact same Manual/DBN strategy over its own session data - see
services/practice_service.py::_save_practice_attempt - but never persists
to user_mastery_level). Both strategies consume the exact same per-unit
bloom_correctness data read from quiz_attempt_details, so this file's
query/persistence/Neo4j sync flow is identical regardless of which one runs.
resolve_strategy() returns one strategy object per call; every per-unit
inference goes through strategy.new_instance_for_unit(unit_code) first, so
DBN gets a fresh per-unit instance (see mastery_inference.py) and no
unit's observations/state can leak into another's.

Adaptive recommendations between Tests: get_effective_remedial_units()
(built on get_practice_mastered_units_since_last_test()) is the single
shared source PracticeService, MaterialsService, and the Practice
Analytics dashboard all read to decide what's still worth recommending -
a unit is Remedial per the latest Test AND not yet demonstrated Mastered
in Practice since that Test. This never writes to user_mastery_level or
Neo4j - Test remains the sole OFFICIAL mastery authority; it's a read-only
refinement layered on top using only the existing
practice_attempts/practice_attempt_units/quiz_attempts tables.
"""

import json
import os
from typing import Dict, List, Optional
from uuid import uuid4
from config.database import execute_query
from services.mastery_inference import (
    MasteryInferenceStrategy,
    ManualMasteryInference,
    DBNMasteryInference,
    bloom_level_rank,
)
from services.quiz_generator import QuizGenerator
from services.neo4j_service import get_neo4j_service
from services.auth_service import AuthenticationService, INFERENCE_METHOD_MANUAL, INFERENCE_METHOD_DBN

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

    def get_unit_code_map(self) -> Dict[str, str]:
        """
        Truncated (3-segment, Postgres-internal) -> full (4-segment, e.g.
        'J.620100.005.02') unit_code, for every unit in knowledge_target.json.
        Static/global (not user-specific) - the single source of truth the
        frontend uses to display full unit codes consistently everywhere,
        without changing what's actually stored internally (see
        _truncate_unit_code - Postgres/Neo4j sync/dashboards keep using the
        truncated code; only display is affected).
        """
        return dict(self.full_unit_codes)

    def resolve_strategy(self, user_id: str) -> MasteryInferenceStrategy:
        """
        Load the user's inference_method preference from the users table
        (requirement: read from users, never from user_mastery_level) and
        resolve it to the strategy that actually runs. Public: also called
        by PracticeService so Practice runs the identical Manual/DBN
        strategy Test does.

        'Manual' -> ManualMasteryInference (rule-based). 'DBN' ->
        DBNMasteryInference (per-unit Forward Algorithm - see
        mastery_inference.py). If DBN's config can't be loaded, or the
        preference is unset/unrecognized, falls back to the default
        strategy passed to __init__ (Manual) so quiz completion always
        keeps working.

        The returned object is a single strategy instance shared across
        every unit in the caller's loop - callers MUST call
        new_instance_for_unit(unit_code) on it before inferring each unit
        so DBN gets proper per-unit isolation (see
        mastery_inference.py::MasteryInferenceStrategy.new_instance_for_unit).
        """
        try:
            user_inference_method = AuthenticationService.get_inference_method(user_id)
        except Exception as e:
            print(f"Warning: Failed to load inference_method for user {user_id}: {str(e)}")
            user_inference_method = None

        print(f"Inference method for user {user_id}: {user_inference_method or '(unset, using default)'}")

        if user_inference_method == INFERENCE_METHOD_MANUAL:
            return ManualMasteryInference()
        if user_inference_method == INFERENCE_METHOD_DBN:
            try:
                return DBNMasteryInference()
            except Exception as e:
                print(f"Warning: Failed to initialize DBN inference for user {user_id}, falling back to default: {str(e)}")
                return self.inference_strategy
        # Unset/unrecognized preference - fall back to the default strategy.
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
        strategy = self.resolve_strategy(user_id)

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
            # Fresh per-unit instance (see new_instance_for_unit) - required
            # for DBN so each unit runs its own isolated DBN; a no-op for
            # Manual, which is stateless.
            unit_strategy = strategy.new_instance_for_unit(unit_code)
            unit_mastery_level = unit_strategy.infer_unit_mastery_level(bloom_correctness)
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

        # Adaptive set for the Practice Analytics dashboard's "Currently
        # Recommended" (also the shared basis for get_effective_remedial_units()
        # below, used by PracticeService/MaterialsService) - computed inline
        # from the `units` list already built above (no extra Test query),
        # deliberately kept separate from units[].mastery_status, which
        # stays Test-only so Test Analytics is never affected by Practice.
        test_remedial_units = {u["unit_code"] for u in units if u["mastery_status"] == REMEDIAL}
        effective_remedial_units = (
            sorted(test_remedial_units - self.get_practice_mastered_units_since_last_test(user_id))
            if latest_attempt else []
        )

        return {
            "success": True,
            "has_attempts": latest_attempt is not None,
            "total_attempts": total_attempts,
            "latest_attempt_date": latest_attempt[1].isoformat() if (latest_attempt and latest_attempt[1]) else None,
            "current_status": current_status,
            "units": units,
            "effective_remedial_units": effective_remedial_units,
        }

    def get_practice_mastered_units_since_last_test(self, user_id: str) -> set:
        """
        Truncated unit_codes the learner has demonstrated Mastered-level
        performance for IN PRACTICE (per the SAME Mastered/Remedial rule
        as Test - inferred level >= target_level) since their latest
        completed Test. Read-only: never writes to user_mastery_level or
        Neo4j - Test remains the sole OFFICIAL source of truth (see module
        docstring). A unit's inclusion here is dropped the moment a newer
        Test exists, since Test's fresh Neo4j sync then reflects that
        unit's true current status directly.
        """
        try:
            latest_test_rows = execute_query(
                "SELECT MAX(completed_at) FROM quiz_attempts WHERE user_id = %s AND completed_at IS NOT NULL",
                (user_id,),
                fetch=True,
            )
            latest_test_at = latest_test_rows[0][0] if latest_test_rows else None

            rows = execute_query(
                """
                SELECT pa.completed_at, pau.unit_code, pau.unit_mastery_level
                FROM practice_attempts pa
                JOIN practice_attempt_units pau ON pau.practice_attempt_id = pa.id
                WHERE pa.user_id = %s
                ORDER BY pa.completed_at DESC
                """,
                (user_id,),
                fetch=True,
            ) or []

            mastered_since_test: set = set()
            seen_units: set = set()
            for completed_at, unit_code, unit_mastery_level in rows:
                if unit_code in seen_units:
                    continue  # only the most recent Practice record per unit matters
                seen_units.add(unit_code)
                if latest_test_at and completed_at <= latest_test_at:
                    continue  # a Test has happened since - defer entirely to Neo4j's fresh status
                target = self.targets.get(unit_code)
                if target and bloom_level_rank(unit_mastery_level) >= bloom_level_rank(target):
                    mastered_since_test.add(unit_code)
            return mastered_since_test
        except Exception as e:
            print(f"Warning: Failed to compute practice-mastered units for user {user_id}: {str(e)}")
            return set()

    def get_effective_remedial_units(self, user_id: str) -> List[str]:
        """
        Truncated unit_codes that are Remedial per the latest Test AND not
        yet Practice-Mastered since that Test - the adaptive recommendation
        set driving Practice, Reading Materials, and the Practice Analytics
        dashboard's "Currently Recommended" between Tests. The Placement
        Test (or any Test) is the baseline; from the first Practice session
        onward, this set narrows as units are demonstrated Mastered in
        Practice, until the next Test re-evaluates everything.

        Public entry point for other services (MaterialsService,
        PracticeService) - delegates to get_user_mastery_summary(), which
        computes this same set inline while building the dashboard payload,
        so there's exactly one implementation and no duplicate queries.

        Returns:
            Sorted list of truncated unit_codes (empty if the user has
            never completed a Test, or if every unit is already covered).
        """
        summary = self.get_user_mastery_summary(user_id)
        return summary.get("effective_remedial_units", [])
