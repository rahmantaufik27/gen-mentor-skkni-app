"""
Authentication controller for handling auth requests.

Parses/validates request JSON, delegates business logic to
AuthenticationService, and translates results into Flask JSON responses.
"""

import glob
import os

from flask import request, jsonify, session, send_from_directory
from services.auth_service import AuthenticationService
from services.learning_path_stats_service import LearningPathStatsService, ACTIVITY_LOGIN

# backend/storage/profile_photos/ - uploaded profile photos, one file per
# user (named "<user_id>.<ext>"). users.profile_photo_path stores just the
# filename; this is where it actually lives on disk.
_PHOTO_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "profile_photos",
)
_ALLOWED_PHOTO_EXTENSIONS = (".png", ".jpg", ".jpeg")


class AuthController:
    """Handles authentication endpoints logic."""
    
    @staticmethod
    def register():
        """
        Handle user registration request.
        
        Expected JSON body:
        {
            "full_name": "John Doe",
            "email": "john@example.com",
            "password": "password123",
            "confirm_password": "password123"
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body is required"}), 400
            
            full_name = data.get("full_name", "").strip()
            email = data.get("email", "").strip()
            password = data.get("password", "")
            confirm_password = data.get("confirm_password", "")
            
            # Validate required fields
            if not full_name:
                return jsonify({"error": "Full name is required"}), 400
            
            if not email:
                return jsonify({"error": "Email is required"}), 400
            
            if not password:
                return jsonify({"error": "Password is required"}), 400
            
            # Validate password length
            if len(password) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            
            # Check password confirmation
            if password != confirm_password:
                return jsonify({"error": "Passwords do not match"}), 400
            
            # Validate email format (basic check)
            if "@" not in email or "." not in email:
                return jsonify({"error": "Invalid email format"}), 400
            
            # Register user
            success, message, user_id = AuthenticationService.register_user(
                full_name, email, password
            )
            
            if success:
                return jsonify({
                    "message": message,
                    "user_id": user_id,
                    "success": True
                }), 201
            else:
                # 409 for duplicate email, 400 for other validation errors
                status_code = 409 if "already registered" in message else 400
                return jsonify({
                    "error": message,
                    "success": False
                }), status_code
        
        except Exception as e:
            return jsonify({
                "error": f"Registration error: {str(e)}",
                "success": False
            }), 500
    
    @staticmethod
    def login():
        """
        Handle user login request.
        
        Expected JSON body:
        {
            "email": "john@example.com",
            "password": "password123"
        }
        """
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({"error": "Request body is required"}), 400
            
            email = data.get("email", "").strip()
            password = data.get("password", "")
            
            if not email or not password:
                return jsonify({"error": "Email and password are required"}), 400
            
            # Authenticate user
            success, message, user_data = AuthenticationService.login_user(email, password)
            
            if success:
                # Store user info in the signed session cookie (see app.py SECRET_KEY)
                session["user_id"] = user_data["id"]
                session["user_name"] = user_data["full_name"]
                session["user_email"] = user_data["email"]

                # Fire-and-forget: feeds the My Profile "Engagement" section
                # (login frequency, streaks). Never blocks or fails login.
                try:
                    LearningPathStatsService().record_activity(user_data["id"], ACTIVITY_LOGIN)
                except Exception:
                    pass

                return jsonify({
                    "message": message,
                    "user": user_data,
                    "success": True
                }), 200
            else:
                return jsonify({
                    "error": message,
                    "success": False
                }), 401
        
        except Exception as e:
            return jsonify({
                "error": f"Login error: {str(e)}",
                "success": False
            }), 500
    
    @staticmethod
    def logout():
        """Handle user logout request."""
        try:
            session.clear()
            return jsonify({
                "message": "Logged out successfully",
                "success": True
            }), 200
        except Exception as e:
            return jsonify({
                "error": f"Logout error: {str(e)}",
                "success": False
            }), 500
    
    @staticmethod
    def get_current_user():
        """Get current authenticated user information."""
        try:
            user_id = session.get("user_id")
            
            if not user_id:
                return jsonify({
                    "error": "Not authenticated",
                    "success": False
                }), 401
            
            # Get user from database to ensure data is current
            user_data = AuthenticationService.get_user_by_id(user_id)
            
            if not user_data:
                session.clear()
                return jsonify({
                    "error": "User not found",
                    "success": False
                }), 404
            
            return jsonify({
                "user": user_data,
                "success": True
            }), 200
        
        except Exception as e:
            return jsonify({
                "error": f"Error retrieving user: {str(e)}",
                "success": False
            }), 500
    
    @staticmethod
    def is_authenticated():
        """Check if user is authenticated."""
        return "user_id" in session and session.get("user_id") is not None

    # -- My Profile: identity / password / photo ----------------------------

    @staticmethod
    def get_profile():
        """Get a user's full profile (identity fields, incl. profile_photo_path)."""
        try:
            user_id = request.args.get("user_id")
            if not user_id:
                return jsonify({"success": False, "error": "user_id is required"}), 400

            user_data = AuthenticationService.get_user_by_id(user_id)
            if not user_data:
                return jsonify({"success": False, "error": "User not found"}), 404
            return jsonify({"success": True, "user": user_data}), 200
        except Exception as e:
            return jsonify({"success": False, "error": f"Error retrieving profile: {str(e)}"}), 500

    @staticmethod
    def update_profile():
        """Update a user's full_name (My Profile page)."""
        try:
            data = request.get_json() or {}
            user_id = data.get("user_id")
            full_name = data.get("full_name", "")
            if not user_id:
                return jsonify({"success": False, "error": "user_id is required"}), 400

            success, message = AuthenticationService.update_profile(user_id, full_name)
            if success:
                # Keep the session cookie's cached name current too, so the
                # header user-chip reflects the new name for the rest of
                # this browser session without needing to log back in.
                if session.get("user_id") == user_id:
                    session["user_name"] = full_name.strip()
                return jsonify({"success": True, "message": message}), 200
            return jsonify({"success": False, "error": message}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Error updating profile: {str(e)}"}), 500

    @staticmethod
    def complete_onboarding():
        """Mark the onboarding wizard complete for a user, optionally recording
        their chosen SKKNI target role/level (onboarding's "Choose Your Path" step)."""
        try:
            data = request.get_json() or {}
            user_id = data.get("user_id")
            if not user_id:
                return jsonify({"success": False, "error": "user_id is required"}), 400

            target_role = data.get("target_role")
            target_level = data.get("target_level")

            success, message = AuthenticationService.complete_onboarding(user_id, target_role, target_level)
            if success:
                return jsonify({"success": True, "message": message}), 200
            return jsonify({"success": False, "error": message}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Error completing onboarding: {str(e)}"}), 500

    @staticmethod
    def change_password():
        """Change a user's password (My Profile page)."""
        try:
            data = request.get_json() or {}
            user_id = data.get("user_id")
            current_password = data.get("current_password", "")
            new_password = data.get("new_password", "")
            if not user_id:
                return jsonify({"success": False, "error": "user_id is required"}), 400

            success, message = AuthenticationService.change_password(user_id, current_password, new_password)
            if success:
                return jsonify({"success": True, "message": message}), 200
            return jsonify({"success": False, "error": message}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Error changing password: {str(e)}"}), 500

    @staticmethod
    def upload_profile_photo():
        """
        Save an uploaded profile photo to disk and point
        users.profile_photo_path at it. Multipart form data (not JSON):
        "user_id" field + "photo" file.
        """
        try:
            user_id = request.form.get("user_id")
            if not user_id:
                return jsonify({"success": False, "error": "user_id is required"}), 400

            photo = request.files.get("photo")
            if not photo or not photo.filename:
                return jsonify({"success": False, "error": "No photo file provided"}), 400

            ext = os.path.splitext(photo.filename)[1].lower()
            if ext not in _ALLOWED_PHOTO_EXTENSIONS:
                return jsonify({"success": False, "error": "Only PNG/JPG images are supported"}), 400

            os.makedirs(_PHOTO_STORAGE_DIR, exist_ok=True)

            # Remove any previous photo for this user first, in case its
            # extension differs from the new one (e.g. old .png, new .jpg) -
            # otherwise the stale file would just sit there unused.
            for existing in glob.glob(os.path.join(_PHOTO_STORAGE_DIR, f"{user_id}.*")):
                try:
                    os.remove(existing)
                except OSError:
                    pass

            filename = f"{user_id}{ext}"
            photo.save(os.path.join(_PHOTO_STORAGE_DIR, filename))

            success, message = AuthenticationService.update_profile_photo_path(user_id, filename)
            if success:
                return jsonify({"success": True, "message": message, "filename": filename}), 200
            return jsonify({"success": False, "error": message}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Error uploading photo: {str(e)}"}), 500

    @staticmethod
    def get_profile_photo(user_id: str):
        """Serve a user's uploaded profile photo file directly (used as the
        src for st.image() on the frontend - see utils/profile_api.py)."""
        try:
            user_data = AuthenticationService.get_user_by_id(user_id)
            filename = user_data.get("profile_photo_path") if user_data else None
            if not filename:
                return jsonify({"success": False, "error": "No photo uploaded"}), 404
            return send_from_directory(_PHOTO_STORAGE_DIR, filename)
        except Exception as e:
            return jsonify({"success": False, "error": f"Error retrieving photo: {str(e)}"}), 500
