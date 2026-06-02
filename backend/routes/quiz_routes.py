"""
API routes for quiz endpoints.
"""

from flask import Blueprint, request, jsonify
from controllers.quiz_controller import QuizController

# Create blueprint
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

    @quiz_bp.route("/health", methods=["GET"])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "ok", "service": "quiz-api"}), 200

    # Register blueprint
    app.register_blueprint(quiz_bp)
