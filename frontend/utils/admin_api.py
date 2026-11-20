"""
Admin API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/admin/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by the other
utils/*_api.py modules.

Every call except login sends the token issued at login (kept in
st.session_state.admin_token) in the X-Admin-Token header. If the backend
answers "sign-in required" (token expired, or the backend restarted), the
admin session is cleared so the dashboard sends the admin back to login.
"""

import httpx
import streamlit as st

from config import backend_endpoint


def _request(method: str, path: str, json: dict = None, params: dict = None, timeout: int = 60):
    """Returns the httpx response, or a dict {"success": False, "error"} on failure."""
    try:
        response = httpx.request(
            method, f"{backend_endpoint}api/admin/{path}", json=json, params=params, timeout=timeout,
            headers={"X-Admin-Token": st.session_state.get("admin_token") or ""},
        )
    except httpx.ConnectError:
        return {"success": False, "error": "Cannot connect to backend server. Make sure it's running on localhost:5000"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    if response.status_code == 401 and path != "login":
        st.session_state.admin_logged_in = False
        st.session_state.admin_token = None
    return response


def _json(method: str, path: str, json: dict = None, params: dict = None, timeout: int = 60) -> dict:
    response = _request(method, path, json, params, timeout)
    if isinstance(response, dict):
        return response
    try:
        return response.json()
    except Exception:
        return {"success": False, "error": f"Status code: {response.status_code}"}


def admin_login(email: str, password: str) -> dict:
    """Verify admin credentials; on success the result carries the session token."""
    return _json("POST", "login", {"email": email, "password": password}, timeout=10)


def admin_logout() -> dict:
    """End the admin session on the backend (best-effort)."""
    return _json("POST", "logout", timeout=10)


def get_all_users() -> dict:
    return _json("GET", "users", timeout=30)


def update_all_users_inference_method(inference_method: str) -> dict:
    return _json("PUT", "users/inference-method", {"inference_method": inference_method}, timeout=30)


def update_inference_method(user_id: str, inference_method: str) -> dict:
    return _json("PUT", f"users/{user_id}/inference-method", {"inference_method": inference_method}, timeout=30)


def admin_view(name: str, **params) -> dict:
    """Data for one admin console page (see backend AdminConsoleService.<name>_view)."""
    return _json("GET", f"view/{name}", params={k: v for k, v in params.items() if v not in (None, "")})


def admin_learner(user_id: str) -> dict:
    return _json("GET", f"learner/{user_id}")


def admin_lesson(unit_code: str, subtopic_index: int) -> dict:
    return _json("GET", "lesson", params={"unit": unit_code, "index": subtopic_index})


def admin_admins() -> dict:
    return _json("GET", "admins")


def admin_action(name: str, **payload) -> dict:
    return _json("POST", f"action/{name}", payload, timeout=120)


def admin_export(key: str, anonymize: bool, include_test: bool) -> str:
    """CSV text for one dataset, or "" if it could not be fetched."""
    response = _request("GET", f"export/{key}", params={"anonymize": "1" if anonymize else "0",
                                                         "include_test": "1" if include_test else "0"})
    if isinstance(response, dict) or response.status_code != 200:
        return ""
    return response.text
