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
