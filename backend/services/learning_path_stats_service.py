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

from datetime import date, timedelta
from typing import Dict, List, Optional
from uuid import uuid4
import json

from config.database import execute_query
from services.mastery_service import MasteryService, MASTERED, REMEDIAL


def _normalize_status(status: Optional[str]) -> str:
    """Local copy of mastery_service._normalize_status (same pattern already
    used by services/practice_service.py and services/materials_service.py
    for _truncate_unit_code - a small private helper duplicated locally
    rather than imported across modules). Handles legacy 'MASTERED'/
    'REMEDIAL' rows the same way the source of truth does."""
    return MASTERED if (status or "").strip().upper() == "MASTERED" else REMEDIAL

# Well-known activity types. New metrics can add their own without touching
# anything here except (optionally) a convenience constant.
ACTIVITY_MATERIAL_VIEW = "material_view"
ACTIVITY_CHATBOT_PROMPT = "chatbot_prompt"
ACTIVITY_LOGIN = "login"

# How many trailing days the "recent activity" chart covers.
_ENGAGEMENT_WINDOW_DAYS = 30


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
            stats.update(self._test_stats(user_id))
            stats.update(self._mastery_stats(user_id))
            stats.update(self._activity_stats(user_id))
            stats.update(self._engagement_stats(user_id))
            stats.update(self._peer_benchmark_stats(user_id))
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

    def _test_stats(self, user_id: str) -> Dict:
        """Completed Test attempt count + latest completion timestamp - the
        engagement-side counterpart to _practice_stats, so the activity
        breakdown can show Test alongside Practice/Materials/Chatbot/Login,
        and "last substantive activity" nudges (see the frontend's
        mastery_dashboard._render_nudge_banner) can factor Test in too."""
        rows = execute_query(
            "SELECT COUNT(*), MAX(completed_at) FROM quiz_attempts WHERE user_id = %s AND completed_at IS NOT NULL",
            (user_id,),
            fetch=True,
        ) or [(0, None)]
        count, latest = rows[0]
        return {
            "test_attempts": count,
            "latest_test_interaction": latest.isoformat() if latest else None,
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
            "logins": count_of(ACTIVITY_LOGIN),
            "latest_login": latest_of(ACTIVITY_LOGIN),
        }

    # -- Engagement (behavioral tracking) -----------------------------------
    #
    # Deliberately reads Practice/Test completion timestamps directly from
    # their own tables (practice_attempts.completed_at, quiz_attempts.
    # completed_at) instead of also logging them into user_activity - they're
    # already reliably timestamped there, so duplicating them as activity
    # events would just be two sources of truth for the same fact. Only
    # events with no table of their own (login) go through record_activity.

    def _active_dates(self, user_id: str) -> List[date]:
        """Every distinct calendar date the user did *anything* countable
        (activity log entry, Practice session, or Test attempt), newest
        first - the raw material for streaks and "last active"."""
        rows = execute_query(
            """
            SELECT DISTINCT d FROM (
                SELECT occurred_at::date AS d FROM user_activity WHERE user_id = %s
                UNION
                SELECT completed_at::date AS d FROM practice_attempts
                    WHERE user_id = %s AND completed_at IS NOT NULL
                UNION
                SELECT completed_at::date AS d FROM quiz_attempts
                    WHERE user_id = %s AND completed_at IS NOT NULL
            ) AS active_dates
            ORDER BY d DESC
            """,
            (user_id, user_id, user_id),
            fetch=True,
        ) or []
        return [r[0] for r in rows]

    def _daily_activity(self, user_id: str) -> List[Dict]:
        """Per-day activity counts for the last _ENGAGEMENT_WINDOW_DAYS days
        (across the same three sources as _active_dates), for a recent-
        activity chart. Sparse - only days with at least one event are
        included; the frontend fills the gaps."""
        rows = execute_query(
            f"""
            SELECT d, COUNT(*) FROM (
                SELECT occurred_at::date AS d FROM user_activity
                    WHERE user_id = %s AND occurred_at >= NOW() - INTERVAL '{_ENGAGEMENT_WINDOW_DAYS} days'
                UNION ALL
                SELECT completed_at::date AS d FROM practice_attempts
                    WHERE user_id = %s AND completed_at >= NOW() - INTERVAL '{_ENGAGEMENT_WINDOW_DAYS} days'
                UNION ALL
                SELECT completed_at::date AS d FROM quiz_attempts
                    WHERE user_id = %s AND completed_at >= NOW() - INTERVAL '{_ENGAGEMENT_WINDOW_DAYS} days'
            ) AS recent_activity
            GROUP BY d ORDER BY d
            """,
            (user_id, user_id, user_id),
            fetch=True,
        ) or []
        return [{"date": d.isoformat(), "count": count} for d, count in rows]

    def _engagement_stats(self, user_id: str) -> Dict:
        """Behavioral/engagement metrics derived from _active_dates: how
        consistently the user shows up, not how well they score. Every value
        degrades to a zero/empty default for a user with no activity yet."""
        active_dates = self._active_dates(user_id)

        if not active_dates:
            return {
                "active_days_total": 0,
                "active_days_last_30": 0,
                "current_streak_days": 0,
                "longest_streak_days": 0,
                "last_active_date": None,
                "daily_activity": [],
            }

        today = date.today()
        date_set = set(active_dates)

        # Current streak: consecutive active days ending today, or ending
        # yesterday if today's session just hasn't happened yet (so the
        # streak doesn't reset to 0 first thing in the morning).
        current_streak = 0
        cursor = today if today in date_set else today - timedelta(days=1)
        while cursor in date_set:
            current_streak += 1
            cursor -= timedelta(days=1)

        # Longest streak ever: longest run of consecutive calendar dates.
        ascending = sorted(date_set)
        longest_streak = run = 1
        for previous, current in zip(ascending, ascending[1:]):
            run = run + 1 if (current - previous).days == 1 else 1
            longest_streak = max(longest_streak, run)

        active_days_last_30 = sum(
            1 for d in active_dates if (today - d).days < _ENGAGEMENT_WINDOW_DAYS
        )

        return {
            "active_days_total": len(active_dates),
            "active_days_last_30": active_days_last_30,
            "current_streak_days": current_streak,
            "longest_streak_days": longest_streak,
            "last_active_date": active_dates[0].isoformat(),
            "daily_activity": self._daily_activity(user_id),
        }

    # -- Peer benchmarking (anonymous collaborative/peer-based personalization) --
    #
    # Rewritten during a 200-concurrent-user scalability audit: this used to
    # call MasteryService.get_user_mastery_summary() once per peer (an N+1
    # query - 3-6 queries per peer, so 5 peers today already means 15-30
    # queries for one dashboard load; at 200 users that's 600-1200 queries
    # for a single request). Replaced with one aggregate query that joins
    # each peer's LATEST quiz_attempt to its user_mastery_level rows -
    # mirroring get_user_mastery_summary()'s own "latest attempt (by
    # completed_at DESC NULLS LAST, started_at DESC), then rows tied to that
    # attempt_id" logic exactly (same ordering, same tie-break), so the
    # numbers match what get_user_mastery_summary() would have returned per
    # peer. get_user_mastery_summary() also fills in every unit from
    # knowledge_target.json that's missing a row as a default (score 0,
    # Remedial) - a default can never add to a Mastered tally, but it DOES
    # mean every target unit is "counted" for every peer regardless of
    # mastery, which is why peer_unit_mastery_pct below is built from
    # mastery_service.targets (every target unit, defaulting to 0.0%) and
    # not just the unit codes that happen to have a Mastered row - verified
    # this exact edge case against the old per-peer logic directly, see the
    # comparison script used while building this rewrite.
    #
    # Nobody's individual data is ever exposed to anybody else here - every
    # value returned is a count/percentage/percentile computed across all
    # users, never a per-user breakdown.

    def _peer_benchmark_stats(self, user_id: str) -> Dict:
        """Anonymous peer comparison: how this user's Test-driven mastery
        stacks up against every other user who has taken a Test."""
        peer_id_rows = execute_query(
            "SELECT DISTINCT user_id FROM quiz_attempts", fetch=True,
        ) or []
        peer_ids = [str(r[0]) for r in peer_id_rows]

        if not peer_ids:
            return {
                "peer_total_learners": 0,
                "peer_mastered_percentile": None,
                "peer_avg_mastered_units": 0,
                "peer_unit_mastery_pct": {},
            }

        # Every peer's latest quiz_attempt, joined to the user_mastery_level
        # rows that attempt produced - one round trip instead of one per peer.
        rows = execute_query(
            """
            SELECT uml.user_id, uml.unit_code, uml.mastery_status
            FROM user_mastery_level uml
            JOIN (
                SELECT DISTINCT ON (user_id) user_id, id AS attempt_id
                FROM quiz_attempts
                ORDER BY user_id, completed_at DESC NULLS LAST, started_at DESC
            ) latest ON uml.attempt_id = latest.attempt_id
            """,
            fetch=True,
        ) or []

        mastered_counts: Dict[str, int] = {pid: 0 for pid in peer_ids}
        unit_mastered_tally: Dict[str, int] = {}

        for peer_user_id, unit_code, mastery_status in rows:
            peer_user_id = str(peer_user_id)
            if peer_user_id not in mastered_counts:
                continue  # defensive: ignore rows for a user_id not in our peer set
            if _normalize_status(mastery_status) == MASTERED:
                mastered_counts[peer_user_id] += 1
                if unit_code:
                    unit_mastered_tally[unit_code] = unit_mastered_tally.get(unit_code, 0) + 1

        # Every target unit (knowledge_target.json) gets an entry, 0.0% if
        # nobody's mastered it yet - matches the old per-peer version, where
        # every peer's `units` list always covered every target unit
        # (defaulting missing ones to Remedial), so every code was tallied
        # for every peer regardless of mastery status.
        peer_unit_mastery_pct = {
            code: round(unit_mastered_tally.get(code, 0) * 100.0 / len(peer_ids), 1)
            for code in self.mastery_service.targets.keys()
        }

        counts = list(mastered_counts.values())
        my_count = mastered_counts.get(str(user_id), 0)
        percentile = round(sum(1 for c in counts if c <= my_count) * 100.0 / len(counts))

        return {
            "peer_total_learners": len(counts),
            "peer_mastered_percentile": percentile,
            "peer_avg_mastered_units": round(sum(counts) / len(counts), 1),
            "peer_unit_mastery_pct": peer_unit_mastery_pct,
        }
