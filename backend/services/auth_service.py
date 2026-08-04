"""
Authentication service for user registration and login.

Passwords are hashed with bcrypt (never stored in plain text); sessions are
Flask server-side cookie sessions (see AuthController), not JWT.
"""

import bcrypt
import uuid
from typing import Optional, Tuple, List
from services.neo4j_service import get_neo4j_service
from config.database import get_db_connection
from psycopg2 import Error

# Valid mastery-inference engine choices for users.inference_method.
# 'DBN' is the default for new users; only 'Manual' has an actual inference
# implementation today (see services/mastery_service.py) - the DBN engine
# is added later without any schema/UI change, per the modular design.
INFERENCE_METHOD_DBN = "DBN"
INFERENCE_METHOD_MANUAL = "Manual"
VALID_INFERENCE_METHODS = (INFERENCE_METHOD_DBN, INFERENCE_METHOD_MANUAL)
DEFAULT_INFERENCE_METHOD = INFERENCE_METHOD_DBN


class AuthenticationService:
    """Handles user authentication, registration, and password management."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt(rounds=12)  # cost factor: higher = slower/safer against brute force
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Plain text password
            password_hash: Hashed password from database
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False
    
    @staticmethod
    def email_exists(email: str) -> bool:
        """
        Check if email already exists in database.
        
        Args:
            email: Email address to check
            
        Returns:
            True if email exists, False otherwise
        """
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            # Emails are always stored/compared lowercase for case-insensitive uniqueness
            cursor.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except Error as e:
            raise Exception(f"Database error checking email: {str(e)}")
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    def register_user(full_name: str, email: str, password: str) -> Tuple[bool, str, Optional[str]]:
        """
        Register a new user.
        
        Args:
            full_name: User's full name
            email: User's email address
            password: User's password (will be hashed)
            
        Returns:
            Tuple of (success: bool, message: str, user_id: Optional[str])
        """
        # Validate inputs
        if not full_name or not full_name.strip():
            return False, "Full name is required", None
        
        if not email or not email.strip():
            return False, "Email is required", None
        
        if not password or len(password) < 8:  # minimum password length policy
            return False, "Password must be at least 8 characters", None
        
        email = email.lower().strip()
        full_name = full_name.strip()
        
        # Check if email already exists
        if AuthenticationService.email_exists(email):
            return False, "Email already registered", None
        
        # Hash password
        password_hash = AuthenticationService.hash_password(password)
        
        # Create user record
        connection = None
        try:
            user_id = str(uuid.uuid4())
            connection = get_db_connection()
            cursor = connection.cursor()
            
            cursor.execute(
                """
                INSERT INTO users (id, full_name, email, password_hash)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, full_name, email, password_hash)
            )
            
            connection.commit()
            cursor.close()

            # Best-effort sync to the Neo4j knowledge graph (requirement: create
            # a User node on registration). PostgreSQL above is already committed
            # and remains the source of truth - a Neo4j hiccup must not fail registration.
            try:
                get_neo4j_service().sync_user(user_id, full_name, email)
            except Exception as e:
                print(f"Warning: Failed to sync user {user_id} to Neo4j: {str(e)}")

            return True, "User registered successfully", user_id
            
        except Error as e:
            if connection:
                connection.rollback()
            return False, f"Registration failed: {str(e)}", None
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    def login_user(email: str, password: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Authenticate user login.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Tuple of (success: bool, message: str, user_data: Optional[dict])
        """
        if not email or not password:
            return False, "Email and password are required", None
        
        email = email.lower().strip()
        
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            cursor.execute(
                "SELECT id, full_name, email, password_hash FROM users WHERE email = %s",
                (email,)
            )
            
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return False, "Invalid email or password", None
            
            user_id, full_name, db_email, password_hash = result
            
            # Verify password
            if not AuthenticationService.verify_password(password, password_hash):
                return False, "Invalid email or password", None
            
            user_data = {
                "id": str(user_id),
                "full_name": full_name,
                "email": db_email
            }
            
            return True, "Login successful", user_data
            
        except Error as e:
            return False, f"Login failed: {str(e)}", None
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[dict]:
        """
        Retrieve user information by ID.
        
        Args:
            user_id: User UUID
            
        Returns:
            User data dictionary or None if not found
        """
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            
            cursor.execute(
                "SELECT id, full_name, email, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return None
            
            user_id, full_name, email, created_at = result
            return {
                "id": str(user_id),
                "full_name": full_name,
                "email": email,
                "created_at": created_at.isoformat() if created_at else None
            }
            
        except Error as e:
            raise Exception(f"Failed to retrieve user: {str(e)}")
        finally:
            if connection:
                connection.close()

    @staticmethod
    def get_inference_method(user_id: str) -> Optional[str]:
        """
        Load a user's mastery-inference engine preference from the users table.
        Called whenever an inference is required (see mastery_service.py) -
        this is the single source of truth for "which engine to use", not
        user_mastery_level.

        Args:
            user_id: User UUID

        Returns:
            'DBN', 'Manual', or None if the user doesn't exist
        """
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT inference_method FROM users WHERE id = %s", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Error as e:
            raise Exception(f"Failed to retrieve inference method: {str(e)}")
        finally:
            if connection:
                connection.close()

    @staticmethod
    def update_inference_method(user_id: str, inference_method: str) -> Tuple[bool, str]:
        """
        Update a user's mastery-inference engine preference (Admin page).

        Args:
            user_id: User UUID
            inference_method: 'DBN' or 'Manual'

        Returns:
            Tuple of (success: bool, message: str)
        """
        if inference_method not in VALID_INFERENCE_METHODS:
            return False, f"Invalid inference method. Must be one of: {', '.join(VALID_INFERENCE_METHODS)}"

        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET inference_method = %s, updated_at = now() WHERE id = %s",
                (inference_method, user_id)
            )
            updated = cursor.rowcount > 0
            connection.commit()
            cursor.close()

            if not updated:
                return False, "User not found"
            return True, "Inference method updated successfully"
        except Error as e:
            if connection:
                connection.rollback()
            return False, f"Failed to update inference method: {str(e)}"
        finally:
            if connection:
                connection.close()

    @staticmethod
    def update_all_users_inference_method(inference_method: str) -> Tuple[bool, str, int]:
        """
        Set inference_method for every user at once (Admin bulk action).
        Per-user updates via update_inference_method() remain available and
        unaffected by this - a bulk update is just a mass write of the same field.

        Args:
            inference_method: 'DBN' or 'Manual'

        Returns:
            Tuple of (success: bool, message: str, updated_count: int)
        """
        if inference_method not in VALID_INFERENCE_METHODS:
            return False, f"Invalid inference method. Must be one of: {', '.join(VALID_INFERENCE_METHODS)}", 0

        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE users SET inference_method = %s, updated_at = now()",
                (inference_method,)
            )
            updated_count = cursor.rowcount
            connection.commit()
            cursor.close()
            return True, f"Updated {updated_count} user(s) to {inference_method}", updated_count
        except Error as e:
            if connection:
                connection.rollback()
            return False, f"Failed to bulk update inference method: {str(e)}", 0
        finally:
            if connection:
                connection.close()

    @staticmethod
    def get_all_users() -> List[dict]:
        """
        List all users with their inference_method (Admin page).

        Returns:
            List of user dictionaries (id, full_name, email, inference_method, created_at)
        """
        connection = None
        try:
            connection = get_db_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, full_name, email, inference_method, created_at
                FROM users
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            return [
                {
                    "id": str(row[0]),
                    "full_name": row[1],
                    "email": row[2],
                    "inference_method": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                }
                for row in rows
            ]
        except Error as e:
            raise Exception(f"Failed to retrieve users: {str(e)}")
        finally:
            if connection:
                connection.close()
