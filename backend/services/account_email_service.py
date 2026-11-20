"""
Email verification and password reset.

Both work the same way: a random one-time token is emailed as a link, and
only its SHA-256 hash is stored (auth_tokens). A token works once, expires,
and issuing a new one for the same purpose cancels the older ones.

Everything here is a no-op / "not configured" while email sending is off
(see config/mail.py), so the app behaves as before until mail.ini exists.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from config.database import execute_query
from config.mail import app_url, mail_enabled, send_email

PURPOSE_VERIFY = "verify"
PURPOSE_RESET = "reset"
VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)

# Same reply whether or not the address has an account, so this endpoint
# can't be used to find out who is registered.
_GENERIC_RESET_REPLY = "If that email has an account, a reset link has been sent. It expires in 30 minutes."
_GENERIC_RESEND_REPLY = "If that email has an unconfirmed account, a new confirmation link has been sent."


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_token(user_id: str, purpose: str, ttl: timedelta) -> str:
    execute_query(
        "UPDATE auth_tokens SET used_at = NOW() WHERE user_id = %s AND purpose = %s AND used_at IS NULL",
        (user_id, purpose),
    )
    token = secrets.token_urlsafe(32)
    execute_query(
        "INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at) VALUES (%s, %s, %s, %s)",
        (user_id, purpose, _hash(token), datetime.now() + ttl),
    )
    return token


def _consume_token(token: str, purpose: str) -> Optional[str]:
    """Return the token's user_id and mark it used, or None if it is
    unknown, already used, or expired."""
    token_hash = _hash(token or "")
    # Read, then mark used in a second statement: execute_query(fetch=True)
    # never commits, so an UPDATE ... RETURNING here would not persist.
    rows = execute_query(
        """
        SELECT user_id FROM auth_tokens
        WHERE token_hash = %s AND purpose = %s AND used_at IS NULL AND expires_at > NOW()
        """,
        (token_hash, purpose),
        fetch=True,
    )
    if not rows:
        return None
    execute_query("UPDATE auth_tokens SET used_at = NOW() WHERE token_hash = %s AND used_at IS NULL", (token_hash,))
    return str(rows[0][0])


def send_verification_email(user_id: str, full_name: str, email: str) -> None:
    token = _issue_token(user_id, PURPOSE_VERIFY, VERIFY_TTL)
    link = f"{app_url()}/login?verify={token}"
    send_email(
        email,
        "Confirm your GAMASKILL email",
        f"Hi {full_name},\n\n"
        "Thanks for registering at GAMASKILL. Open this link to confirm your email address:\n\n"
        f"{link}\n\n"
        "The link works once and expires in 24 hours. If you didn't create this account, ignore this email.\n",
    )


def verify_email(token: str) -> Tuple[bool, str]:
    user_id = _consume_token(token, PURPOSE_VERIFY)
    if not user_id:
        return False, "This confirmation link is invalid or has expired. Sign in to request a new one."
    execute_query("UPDATE users SET email_verified = TRUE, updated_at = NOW() WHERE id = %s", (user_id,))
    return True, "Email confirmed. You can sign in now."


def resend_verification(email: str) -> Tuple[bool, str]:
    if not mail_enabled():
        return False, "Email is not set up on this server."
    rows = execute_query(
        "SELECT id, full_name, email FROM users WHERE email = %s AND email_verified = FALSE",
        ((email or "").lower().strip(),),
        fetch=True,
    )
    if rows:
        user_id, full_name, db_email = rows[0]
        try:
            send_verification_email(str(user_id), full_name, db_email)
        except Exception as e:
            return False, f"Could not send the email: {str(e)}"
    return True, _GENERIC_RESEND_REPLY


def request_password_reset(email: str) -> Tuple[bool, str]:
    if not mail_enabled():
        return False, "Password reset by email is not set up on this server. Please contact the administrator."
    rows = execute_query(
        "SELECT id, full_name, email FROM users WHERE email = %s",
        ((email or "").lower().strip(),),
        fetch=True,
    )
    if rows:
        user_id, full_name, db_email = rows[0]
        token = _issue_token(str(user_id), PURPOSE_RESET, RESET_TTL)
        link = f"{app_url()}/login?reset={token}"
        try:
            send_email(
                db_email,
                "Reset your GAMASKILL password",
                f"Hi {full_name},\n\n"
                "We received a request to reset your GAMASKILL password. Open this link to choose a new one:\n\n"
                f"{link}\n\n"
                "The link works once and expires in 30 minutes. If you didn't ask for this, ignore this email - "
                "your password stays the same.\n",
            )
        except Exception as e:
            return False, f"Could not send the email: {str(e)}"
    return True, _GENERIC_RESET_REPLY


def reset_password(token: str, new_password: str, hash_password) -> Tuple[bool, str]:
    if not new_password or len(new_password) < 8:
        return False, "Password must be at least 8 characters"
    user_id = _consume_token(token, PURPOSE_RESET)
    if not user_id:
        return False, "This reset link is invalid or has expired. Request a new one from the sign-in page."
    # Opening the emailed link also proves the mailbox, so confirm the email.
    execute_query(
        "UPDATE users SET password_hash = %s, email_verified = TRUE, updated_at = NOW() WHERE id = %s",
        (hash_password(new_password), user_id),
    )
    return True, "Password updated. You can sign in with your new password."
