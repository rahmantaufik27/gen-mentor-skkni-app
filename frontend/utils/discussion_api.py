"""
Unit Discussion API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/discussions/* endpoints,
matching the {"success": bool, ...}-never-raises convention used by the
other api utils (see utils/free_notes_api.py for the same pattern).
"""

import httpx
import streamlit as st
from config import backend_endpoint

_TIMEOUT = 20


def list_discussion_posts(unit_code: str, material_id: str = None) -> dict:
    """List every post (with nested replies) for one unit's general
    discussion, or - if material_id is given - just that material's
    thread within the unit."""
    try:
        params = {"unit_code": unit_code}
        if material_id:
            params["material_id"] = material_id
        response = httpx.get(f"{backend_endpoint}api/discussions", params=params, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_discussion_post(
    unit_code: str, body: str, parent_post_id: str = None,
    material_id: str = None, material_title: str = None,
) -> dict:
    """Create a top-level post, or a reply when parent_post_id is given -
    in the unit's general discussion, or scoped to one material when
    material_id/material_title are given."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        payload = {"user_id": user_id, "unit_code": unit_code, "body": body}
        if parent_post_id:
            payload["parent_post_id"] = parent_post_id
        if material_id:
            payload["material_id"] = material_id
            payload["material_title"] = material_title
        response = httpx.post(f"{backend_endpoint}api/discussions", json=payload, timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_discussion_counts() -> dict:
    """Post count per unit_code, across every unit - for the unit picker."""
    try:
        response = httpx.get(f"{backend_endpoint}api/discussions/counts", timeout=_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_material_discussion_counts(unit_code: str) -> dict:
    """Post count per material_id within one unit - for the material picker
    inside the Discussion page and Reading Materials' "Discuss" links."""
    try:
        response = httpx.get(
            f"{backend_endpoint}api/discussions/material-counts",
            params={"unit_code": unit_code}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def set_best_answer(reply_id: str, is_best: bool = True) -> dict:
    """Mark (is_best=True) or unmark (is_best=False) a reply as the best
    answer to its parent post. Only the parent post's own author may do
    this - the backend enforces that and returns an error otherwise."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.put(
            f"{backend_endpoint}api/discussions/best-answer",
            json={"user_id": user_id, "reply_id": reply_id, "is_best": is_best}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        try:
            return response.json()
        except Exception:
            return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_discussion_post(post_id: str) -> dict:
    """Delete a post (and its replies) - only the post's own author can delete it."""
    try:
        user_id = st.session_state.get("userId")
        if not user_id:
            return {"success": False, "error": "User not authenticated"}
        response = httpx.request(
            "DELETE", f"{backend_endpoint}api/discussions",
            json={"user_id": user_id, "post_id": post_id}, timeout=_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json()
        return {"success": False, "error": f"Status code: {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
