"""
Main Flask application for the Quiz Backend.
"""

import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.question_loader import QuestionLoader
from services.session_manager import QuizSessionManager
from services.session_storage import SessionStorage
from controllers.quiz_controller import QuizController
from routes.quiz_routes import init_quiz_routes


def create_app(config=None):
    """
    Create and configure Flask application
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Flask application
    """
    app = Flask(__name__)

    # Default configuration
    if config is None:
        config = {}

    # Get paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    storage_dir = os.path.join(base_dir, "storage")

    # Create directories if they don't exist
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    # Configuration
    app.config.update(
        JSON_SORT_KEYS=False,
        JSONIFY_PRETTYPRINT_REGULAR=True
    )

    # Enable CORS
    CORS(app)

    # Initialize services
    question_loader = QuestionLoader(data_dir)
    session_manager = QuizSessionManager(question_loader)
    storage = SessionStorage(storage_dir)

    # Initialize controller
    controller = QuizController(question_loader, session_manager, storage)

    # Initialize routes
    init_quiz_routes(app, controller)

    # Root endpoint
    @app.route("/", methods=["GET"])
    def root():
        """Root endpoint"""
        return jsonify({
            "message": "Quiz Backend API",
            "version": "1.0.0",
            "endpoints": {
                "health": "/api/quiz/health",
                "start_quiz": "POST /api/quiz/start",
                "get_question": "GET /api/quiz/question/<session_id>/<question_index>",
                "submit_answer": "POST /api/quiz/submit-answer",
                "get_progress": "GET /api/quiz/progress/<session_id>",
                "complete_quiz": "POST /api/quiz/complete/<session_id>",
                "get_results": "GET /api/quiz/results/<session_id>",
                "get_all_results": "GET /api/quiz/all-results",
                "get_results_summary": "GET /api/quiz/results-summary"
            }
        }), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    print("Starting Quiz Backend Server...")
    print("Server running on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
