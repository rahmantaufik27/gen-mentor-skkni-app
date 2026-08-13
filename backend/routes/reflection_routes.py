"""
API routes for Learning Reflection - thin HTTP layer over ReflectionController.
Mounted under /api/reflection/*.

  - GET    /reflection/questions          -> the reflection question config
  - GET    /reflection/answers?user_id=   -> a user's saved answers (by key)
  - POST   /reflection/answers            -> create/update one answer (upsert)
  - DELETE /reflection/answers            -> delete one answer by question_key

Every answer endpoint requires user_id and is scoped to it, so no user can read
or modify another user's reflection data.
"""

from flask import Blueprint, request, jsonify
from controllers.reflection_controller import ReflectionController

reflection_bp = Blueprint("reflection", __name__, url_prefix="/api/reflection")


def init_reflection_routes(app, controller: ReflectionController):
    """Initialize reflection routes."""

    @reflection_bp.route("/questions", methods=["GET"])
    def get_questions():
        result = controller.get_questions()
        return jsonify(result), (200 if result.get("success") else 400)

    @reflection_bp.route("/answers", methods=["GET"])
    def get_answers():
        user_id = request.args.get("user_id")
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        result = controller.get_answers(user_id)
        return jsonify(result), (200 if result.get("success") else 400)

    @reflection_bp.route("/answers", methods=["POST"])
    def save_answer():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        question_key = data.get("question_key")
        if not user_id or not question_key:
            return jsonify({"success": False, "error": "user_id and question_key are required"}), 400
        result = controller.save_answer(
            user_id, question_key, data.get("answer_text"), data.get("answer_number")
        )
        return jsonify(result), (200 if result.get("success") else 400)

    @reflection_bp.route("/answers", methods=["DELETE"])
    def delete_answer():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        question_key = data.get("question_key")
        if not user_id or not question_key:
            return jsonify({"success": False, "error": "user_id and question_key are required"}), 400
        result = controller.delete_answer(user_id, question_key)
        return jsonify(result), (200 if result.get("success") else 400)

    app.register_blueprint(reflection_bp)
