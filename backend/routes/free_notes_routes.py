"""
API routes for free notes - thin HTTP layer over FreeNotesController.
Mounted under /api/free-notes/*.

  - GET    /free-notes?user_id=&category=  -> list a user's free notes
  - POST   /free-notes                     -> create {user_id, category, content_html}
  - PUT    /free-notes                     -> update {user_id, note_id, content_html}
  - DELETE /free-notes                     -> delete {user_id, note_id}

category is one of 'question' | 'key_points'.
"""

from flask import Blueprint, request, jsonify
from controllers.free_notes_controller import FreeNotesController

free_notes_bp = Blueprint("free_notes", __name__, url_prefix="/api/free-notes")


def init_free_notes_routes(app, controller: FreeNotesController):
    """Initialize free-notes routes."""

    @free_notes_bp.route("", methods=["GET"])
    def list_notes():
        user_id = request.args.get("user_id")
        category = request.args.get("category")
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        result = controller.list_notes(user_id, category or None)
        return jsonify(result), (200 if result.get("success") else 400)

    @free_notes_bp.route("", methods=["POST"])
    def create_note():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        category = data.get("category")
        content_html = data.get("content_html")
        if not user_id or not category:
            return jsonify({"success": False, "error": "user_id and category are required"}), 400
        result = controller.create_note(user_id, category, content_html)
        return jsonify(result), (200 if result.get("success") else 400)

    @free_notes_bp.route("", methods=["PUT"])
    def update_note():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        note_id = data.get("note_id")
        content_html = data.get("content_html")
        if not user_id or not note_id:
            return jsonify({"success": False, "error": "user_id and note_id are required"}), 400
        result = controller.update_note(user_id, note_id, content_html)
        return jsonify(result), (200 if result.get("success") else 400)

    @free_notes_bp.route("", methods=["DELETE"])
    def delete_note():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        note_id = data.get("note_id")
        if not user_id or not note_id:
            return jsonify({"success": False, "error": "user_id and note_id are required"}), 400
        result = controller.delete_note(user_id, note_id)
        return jsonify(result), (200 if result.get("success") else 400)

    app.register_blueprint(free_notes_bp)
