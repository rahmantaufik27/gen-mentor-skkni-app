"""
API routes for the Admin module - thin HTTP layer over AdminController.
Mounted under /api/admin/*.

NOTE: the frontend calls this API statelessly (a fresh httpx connection per
request, no cookie jar - see frontend/utils/admin_api.py), so the Flask
session set on login is not relied upon for authorization here; the actual
gate is enforced client-side (frontend/components/admin_shell.py), the same
pattern the learner flow already uses. /login still does real credential
verification against AdminAuthService.
"""

from flask import Blueprint, request, jsonify
from controllers.admin_controller import AdminController

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def init_admin_routes(app):
    """
    Initialize admin routes.

    Args:
        app: Flask application
    """

    @admin_bp.route("/login", methods=["POST"])
    def login():
        """Admin login endpoint"""
        data = request.get_json() or {}
        email = data.get("email", "")
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required"}), 400

        result = AdminController.login(email, password)
        status_code = 200 if result.get("success") else 401
        return jsonify(result), status_code

    @admin_bp.route("/logout", methods=["POST"])
    def logout():
        """Admin logout endpoint"""
        result = AdminController.logout()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @admin_bp.route("/users", methods=["GET"])
    def get_all_users():
        """List all users with their inference_method"""
        result = AdminController.get_all_users()
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @admin_bp.route("/users/inference-method", methods=["PUT"])
    def update_all_users_inference_method():
        """Bulk-update inference_method (DBN or Manual) for every user"""
        data = request.get_json() or {}
        inference_method = data.get("inference_method")

        if not inference_method:
            return jsonify({"success": False, "error": "inference_method is required"}), 400

        result = AdminController.update_all_users_inference_method(inference_method)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    @admin_bp.route("/users/<user_id>/inference-method", methods=["PUT"])
    def update_inference_method(user_id):
        """Update a single user's inference_method (DBN or Manual)"""
        data = request.get_json() or {}
        inference_method = data.get("inference_method")

        if not inference_method:
            return jsonify({"success": False, "error": "inference_method is required"}), 400

        result = AdminController.update_inference_method(user_id, inference_method)
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code

    # Register blueprint
    app.register_blueprint(admin_bp)
