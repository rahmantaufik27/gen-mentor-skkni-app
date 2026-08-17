"""
Free Notes API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/free-notes/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by the other api utils.

A free note is pure user-authored rich text (no source reference) tagged with
a category so it renders on the right tab: CATEGORY_QUESTION (Cue Questions ->
Free Question) or CATEGORY_KEY_POINTS (Key Points -> Free Notes).
"""

import httpx
import streamlit as st
from config import backend_endpoint

CATEGORY_QUESTION = "question"
CATEGORY_KEY_POINTS = "key_points"

_TIMEOUT = 20


def list_free_notes(category: str) -> dict:
    """List the current user's free notes for one category."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.get(
            f"{backend_endpoint}api/free-notes",
            params={"user_id": user_id, "category": category}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_free_note(category: str, content_html: str) -> dict:
    """Create a new free note in the given category."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {"user_id": user_id, "category": category, "content_html": content_html}
        response = httpx.post(f"{backend_endpoint}api/free-notes", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update_free_note(note_id: str, content_html: str) -> dict:
    """Update an existing free note's content."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {"user_id": user_id, "note_id": note_id, "content_html": content_html}
        response = httpx.put(f"{backend_endpoint}api/free-notes", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_free_note(note_id: str) -> dict:
    """Delete a free note."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.request(
            "DELETE", f"{backend_endpoint}api/free-notes",
            json={"user_id": user_id, "note_id": note_id}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
