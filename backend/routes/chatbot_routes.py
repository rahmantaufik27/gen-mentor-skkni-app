"""
API routes for the chatbot endpoints - thin HTTP layer over ChatbotController.
Mounted under /api/chatbot/*.

Standalone learning assistant: these routes never touch the database, Neo4j,
the user model, recommendations, or adaptive-learning logic.
"""

from flask import Blueprint, request, jsonify
from controllers.chatbot_controller import ChatbotController

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


def init_chatbot_routes(app, controller: ChatbotController):
    """
    Initialize chatbot routes.

    Args:
        app: Flask application
        controller: ChatbotController instance
    """

    @chatbot_bp.route("/chat", methods=["POST"])
    def chat():
        """Return an assistant reply for the posted conversation."""
        data = request.get_json(silent=True) or {}
        messages = data.get("messages")

        if not isinstance(messages, list) or not messages:
            return jsonify({"success": False, "error": "A non-empty 'messages' list is required."}), 400

        result = controller.chat(messages)
        # 200 on success; 503 when the assistant/provider is unavailable, so the
        # client can tell a transient outage from a bad request (400 above).
        status_code = 200 if result.get("success") else 503
        return jsonify(result), status_code

    @chatbot_bp.route("/health", methods=["GET"])
    def health():
        """Report whether the underlying LLM provider is reachable."""
        result = controller.health()
        status_code = 200 if result.get("success") else 500
        return jsonify(result), status_code

    app.register_blueprint(chatbot_bp)
