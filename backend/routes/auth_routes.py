"""Authentication routes."""

from flask import Blueprint
from controllers.auth_controller import AuthController

# Create authentication blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def init_auth_routes(app):
    """
    Initialize authentication routes.
    
    Args:
        app: Flask application instance
    """
    @auth_bp.route("/register", methods=["POST"])
    def register():
        """User registration endpoint."""
        return AuthController.register()
    
    @auth_bp.route("/login", methods=["POST"])
    def login():
        """User login endpoint."""
        return AuthController.login()
    
    @auth_bp.route("/logout", methods=["POST"])
    def logout():
        """User logout endpoint."""
        return AuthController.logout()
    
    @auth_bp.route("/me", methods=["GET"])
    def get_current_user():
        """Get current authenticated user endpoint."""
        return AuthController.get_current_user()
    
    # Register blueprint with app
    app.register_blueprint(auth_bp)
