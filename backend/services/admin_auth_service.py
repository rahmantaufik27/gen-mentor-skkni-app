"""
Admin authentication.

Admin accounts live in the admin_users table (bcrypt password hashes, see
migrations/018_create_admin_users_table.py) - nothing is hardcoded here.

A successful login returns a random token. The frontend sends it back on
every /api/admin/* request in the X-Admin-Token header, and the routes
refuse requests without a valid one - so the admin data (which includes
learners' personal data) is no longer readable by anything that can merely
reach the backend. Tokens are kept in memory: restarting the backend signs
every admin out, and they simply log in again.
"""

import secrets
import time
from typing import List, Optional, Tuple

import bcrypt

from config.database import execute_query

_TOKEN_TTL_SECONDS = 8 * 60 * 60
_tokens = {}  # token -> (admin email, expiry timestamp)


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _matches(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


class AdminAuthService:
    """Verifies admin credentials against admin_users and manages login tokens."""

    @staticmethod
    def verify_credentials(email: str, password: str) -> bool:
        rows = execute_query(
            "SELECT password_hash FROM admin_users WHERE email = %s AND is_active = TRUE",
            ((email or "").strip().lower(),),
            fetch=True,
        )
        return bool(rows) and _matches(password or "", rows[0][0])

    @staticmethod
    def login(email: str, password: str) -> Optional[str]:
        """Return a new token for valid credentials, else None."""
        email = (email or "").strip().lower()
        if not AdminAuthService.verify_credentials(email, password):
            return None
        execute_query("UPDATE admin_users SET last_login_at = NOW() WHERE email = %s", (email,))
        token = secrets.token_urlsafe(32)
        _tokens[token] = (email, time.time() + _TOKEN_TTL_SECONDS)
        return token

    @staticmethod
    def admin_for_token(token: Optional[str]) -> Optional[str]:
        """The admin email a token belongs to, or None if unknown/expired."""
        entry = _tokens.get(token or "")
        if not entry:
            return None
        email, expires_at = entry
        if time.time() > expires_at:
            _tokens.pop(token, None)
            return None
        return email

    @staticmethod
    def logout(token: Optional[str]) -> None:
        _tokens.pop(token or "", None)

    @staticmethod
    def change_password(email: str, current_password: str, new_password: str) -> Tuple[bool, str]:
        if not new_password or len(new_password) < 8:
            return False, "New password must be at least 8 characters"
        if not AdminAuthService.verify_credentials(email, current_password):
            return False, "Current password is incorrect"
        execute_query("UPDATE admin_users SET password_hash = %s WHERE email = %s", (_hash(new_password), email))
        return True, "Password changed"

    @staticmethod
    def list_admins() -> List[dict]:
        rows = execute_query(
            "SELECT email, full_name, is_active, created_at, last_login_at FROM admin_users ORDER BY created_at",
            fetch=True,
        ) or []
        return [
            {
                "email": email, "full_name": full_name, "is_active": is_active,
                "created_at": created_at.isoformat() if created_at else None,
                "last_login_at": last_login_at.isoformat() if last_login_at else None,
            }
            for email, full_name, is_active, created_at, last_login_at in rows
        ]

    @staticmethod
    def add_admin(email: str, full_name: str, password: str) -> Tuple[bool, str]:
        email = (email or "").strip().lower()
        if "@" not in email or "." not in email:
            return False, "Enter a valid email address"
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters"
        if execute_query("SELECT 1 FROM admin_users WHERE email = %s", (email,), fetch=True):
            return False, "An admin with that email already exists"
        execute_query(
            "INSERT INTO admin_users (email, full_name, password_hash) VALUES (%s, %s, %s)",
            (email, (full_name or "Admin").strip() or "Admin", _hash(password)),
        )
        return True, f"Admin account created for {email}"

    @staticmethod
    def set_active(email: str, is_active: bool, acting_admin: str) -> Tuple[bool, str]:
        email = (email or "").strip().lower()
        if email == acting_admin and not is_active:
            return False, "You can't deactivate your own account"
        execute_query("UPDATE admin_users SET is_active = %s WHERE email = %s", (is_active, email))
        if not is_active:
            for token, (token_email, _) in list(_tokens.items()):
                if token_email == email:
                    _tokens.pop(token, None)
        return True, f"{email} {'activated' if is_active else 'deactivated'}"
