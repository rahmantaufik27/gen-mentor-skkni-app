"""
API routes for reading-materials endpoints - thin HTTP layer over
MaterialsController. Mounted under /api/materials/*.
"""

from flask import Blueprint, request, jsonify
from controllers.materials_controller import MaterialsController

materials_bp = Blueprint("materials", __name__, url_prefix="/api/materials")


def init_materials_routes(app, controller: MaterialsController):
    """
    Initialize reading-materials routes.

    Args:
        app: Flask application
        controller: MaterialsController instance
    """

    @materials_bp.route("/all", methods=["GET"])
    def get_all_materials():
        """Get every reading material"""
        result = controller.get_all_materials()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @materials_bp.route("/recommended", methods=["GET"])
    def get_recommended_materials():
        """Get materials recommended based on the user's mastery gaps"""
        user_id = request.args.get("user_id")

        if not user_id:
            return jsonify({"success": False, "error": "User ID required"}), 400

        result = controller.get_recommended_materials(user_id)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @materials_bp.route("/units", methods=["GET"])
    def get_all_units():
        """Get every unit's code + human-readable title"""
        result = controller.get_all_units()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @materials_bp.route("/generate-learning", methods=["POST"])
    def generate_learning_material():
        """Generate learning content using existing materials for a unit."""
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "error": "JSON object required"}), 400
        unit_code = body.get("unit_code")
        if not isinstance(unit_code, str) or not unit_code.strip():
            return jsonify({"success": False, "error": "Unit code required"}), 400
        competency_name = body.get("competency_name")
        if not isinstance(competency_name, str) or not competency_name.strip():
            return jsonify({"success": False, "error": "Competency name required"}), 400

        result = controller.generate_learning_material(unit_code, competency_name)
        status_code = 200 if result.get("success") else 502
        return jsonify(result), status_code

    @materials_bp.route("/subtopics", methods=["POST"])
    def list_subtopics():
        """List one short, generated title per reference group for a unit -
        the fast first step of the "pick a subtopic, then generate just
        that one" flow (see generate-subtopic below)."""
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "error": "JSON object required"}), 400
        unit_code = body.get("unit_code")
        if not isinstance(unit_code, str) or not unit_code.strip():
            return jsonify({"success": False, "error": "Unit code required"}), 400
        competency_name = body.get("competency_name")
        if not isinstance(competency_name, str) or not competency_name.strip():
            return jsonify({"success": False, "error": "Competency name required"}), 400

        result = controller.list_subtopics(unit_code, competency_name)
        status_code = 200 if result.get("success") else 502
        return jsonify(result), status_code

    @materials_bp.route("/generate-subtopic", methods=["POST"])
    def generate_subtopic_material():
        """Generate learning content for ONE subtopic (one reference group)
        of a unit - triggered per subtopic by its own button on the
        frontend, never automatically for every subtopic in a loop."""
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "error": "JSON object required"}), 400
        unit_code = body.get("unit_code")
        if not isinstance(unit_code, str) or not unit_code.strip():
            return jsonify({"success": False, "error": "Unit code required"}), 400
        competency_name = body.get("competency_name")
        if not isinstance(competency_name, str) or not competency_name.strip():
            return jsonify({"success": False, "error": "Competency name required"}), 400
        subtopic_index = body.get("subtopic_index")
        if not isinstance(subtopic_index, int):
            return jsonify({"success": False, "error": "subtopic_index (integer) required"}), 400
        subtopic_title = body.get("subtopic_title") or ""

        result = controller.generate_subtopic_material(
            unit_code, competency_name, subtopic_index, subtopic_title
        )
        status_code = 200 if result.get("success") else 502
        return jsonify(result), status_code

    # Register blueprint
    app.register_blueprint(materials_bp)
