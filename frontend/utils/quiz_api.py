"""
Quiz API utilities for frontend integration.
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
