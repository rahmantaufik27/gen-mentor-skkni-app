"""
Controller for Learning Path statistics endpoints.

Thin pass-through to LearningPathStatsService, matching the other controllers'
convention of normalizing exceptions into {"success": False, "error": ...}.
"""

from typing import Dict, Optional

from services.learning_path_stats_service import LearningPathStatsService


class LearningPathStatsController:
    """Controller for Learning Path statistics operations."""

    def __init__(self, stats_service: LearningPathStatsService):
        self.stats_service = stats_service

    def get_stats(self, user_id: str) -> Dict:
        """Return the aggregated Learning Path statistics for a user."""
        try:
            return self.stats_service.get_learning_path_stats(user_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def record_activity(self, user_id: str, activity_type: str, metadata: Optional[Dict] = None) -> Dict:
        """Record one activity event (a counter/latest-timestamp metric)."""
        try:
            return self.stats_service.record_activity(user_id, activity_type, metadata)
        except Exception as e:
            return {"success": False, "error": str(e)}
