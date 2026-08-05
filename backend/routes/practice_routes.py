"""
API routes for practice-session endpoints - thin HTTP layer over
PracticeController. Mounted under /api/practice/*.

Mirrors /api/quiz/* (start/question/submit-answer/complete) for UI/UX
parity with Test, but is a fully separate blueprint: Practice never writes
to quiz_attempts/user_mastery_level, so it can't affect Test's scoring or
mastery logic.
"""

from flask import Blueprint, request, jsonify
from controllers.practice_controller import PracticeController

practice_bp = Blueprint("practice", __name__, url_prefix="/api/practice")


def init_practice_routes(app, controller: PracticeController):
    """
    Initialize practice routes

    Args:
        app: Flask application
        controller: PracticeController instance
    """

    @practice_bp.route("/start", methods=["POST"])
    def start_practice():
        """Start a new practice session"""
        data = request.get_json() or {}
        user_id = data.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.start_practice(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @practice_bp.route("/question/<session_id>/<int:question_index>", methods=["GET"])
    def get_question(session_id, question_index):
        """Get a specific question"""
        result = controller.get_question(session_id, question_index)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @practice_bp.route("/submit-answer", methods=["POST"])
    def submit_answer():
        """Submit an answer"""
        data = request.get_json() or {}
        session_id = data.get("session_id")
        question_index = data.get("question_index")
        selected_answer = data.get("selected_answer")

        if not all([session_id, question_index is not None, selected_answer]):
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        result = controller.submit_answer(session_id, question_index, selected_answer)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @practice_bp.route("/complete/<session_id>", methods=["POST"])
    def complete_practice(session_id):
        """Complete practice session and return results"""
        result = controller.complete_practice(session_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @practice_bp.route("/analytics", methods=["GET"])
    def get_practice_analytics():
        """Get Practice Analytics dashboard summary (total sessions, per-unit progression)"""
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_practice_analytics(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    # Register blueprint
    app.register_blueprint(practice_bp)
