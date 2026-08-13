"""
Learning Reflection API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/reflection/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by the other api utils.

Question text/keys/types come from the backend config (get_reflection_questions);
answers are per-user and keyed by the stable question_key.
"""

import httpx
import streamlit as st
from config import backend_endpoint

_TIMEOUT = 20


def get_reflection_questions() -> dict:
    """Return the reflection question configuration (sections + questions)."""
    try:
        response = httpx.get(f"{backend_endpoint}api/reflection/questions", timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_reflection_answers() -> dict:
    """Return the current user's saved answers, keyed by question_key."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.get(
            f"{backend_endpoint}api/reflection/answers",
            params={"user_id": user_id}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def save_reflection_answer(question_key: str, answer_text: str = None, answer_number: int = None) -> dict:
    """Create or update the current user's answer to one question (upsert)."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {"user_id": user_id, "question_key": question_key}
        if answer_text is not None:
            payload["answer_text"] = answer_text
        if answer_number is not None:
            payload["answer_number"] = answer_number
        response = httpx.post(f"{backend_endpoint}api/reflection/answers", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        # Surface the backend's specific validation error when present.
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_reflection_answer(question_key: str) -> dict:
    """Delete the current user's answer to one question."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.request(
            "DELETE", f"{backend_endpoint}api/reflection/answers",
            json={"user_id": user_id, "question_key": question_key}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
