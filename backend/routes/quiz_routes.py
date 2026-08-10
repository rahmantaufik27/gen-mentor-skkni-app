"""
API routes for quiz endpoints - thin HTTP layer over QuizController.

Every route follows the same convention: call the controller, then map its
{"success": bool, ...} dict to HTTP 200 (success) or 400 (error).
"""

from flask import Blueprint, request, jsonify
from controllers.quiz_controller import QuizController

# All endpoints below are mounted under /api/quiz/*
quiz_bp = Blueprint("quiz", __name__, url_prefix="/api/quiz")


def init_quiz_routes(app, controller: QuizController):
    """
    Initialize quiz routes
    
    Args:
        app: Flask application
        controller: QuizController instance
    """

    @quiz_bp.route("/start", methods=["POST"])
    def start_quiz():
        """Start a new quiz session"""
        # Get user_id from request body
        data = request.get_json() or {}
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        
        result = controller.start_quiz(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/question/<session_id>/<int:question_index>", methods=["GET"])
    def get_question(session_id, question_index):
        """Get a specific question"""
        result = controller.get_question(session_id, question_index)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/submit-answer", methods=["POST"])
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

    @quiz_bp.route("/complete/<session_id>", methods=["POST"])
    def complete_quiz(session_id):
        """Complete quiz and save results"""
        data = request.get_json() or {}
        user_id = data.get("user_id")
        
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        
        result = controller.complete_quiz(session_id, user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/history", methods=["GET"])
    def get_quiz_history():
        """Get user quiz history"""
        user_id = request.args.get("user_id")
        limit = request.args.get("limit", 10, type=int)
        
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        
        result = controller.get_user_quiz_history(user_id, limit)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/mastery-summary", methods=["GET"])
    def get_mastery_summary():
        """Get user mastery-level dashboard summary"""
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_mastery_summary(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/test-analytics", methods=["GET"])
    def get_test_analytics():
        """Get per-stage (Pre-Test / Post-Test) analytics for the dashboard"""
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_test_analytics(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/unit-codes", methods=["GET"])
    def get_unit_code_map():
        """Get the truncated -> full unit_code map (static, not user-specific)"""
        result = controller.get_unit_code_map()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/recommended-questions", methods=["GET"])
    def get_recommended_questions():
        """Get practice questions recommended from the Neo4j knowledge graph"""
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_recommended_questions(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @quiz_bp.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok", "service": "quiz-api"}), 200

    # Register blueprint
    app.register_blueprint(quiz_bp)
