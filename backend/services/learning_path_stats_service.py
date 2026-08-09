"""
Learning Path statistics service.

Lightweight, read-mostly aggregation for the Learning Path dashboard. It pulls
together, per user:

  - Latest & average Practice score          (from practice_attempts)
  - Mastered vs Remedial unit counts         (from MasteryService, Test-driven)
  - Materials viewed/completed count + latest activity   (from user_activity)
  - Chatbot attempts count + latest interaction          (from user_activity)
  - Latest Practice interaction timestamp    (from practice_attempts)

Design goals (per task): modular, lightweight, easy to use, and independent so
new metrics can be added without changing the frontend interface.

  - Counters and "latest interaction" timestamps are backed by a single generic
    append-only event log (user_activity - see migrations/005). Any new
    countable/timestamped activity is just another activity_type: call
    record_activity(user_id, "<new_type>") from wherever it happens, then read
    it back in get_learning_path_stats() - no schema or frontend-contract change.
  - get_learning_path_stats() returns a flat dict that callers read by key, so
    adding a key is backwards-compatible: existing frontend code keeps working.
  - This service never writes to Test/mastery tables; it only reads them and
    appends to its own user_activity log. It touches no Neo4j and no user model.
"""

from typing import Dict, Optional
from uuid import uuid4
import json

from config.database import execute_query
from services.mastery_service import MasteryService, MASTERED

# Well-known activity types. New metrics can add their own without touching
# anything here except (optionally) a convenience constant.
ACTIVITY_MATERIAL_VIEW = "material_view"
ACTIVITY_CHATBOT_PROMPT = "chatbot_prompt"


class LearningPathStatsService:
    """Aggregates Learning Path metrics and records lightweight activity events."""

    def __init__(self, mastery_service: Optional[MasteryService] = None):
        # MasteryService is Postgres-only (no Neo4j) and is the single source
        # of truth for Mastered/Remedial - reused here, not reimplemented.
        self.mastery_service = mastery_service or MasteryService()

    # -- Recording ---------------------------------------------------------

    def record_activity(self, user_id: str, activity_type: str, metadata: Optional[Dict] = None) -> Dict:
        """
        Append one activity event. Used for every counter/latest-timestamp
        metric (materials opened, chatbot prompts, and any future one).

        Kept intentionally generic so a new metric needs no new endpoint:
        pass its own activity_type string. `metadata` is optional per-event
        detail (stored as JSONB) for metrics that want it later.
        """
        if not activity_type or not isinstance(activity_type, str):
            return {"success": False, "error": "activity_type is required"}

        try:
            execute_query(
                """
                INSERT INTO user_activity (id, user_id, activity_type, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid4()), user_id, activity_type.strip(), json.dumps(metadata) if metadata else None),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to record activity: {str(e)}"}

    # -- Aggregation -------------------------------------------------------

    def get_learning_path_stats(self, user_id: str) -> Dict:
        """
        Build the Learning Path statistics payload for a user.

        Returns a flat {"success": True, ...metrics...} dict. Every metric
        degrades gracefully to a zero/None default for a user with no data,
        so the dashboard always renders.
        """
        try:
            stats = {"success": True}
            stats.update(self._practice_stats(user_id))
            stats.update(self._mastery_stats(user_id))
            stats.update(self._activity_stats(user_id))
            return stats
        except Exception as e:
            return {"success": False, "error": f"Failed to load learning path stats: {str(e)}"}

    def _practice_stats(self, user_id: str) -> Dict:
        """Latest & average Practice score (as a 0-100 percentage) and the
        latest Practice interaction timestamp."""
        rows = execute_query(
            """
            SELECT completed_at, total_score, max_possible_score
            FROM practice_attempts
            WHERE user_id = %s
            ORDER BY completed_at DESC NULLS LAST
            """,
            (user_id,),
            fetch=True,
        ) or []

        def _pct(total, maximum):
            return round((total / maximum) * 100, 2) if maximum else 0.0

        percentages = [_pct(total, maximum) for _, total, maximum in rows]

        latest_completed_at = rows[0][0] if rows else None

        return {
            "practice_sessions": len(rows),
            "latest_practice_score": percentages[0] if percentages else None,
            "average_practice_score": round(sum(percentages) / len(percentages), 2) if percentages else None,
            "latest_practice_interaction": latest_completed_at.isoformat() if latest_completed_at else None,
        }

    def _mastery_stats(self, user_id: str) -> Dict:
        """Mastered vs Remedial unit counts, from the Test-driven mastery
        summary (the sole source of truth)."""
        summary = self.mastery_service.get_user_mastery_summary(user_id)
        units = summary.get("units", []) if summary.get("success") else []
        mastered = sum(1 for u in units if u.get("mastery_status") == MASTERED)

        return {
            "mastered_units": mastered,
            "remedial_units": len(units) - mastered,
            "total_units": len(units),
        }

    def _activity_stats(self, user_id: str) -> Dict:
        """Per-activity_type counts and latest-occurrence timestamps, read
        from the generic user_activity log in a single query."""
        rows = execute_query(
            """
            SELECT activity_type, COUNT(*), MAX(occurred_at)
            FROM user_activity
            WHERE user_id = %s
            GROUP BY activity_type
            """,
            (user_id,),
            fetch=True,
        ) or []

        by_type = {
            activity_type: (count, latest)
            for activity_type, count, latest in rows
        }

        def count_of(activity_type):
            return by_type.get(activity_type, (0, None))[0]

        def latest_of(activity_type):
            latest = by_type.get(activity_type, (0, None))[1]
            return latest.isoformat() if latest else None

        return {
            "materials_viewed": count_of(ACTIVITY_MATERIAL_VIEW),
            "latest_material_activity": latest_of(ACTIVITY_MATERIAL_VIEW),
            "chatbot_attempts": count_of(ACTIVITY_CHATBOT_PROMPT),
            "latest_chatbot_interaction": latest_of(ACTIVITY_CHATBOT_PROMPT),
        }
