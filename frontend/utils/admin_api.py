"""
Admin API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/admin/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by the other
utils/*_api.py modules.
"""

import httpx
from config import backend_endpoint


def admin_login(email: str, password: str) -> dict:
    """
    Verify admin credentials with the backend.

    Returns:
        Dictionary with success/message or error
    """
    try:
        url = f"{backend_endpoint}api/admin/login"
        response = httpx.post(url, json={"email": email, "password": password}, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return response.json() if response.content else {"success": False, "error": f"Status code: {response.status_code}"}
    except httpx.ConnectError:
        return {"success": False, "error": "Cannot connect to backend server. Make sure it's running on localhost:5000"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def admin_logout() -> dict:
    """Clear the admin session on the backend (best-effort)."""
    try:
        url = f"{backend_endpoint}api/admin/logout"
        response = httpx.post(url, timeout=10)
        return response.json() if response.content else {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_all_users_inference_method(inference_method: str) -> dict:
    """
    Bulk-update inference_method for every user.

    Args:
        inference_method: 'DBN' or 'Manual'

    Returns:
        Dictionary with success/message/updated_count or error
    """
    try:
        url = f"{backend_endpoint}api/admin/users/inference-method"
        response = httpx.put(url, json={"inference_method": inference_method}, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return response.json() if response.content else {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_all_users() -> dict:
    """
    Get every user with their inference_method.

    Returns:
        Dictionary with a "users" list
    """
    try:
        url = f"{backend_endpoint}api/admin/users"
        response = httpx.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
        url = f"{backend_endpoint}api/admin/users/{user_id}/inference-method"
        response = httpx.put(url, json={"inference_method": inference_method}, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return response.json() if response.content else {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
