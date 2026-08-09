"""
Practice API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/practice/* endpoints,
mirroring utils/quiz_api.py's start/get_question/submit_answer/complete
shape for UI/UX parity with Test. Every function returns a
{"success": bool, ...} dict and never raises.
"""

import httpx
import streamlit as st
from config import backend_endpoint


def start_practice() -> dict:
    """
    Start a new practice session, sourced from the user's recommended
    questions (see components/practice.py).

    Returns:
        Dictionary with session info and first question
    """
    try:
        url = f"{backend_endpoint}api/practice/start"
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}

        data = {"user_id": user_id}
        response = httpx.post(url, json=data, timeout=30)

        if response.status_code in (200, 400):
            return response.json()
        else:
            return {"success": False, "error": f"Server error: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_question(session_id: str, question_index: int) -> dict:
    """
    Get a specific question from the practice session

    Args:
        session_id: ID of the practice session
        question_index: Index of the question (0-based)

    Returns:
        Dictionary with question data
    """
    try:
        url = f"{backend_endpoint}api/practice/question/{session_id}/{question_index}"
        response = httpx.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def submit_answer(session_id: str, question_index: int, selected_answer: str) -> dict:
    """
    Submit an answer for a practice question

    Args:
        session_id: ID of the practice session
        question_index: Index of the question (0-based)
        selected_answer: Selected choice ID (A, B, C, or D)

    Returns:
        Dictionary with result
    """
    try:
        url = f"{backend_endpoint}api/practice/submit-answer"
        data = {
            "session_id": session_id,
            "question_index": question_index,
            "selected_answer": selected_answer
        }
        response = httpx.post(url, json=data, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def complete_practice(session_id: str) -> dict:
    """
    Complete the practice session and get the results summary. Never
    affects mastery status/quiz history - Test remains the sole source of
    mastery truth. A lightweight session summary is saved server-side
    purely for get_practice_analytics() below.

    Args:
        session_id: ID of the practice session

    Returns:
        Dictionary with results
    """
    try:
        url = f"{backend_endpoint}api/practice/complete/{session_id}"
        response = httpx.post(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_practice_analytics() -> dict:
    """
    Get the current user's Practice Analytics dashboard summary.

    Returns:
        Dictionary with total_sessions and a progression list of
        {completed_at, unit_code, unit_mastery_level, level_rank}
    """
    try:
        url = f"{backend_endpoint}api/practice/analytics"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id}
        response = httpx.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Learning Path statistics
#
# Backed by the standalone /api/learning-path/* module (see
# backend/services/learning_path_stats_service.py). Exposed here so the
# frontend has a single, stable practice_api entry point for Learning Path
# dashboard metrics. New metrics show up as new keys in the get_learning_path_stats()
# payload - no change to these function signatures is needed to add one.
# ---------------------------------------------------------------------------

# Well-known activity types (mirror the backend constants). Passing a new
# string here is all it takes to start tracking a new countable metric.
ACTIVITY_MATERIAL_VIEW = "material_view"
ACTIVITY_CHATBOT_PROMPT = "chatbot_prompt"


def get_learning_path_stats() -> dict:
    """
    Get the current user's aggregated Learning Path statistics.

    Returns:
        {"success": True, latest_practice_score, average_practice_score,
         mastered_units, remedial_units, total_units, materials_viewed,
         latest_material_activity, chatbot_attempts, latest_chatbot_interaction,
         latest_practice_interaction, ...} or {"success": False, "error": str}
    """
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}

        url = f"{backend_endpoint}api/learning-path/stats"
        response = httpx.get(url, params={"user_id": user_id}, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def record_activity(activity_type: str, metadata: dict = None) -> dict:
    """
    Record one Learning Path activity event for the current user.

    Fire-and-forget from the caller's perspective: it never raises, so a
    tracking failure can't break the feature the user is actually using.

    Args:
        activity_type: e.g. ACTIVITY_MATERIAL_VIEW, ACTIVITY_CHATBOT_PROMPT,
            or any new metric's own string.
        metadata: optional per-event detail (e.g. {"unit_code": ...}).
    """
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}

        url = f"{backend_endpoint}api/learning-path/activity"
        payload = {"user_id": user_id, "activity_type": activity_type}
        if metadata:
            payload["metadata"] = metadata
        response = httpx.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def record_material_view(unit_code: str = None) -> dict:
    """Count that the user opened a material (see reading_materials.py)."""
    metadata = {"unit_code": unit_code} if unit_code else None
    return record_activity(ACTIVITY_MATERIAL_VIEW, metadata)


def record_chatbot_attempt() -> dict:
    """Count that the user sent a chatbot prompt (see components/chatbot.py)."""
    return record_activity(ACTIVITY_CHATBOT_PROMPT)
