"""
API routes for Learning Path statistics - thin HTTP layer over
LearningPathStatsController. Mounted under /api/learning-path/*.

Two lightweight, generic endpoints back every metric:
  - GET  /stats?user_id=...   -> aggregated Learning Path statistics
  - POST /activity            -> record one activity event {user_id, activity_type}

Keeping the write side a single generic /activity endpoint means new
countable/timestamped metrics need no new route - just a new activity_type.
"""

from flask import Blueprint, request, jsonify
from controllers.learning_path_stats_controller import LearningPathStatsController

learning_path_stats_bp = Blueprint("learning_path_stats", __name__, url_prefix="/api/learning-path")


def init_learning_path_stats_routes(app, controller: LearningPathStatsController):
    """Initialize Learning Path statistics routes."""

    @learning_path_stats_bp.route("/stats", methods=["GET"])
    def get_stats():
        """Get the aggregated Learning Path statistics for a user."""
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_stats(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @learning_path_stats_bp.route("/activity", methods=["POST"])
    def record_activity():
        """Record one activity event (e.g. a material opened, a chatbot prompt)."""
        data = request.get_json() or {}
        user_id = data.get("user_id")
        activity_type = data.get("activity_type")
        metadata = data.get("metadata")

        if not user_id or not activity_type:
            return jsonify({"success": False, "error": "user_id and activity_type are required"}), 400

        result = controller.record_activity(user_id, activity_type, metadata)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    app.register_blueprint(learning_path_stats_bp)
