"""
API routes for Notes endpoints - thin HTTP layer over NotesController.
Mounted under /api/notes/*.

  - GET    /notes?user_id=&source_type=   -> list a user's notes (optional filter)
  - GET    /notes/keys?user_id=&source_type= -> saved (source_type, source_id) keys
  - POST   /notes                         -> save a note (idempotent toggle-on)
  - DELETE /notes                         -> remove a note by id or (source_type, source_id)

source_type is one of 'material' | 'question' | 'chat'.
"""

from flask import Blueprint, request, jsonify
from controllers.notes_controller import NotesController

notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")


def init_notes_routes(app, controller: NotesController):
    """Initialize notes routes."""

    @notes_bp.route("", methods=["GET"])
    def list_notes():
        user_id = request.args.get("user_id")
        source_type = request.args.get("source_type")
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        result = controller.list_notes(user_id, source_type or None)
        return jsonify(result), (200 if result.get("success") else 400)

    @notes_bp.route("/keys", methods=["GET"])
    def get_keys():
        user_id = request.args.get("user_id")
        source_type = request.args.get("source_type")
        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        result = controller.get_saved_source_ids(user_id, source_type or None)
        return jsonify(result), (200 if result.get("success") else 400)

    @notes_bp.route("", methods=["POST"])
    def create_note():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        source_type = data.get("source_type")
        source_id = data.get("source_id")
        snapshot_text = data.get("snapshot_text")
        title = data.get("title")
        source_ref = data.get("source_ref")

        if not all([user_id, source_type, source_id, snapshot_text]):
            return jsonify({
                "success": False,
                "error": "user_id, source_type, source_id and snapshot_text are required",
            }), 400

        result = controller.create_note(user_id, source_type, source_id, snapshot_text, title, source_ref)
        return jsonify(result), (200 if result.get("success") else 400)

    @notes_bp.route("", methods=["DELETE"])
    def delete_note():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        note_id = data.get("note_id")
        source_type = data.get("source_type")
        source_id = data.get("source_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400
        if not note_id and not (source_type and source_id):
            return jsonify({"success": False, "error": "Provide note_id or (source_type, source_id)"}), 400

        result = controller.delete_note(user_id, note_id, source_type, source_id)
        return jsonify(result), (200 if result.get("success") else 400)

    app.register_blueprint(notes_bp)
