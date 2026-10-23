"""
Onboarding API utilities for frontend integration - marks the onboarding
wizard (pages/onboarding.py) complete for the current user, with an
optional SKKNI target role/level from its "Choose Your Path" step.

Thin httpx wrapper around the backend's /api/auth/onboarding/complete
endpoint, matching the {"success": bool, ...}-never-raises convention used
by the other api utils (see utils/profile_api.py).
"""

import httpx
import streamlit as st
from config import backend_endpoint

_TIMEOUT = 20


def complete_onboarding(target_role: str = None, target_level: int = None) -> dict:
    """Mark the current user's onboarding as complete."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.post(
            f"{backend_endpoint}api/auth/onboarding/complete",
            json={"user_id": user_id, "target_role": target_role, "target_level": target_level},
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
