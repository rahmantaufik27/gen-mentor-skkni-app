"""
Reading Materials API utilities for frontend integration.

Thin httpx wrappers around the backend's /api/materials/* endpoints, matching
the {"success": bool, ...}-never-raises convention used by utils/quiz_api.py.
"""

import httpx
import streamlit as st
from config import backend_endpoint


def material_source_id(material: dict) -> str:
    """
    Stable id for a material - it has no DB id (materials live in Neo4j as
    Concept nodes, see services/neo4j_service.py), so this is the shared
    convention every feature that needs to reference one specific material
    uses: its url, or "title|unit_code" as a fallback when there's no url.

    Shared by components/reading_materials.py (Notes bookmarking) and
    components/discussion.py (per-material discussion threads) - both need
    the SAME id for the same material so a bookmark and a discussion
    thread for it always agree on which material they mean.
    """
    return material.get("url") or f"{material.get('title', '')}|{material.get('unit_code', '')}"


# Cached at module scope (st.cache_data is shared across every session on
# this server, not per-user - correct here since neither call takes a
# user-specific argument or reads st.session_state; the data really is the
# same for everyone). Found during a 200-concurrent-user scalability audit:
# both were re-fetched from the backend (which re-queries Neo4j) on every
# single page load across every user, for content that's effectively
# static (materials/units only change if someone edits the knowledge
# graph). 5 minutes so a real edit still shows up reasonably soon without
# a server restart, without hammering Neo4j on every render.
_STATIC_DATA_TTL = 300


@st.cache_data(ttl=_STATIC_DATA_TTL)
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


@st.cache_data(ttl=_STATIC_DATA_TTL)
def get_all_units() -> dict:
    """
    Get every unit's code + human-readable title (static, not user-specific).

    Returns:
        Dictionary with a "units" list of {"unit_code", "title"}
    """
    try:
        url = f"{backend_endpoint}api/materials/units"
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
