"""
Quiz API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/quiz/* endpoints. Every
function returns a {"success": bool, ...} dict and never raises - network
or server errors are caught and surfaced as {"success": False, "error": ...}
so calling pages can just check `.get("success")`.
"""

import httpx
import streamlit as st
from config import backend_endpoint


def start_quiz() -> dict:
    """
    Start a new quiz session
    
    Returns:
        Dictionary with session info
    """
    try:
        url = f"{backend_endpoint}api/quiz/start"
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        
        data = {"user_id": user_id}
        response = httpx.post(url, json=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 400:
            return response.json()
        else:
            return {"success": False, "error": f"Server error: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_question(session_id: str, question_index: int) -> dict:
    """
    Get a specific question from the quiz
    
    Args:
        session_id: ID of the quiz session
        question_index: Index of the question (0-based)
        
    Returns:
        Dictionary with question data
    """
    try:
        url = f"{backend_endpoint}api/quiz/question/{session_id}/{question_index}"
        response = httpx.get(url, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def submit_answer(session_id: str, question_index: int, selected_answer: str) -> dict:
    """
    Submit an answer for a question
    
    Args:
        session_id: ID of the quiz session
        question_index: Index of the question (0-based)
        selected_answer: Selected choice ID (A, B, C, or D)
        
    Returns:
        Dictionary with result
    """
    try:
        url = f"{backend_endpoint}api/quiz/submit-answer"
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


def get_progress(session_id: str) -> dict:
    """
    Get quiz progress
    
    Args:
        session_id: ID of the quiz session
        
    Returns:
        Dictionary with progress info
    """
    try:
        url = f"{backend_endpoint}api/quiz/progress/{session_id}"
        response = httpx.get(url, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def complete_quiz(session_id: str) -> dict:
    """
    Complete the quiz and save results
    
    Args:
        session_id: ID of the quiz session
        
    Returns:
        Dictionary with results and mastery information
    """
    try:
        url = f"{backend_endpoint}api/quiz/complete/{session_id}"
        user_id = st.session_state.get("userId")
        data = {"user_id": user_id}
        response = httpx.post(url, json=data, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_mastery_summary() -> dict:
    """
    Get the current user's unit mastery-level dashboard summary.

    Returns:
        Dictionary with current_status, total_attempts, latest_attempt_date,
        and per-unit mastery data (unit_code, unit_score, unit_mastery_level,
        target_level, mastery_status)
    """
    try:
        url = f"{backend_endpoint}api/quiz/mastery-summary"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id}
        response = httpx.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_test_analytics() -> dict:
    """
    Get the current user's per-stage (Pre-Test / Post-Test) analytics.

    Returns:
        Dictionary with a "stages" map: {"pre": {...}|None, "post": {...}|None},
        each stage carrying completed_at, status, score, and per-unit mastery
        (unit_code, unit_score, unit_mastery_level, target_level, mastery_status).
    """
    try:
        url = f"{backend_endpoint}api/quiz/test-analytics"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id}
        response = httpx.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_unit_code_map() -> dict:
    """
    Get the truncated -> full unit_code map (static, not user-specific) -
    used to display full unit codes (e.g. "J.620100.005.02") consistently
    everywhere a unit_code is shown, without changing what's stored
    internally (Postgres/session data keep using the truncated code).

    Returns:
        Dictionary with a "unit_codes" map ({truncated: full})
    """
    try:
        url = f"{backend_endpoint}api/quiz/unit-codes"
        response = httpx.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_recommended_questions() -> dict:
    """
    Get adaptive practice questions recommended for the current user's
    weakest units (backed by the Neo4j knowledge graph - see
    backend/services/neo4j_service.py::get_recommended_questions).

    Returns:
        Dictionary with a "questions" list (id, question_text, unit,
        bloom_level, options, mastery_status, target_level)
    """
    try:
        url = f"{backend_endpoint}api/quiz/recommended-questions"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id}
        response = httpx.get(url, params=params, timeout=30)

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_quiz_history(limit: int = 10) -> dict:
    """
    Get user quiz history
    
    Args:
        limit: Number of recent attempts to retrieve
        
    Returns:
        Dictionary with quiz history
    """
    try:
        url = f"{backend_endpoint}api/quiz/history"
        user_id = st.session_state.get("userId")
        params = {"user_id": user_id, "limit": limit}
        response = httpx.get(url, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
