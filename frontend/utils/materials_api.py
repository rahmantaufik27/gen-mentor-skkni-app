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


# Kept comfortably above the backend's own OLLAMA_TIMEOUT (480s, see
# services/llm/ollama_provider.py) so a slow local generation hits THAT
# timeout first and returns its friendlier "took too long, try again"
# message - not this client cutting the connection first with a generic
# httpx error that skips the backend's own handling entirely.
_GENERATE_TIMEOUT = 500


def generate_learning_material(unit_code: str, competency_name: str) -> dict:
    """Generate learning content for a unit from its existing references."""
    try:
        response = httpx.post(
            f"{backend_endpoint}api/materials/generate-learning",
            json={"unit_code": unit_code, "competency_name": competency_name},
            timeout=_GENERATE_TIMEOUT,
        )
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_subtopics(unit_code: str, competency_name: str) -> dict:
    """List one short, generated title per reference group for a unit - the
    fast first step of the "pick a subtopic, then generate just that one"
    flow (see generate_subtopic_material). Returns
    {"success": bool, "subtopics": [{"index", "title"}, ...]}."""
    try:
        response = httpx.post(
            f"{backend_endpoint}api/materials/subtopics",
            json={"unit_code": unit_code, "competency_name": competency_name},
            timeout=_GENERATE_TIMEOUT,
        )
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_subtopic_material(
    unit_code: str, competency_name: str, subtopic_index: int, subtopic_title: str
) -> dict:
    """Generate learning content for ONE subtopic of a unit - called when
    the user clicks that specific subtopic's own button, never
    automatically for every subtopic in a loop."""
    try:
        response = httpx.post(
            f"{backend_endpoint}api/materials/generate-subtopic",
            json={
                "unit_code": unit_code,
                "competency_name": competency_name,
                "subtopic_index": subtopic_index,
                "subtopic_title": subtopic_title,
            },
            timeout=_GENERATE_TIMEOUT,
        )
        return response.json()
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
