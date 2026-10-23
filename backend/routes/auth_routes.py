"""Authentication routes - thin HTTP layer delegating to AuthController."""

from flask import Blueprint
from controllers.auth_controller import AuthController

# All endpoints below are mounted under /api/auth/*
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

    # -- My Profile: identity / password / photo -----------------------

    @auth_bp.route("/profile", methods=["GET"])
    def get_profile():
        """Get a user's full profile endpoint."""
        return AuthController.get_profile()

    @auth_bp.route("/profile", methods=["PUT"])
    def update_profile():
        """Update a user's identity fields endpoint."""
        return AuthController.update_profile()

    @auth_bp.route("/change-password", methods=["POST"])
    def change_password():
        """Change a user's password endpoint."""
        return AuthController.change_password()

    @auth_bp.route("/onboarding/complete", methods=["POST"])
    def complete_onboarding():
        """Mark the onboarding wizard complete endpoint."""
        return AuthController.complete_onboarding()

    @auth_bp.route("/profile-photo", methods=["POST"])
    def upload_profile_photo():
        """Upload a user's profile photo endpoint."""
        return AuthController.upload_profile_photo()

    @auth_bp.route("/profile-photo/<user_id>", methods=["GET"])
    def get_profile_photo(user_id):
        """Serve a user's profile photo file endpoint."""
        return AuthController.get_profile_photo(user_id)

    # Register blueprint with app
    app.register_blueprint(auth_bp)
