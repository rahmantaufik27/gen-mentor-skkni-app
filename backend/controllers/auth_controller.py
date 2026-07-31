"""Authentication controller for handling auth requests."""

from flask import request, jsonify, session
from services.auth_service import AuthenticationService


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
                # Store user info in session
                session["user_id"] = user_data["id"]
                session["user_name"] = user_data["full_name"]
                session["user_email"] = user_data["email"]
                
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
