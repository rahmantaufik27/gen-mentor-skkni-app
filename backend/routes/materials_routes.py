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

    # Register blueprint
    app.register_blueprint(materials_bp)
