"""
Notes API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/notes/* endpoints, matching the
{"success": bool, ...}-never-raises convention used by the other api utils.

A note bookmarks one SPECIFIC piece of content from a source
(source_type in {"material", "question", "chat"}), keyed by source_id, with a
snapshot_text copy so it stays understandable and a source_ref for opening the
original.
"""

import httpx
import streamlit as st
from config import backend_endpoint

SOURCE_MATERIAL = "material"
SOURCE_QUESTION = "question"
SOURCE_CHAT = "chat"

_TIMEOUT = 20


def save_note(source_type: str, source_id: str, snapshot_text: str, title: str = None, source_ref: dict = None) -> dict:
    """Save a note for a specific piece of content. Idempotent server-side
    (a duplicate is a no-op success)."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "snapshot_text": snapshot_text,
        }
        if title:
            payload["title"] = title
        if source_ref:
            payload["source_ref"] = source_ref
        response = httpx.post(f"{backend_endpoint}api/notes", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def remove_note(source_type: str = None, source_id: str = None, note_id: str = None) -> dict:
    """Remove a note - by note_id (Notes page) or by (source_type, source_id)
    (the Remove-from-Notes toggle on the content itself)."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {"user_id": user_id}
        if note_id:
            payload["note_id"] = note_id
        if source_type and source_id:
            payload["source_type"] = source_type
            payload["source_id"] = source_id
        response = httpx.request("DELETE", f"{backend_endpoint}api/notes", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_notes(source_type: str = None) -> dict:
    """List the current user's notes, optionally filtered by source_type."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        params = {"user_id": user_id}
        if source_type:
            params["source_type"] = source_type
        response = httpx.get(f"{backend_endpoint}api/notes", params=params, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_saved_source_ids(source_type: str = None) -> set:
    """Return the set of source_ids the user has already saved for source_type
    (or all types). Used to render the Save/Remove toggle in the right state.
    Never raises - returns an empty set on any failure."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return set()
        params = {"user_id": user_id}
        if source_type:
            params["source_type"] = source_type
        response = httpx.get(f"{backend_endpoint}api/notes/keys", params=params, timeout=_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return {k["source_id"] for k in data.get("keys", [])}
        return set()
    except Exception:
        return set()
