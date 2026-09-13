"""
API routes for the unit discussion forum - thin HTTP layer over
DiscussionController. Mounted under /api/discussions/*.

  - GET    /discussions?unit_code=&material_id=       -> list a unit's (or one
                                                           material's) posts (threaded)
  - GET    /discussions/counts                         -> post count per unit_code
  - GET    /discussions/material-counts?unit_code=     -> post count per material_id in a unit
  - POST   /discussions                                 -> create {user_id, unit_code, body,
                                                             parent_post_id?, material_id?, material_title?}
  - PUT    /discussions/best-answer                     -> {user_id, reply_id, is_best}
  - DELETE /discussions                                  -> delete {user_id, post_id}
"""

from flask import Blueprint, request, jsonify
from controllers.discussion_controller import DiscussionController

discussion_bp = Blueprint("discussion", __name__, url_prefix="/api/discussions")


def init_discussion_routes(app, controller: DiscussionController):
    """Initialize discussion routes."""

    @discussion_bp.route("", methods=["GET"])
    def list_posts():
        unit_code = request.args.get("unit_code")
        material_id = request.args.get("material_id") or None
        if not unit_code:
            return jsonify({"success": False, "error": "unit_code is required"}), 400
        result = controller.list_posts(unit_code, material_id)
        return jsonify(result), (200 if result.get("success") else 400)

    @discussion_bp.route("/counts", methods=["GET"])
    def get_post_counts():
        result = controller.get_post_counts()
        return jsonify(result), (200 if result.get("success") else 400)

    @discussion_bp.route("/material-counts", methods=["GET"])
    def get_material_post_counts():
        unit_code = request.args.get("unit_code")
        if not unit_code:
            return jsonify({"success": False, "error": "unit_code is required"}), 400
        result = controller.get_material_post_counts(unit_code)
        return jsonify(result), (200 if result.get("success") else 400)

    @discussion_bp.route("", methods=["POST"])
    def create_post():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        unit_code = data.get("unit_code")
        body = data.get("body")
        parent_post_id = data.get("parent_post_id")
        material_id = data.get("material_id")
        material_title = data.get("material_title")
        if not user_id or not unit_code:
            return jsonify({"success": False, "error": "user_id and unit_code are required"}), 400
        result = controller.create_post(user_id, unit_code, body, parent_post_id, material_id, material_title)
        return jsonify(result), (200 if result.get("success") else 400)

    @discussion_bp.route("/best-answer", methods=["PUT"])
    def set_best_answer():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        reply_id = data.get("reply_id")
        is_best = data.get("is_best", True)
        if not user_id or not reply_id:
            return jsonify({"success": False, "error": "user_id and reply_id are required"}), 400
        result = controller.set_best_answer(user_id, reply_id, bool(is_best))
        return jsonify(result), (200 if result.get("success") else 400)

    @discussion_bp.route("", methods=["DELETE"])
    def delete_post():
        data = request.get_json() or {}
        user_id = data.get("user_id")
        post_id = data.get("post_id")
        if not user_id or not post_id:
            return jsonify({"success": False, "error": "user_id and post_id are required"}), 400
        result = controller.delete_post(user_id, post_id)
        return jsonify(result), (200 if result.get("success") else 400)

    app.register_blueprint(discussion_bp)
