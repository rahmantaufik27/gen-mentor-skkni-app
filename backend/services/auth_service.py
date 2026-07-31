"""Authentication service for user registration and login."""

import bcrypt
import uuid
from typing import Optional, Tuple
from config.database import get_db_connection
from psycopg2 import Error


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
        salt = bcrypt.gensalt(rounds=12)
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
        
        if not password or len(password) < 8:
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
