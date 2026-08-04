"""
Controller for the Admin module: admin login/logout and user management
(listing, per-user and bulk inference_method updates).
"""

from flask import session
from services.auth_service import AuthenticationService
from services.admin_auth_service import AdminAuthService


class AdminController:
    """Controller for admin authentication and user-management operations."""

    @staticmethod
    def login(email: str, password: str) -> dict:
        """
        Verify admin credentials.

        Args:
            email: Submitted admin email
            password: Submitted admin password

        Returns:
            Dictionary with success/message or error
        """
        try:
            if AdminAuthService.verify_credentials(email, password):
                # Stored for parity with the learner session, though the
                # frontend doesn't rely on cookies persisting across
                # requests (see routes/admin_routes.py) - the actual gate
                # is enforced client-side, same as the learner flow.
                session["is_admin"] = True
                session["admin_email"] = email.strip().lower()
                return {"success": True, "message": "Admin login successful"}
            return {"success": False, "error": "Invalid admin email or password"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def logout() -> dict:
        """Clear the admin session."""
        try:
            session.pop("is_admin", None)
            session.pop("admin_email", None)
            return {"success": True, "message": "Admin logged out successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_all_users() -> dict:
        """
        List all users with their inference_method.

        Returns:
            Dictionary with a "users" list
        """
        try:
            users = AuthenticationService.get_all_users()
            return {"success": True, "users": users}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_inference_method(user_id: str, inference_method: str) -> dict:
        """
        Update a user's inference_method preference.

        Args:
            user_id: ID of the user
            inference_method: 'DBN' or 'Manual'

        Returns:
            Dictionary with success/message or error
        """
        try:
            success, message = AuthenticationService.update_inference_method(user_id, inference_method)
            if success:
                return {"success": True, "message": message}
            return {"success": False, "error": message}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_all_users_inference_method(inference_method: str) -> dict:
        """
        Set inference_method for every user at once (bulk action).

        Args:
            inference_method: 'DBN' or 'Manual'

        Returns:
            Dictionary with success/message/updated_count or error
        """
        try:
            success, message, updated_count = AuthenticationService.update_all_users_inference_method(inference_method)
            if success:
                return {"success": True, "message": message, "updated_count": updated_count}
            return {"success": False, "error": message}
        except Exception as e:
            return {"success": False, "error": str(e)}
