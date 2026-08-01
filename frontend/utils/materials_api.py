"""
Reading Materials API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/materials/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by utils/quiz_api.py.
"""

import httpx
import streamlit as st
from config import backend_endpoint


def get_all_materials() -> dict:
    """
    Get every reading material.

    Returns:
        Dictionary with a "materials" list
    """
    try:
        url = f"{backend_endpoint}api/materials/all"
        response = httpx.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recommended_materials() -> dict:
    """
    Get materials recommended for the current user based on their mastery gaps.

    Returns:
        Dictionary with a "materials" list and an "all_mastered" flag
    """
    try:
        url = f"{backend_endpoint}api/materials/recommended"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id}
        response = httpx.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
