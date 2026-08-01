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

    # Register blueprint
    app.register_blueprint(materials_bp)
