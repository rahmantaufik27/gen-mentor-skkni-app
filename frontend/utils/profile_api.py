"""
User Profile API utilities for frontend integration - identity, password,
and profile photo (My Profile page).

Thin httpx wrappers around the backend's /api/auth/profile*,
/api/auth/change-password endpoints, matching the
{"success": bool, ...}-never-raises convention used by the other api utils.
"""

import httpx
import streamlit as st
from config import backend_endpoint

_TIMEOUT = 20


def get_profile() -> dict:
    """Get the current user's full profile (identity fields, incl. photo)."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.get(
            f"{backend_endpoint}api/auth/profile", params={"user_id": user_id}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_profile(full_name: str) -> dict:
    """Update the current user's full_name."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.put(
            f"{backend_endpoint}api/auth/profile",
            json={"user_id": user_id, "full_name": full_name}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def change_password(current_password: str, new_password: str) -> dict:
    """Change the current user's password."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.post(
            f"{backend_endpoint}api/auth/change-password",
            json={"user_id": user_id, "current_password": current_password, "new_password": new_password},
            timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_profile_photo(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """Upload a new profile photo (PNG/JPG) for the current user."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.post(
            f"{backend_endpoint}api/auth/profile-photo",
            data={"user_id": user_id},
            files={"photo": (filename, file_bytes, content_type or "image/jpeg")},
            timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def profile_photo_url(user_id: str) -> str:
    """Direct URL to a user's uploaded profile photo (fetched client-side
    by st.image() in the browser - CORS is already wide open, see app.py)."""
    return f"{backend_endpoint}api/auth/profile-photo/{user_id}"
