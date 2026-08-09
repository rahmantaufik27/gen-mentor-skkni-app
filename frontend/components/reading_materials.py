"""
Reading Materials learning method.

Self-contained module: exposes render_reading_materials() as its only public
entry point, so components/learning_path.py (and any future learning method)
can use it without knowing anything about materials.json, the recommendation
logic, or the inline-viewer mechanics.
"""

import re

import streamlit as st
import streamlit.components.v1 as components

from utils.materials_api import get_all_materials, get_recommended_materials
from utils.practice_api import record_material_view

TYPE_ICONS = {
    "presentation": "📄",
    "pdf": "📄",
    "document": "📄",
    "video": "🎬",
    "article": "📰",
}


def _type_icon(material_type: str) -> str:
    return TYPE_ICONS.get((material_type or "").lower(), "🔗")


def _to_embed_url(url: str) -> str:
    """
    Convert a share URL into an embeddable "preview" URL so the material can
    be viewed inline without downloading it first. Falls back to the original
    URL when no known provider pattern matches (many public pages still embed
    fine as-is).
    """
    if not url:
        return url

    # Google Slides / Docs / Sheets: .../d/<ID>/edit... -> .../d/<ID>/preview
    match = re.search(r"docs\.google\.com/(presentation|document|spreadsheets)/d/([^/]+)", url)
    if match:
        kind, file_id = match.group(1), match.group(2)
        return f"https://docs.google.com/{kind}/d/{file_id}/preview"

    # Google Drive file: .../file/d/<ID>/... -> .../file/d/<ID>/preview
    match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
    if match:
        return f"https://drive.google.com/file/d/{match.group(1)}/preview"

    # YouTube: watch?v=<ID> or youtu.be/<ID> -> /embed/<ID>
    match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)", url)
    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    # Direct PDF / unknown provider: most browsers render these natively in an iframe
    return url


def _render_material_list(materials: list, key_prefix: str, show_status: bool):
    """Render one card per material with a View button that opens the inline viewer."""
    for idx, material in enumerate(materials):
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                icon = _type_icon(material.get("type"))
                st.markdown(f"**{icon} {material.get('title', 'Untitled')}**")

                meta = f"Unit: {material.get('unit_code', '-')} · Type: {str(material.get('type', '-')).title()}"
                if show_status:
                    status = material.get("mastery_status", "Remedial")
                    badge_class = "gm-badge-success" if status == "Mastered" else "gm-badge-danger"
                    st.markdown(
                        f"<span class='gm-badge {badge_class}'>{status}</span> "
                        f"<span style='color: var(--text-muted); font-size: 13px;'>"
                        f"{meta} · Target: {material.get('target_level', '-')}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(meta)
            with col2:
                if st.button("View", key=f"view_{key_prefix}_{idx}", use_container_width=True):
                    st.session_state["selected_material"] = material
                    # Fire-and-forget: count this material open for Learning Path
                    # stats. Never blocks or breaks the viewer if it fails.
                    record_material_view(material.get("unit_code"))
                    st.rerun()


def _render_selected_material_viewer():
    """Render the inline viewer for whatever material is currently selected, if any."""
    material = st.session_state.get("selected_material")
    if not material:
        return

    st.markdown("")
    with st.container(border=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"#### {_type_icon(material.get('type'))} {material.get('title', 'Untitled')}")
        with col2:
            if st.button("✕ Close", key="close_material_viewer", use_container_width=True):
                st.session_state["selected_material"] = None
                st.rerun()

        embed_url = _to_embed_url(material.get("url", ""))
        components.iframe(embed_url, height=600, scrolling=True)
        st.caption(f"Having trouble viewing it here? [Open in a new tab ↗]({material.get('url', '')})")


def render_reading_materials():
    """Render the Reading Materials learning method: recommended + all materials, with an inline viewer."""
    tab_recommended, tab_all = st.tabs(["🎯 Recommended for You", "📚 All Materials"])

    with tab_recommended:
        result = get_recommended_materials()
        if not result.get("success"):
            st.error(f"Failed to load recommended materials: {result.get('error', 'Unknown error')}")
        elif result.get("all_mastered"):
            st.success("🎉 All units are currently Mastered! Check out All Materials to keep learning.")
        else:
            materials = result.get("materials", [])
            if not materials:
                st.info("No recommended materials found for your current gaps yet.")
            else:
                _render_material_list(materials, key_prefix="rec", show_status=True)

    with tab_all:
        result = get_all_materials()
        if not result.get("success"):
            st.error(f"Failed to load materials: {result.get('error', 'Unknown error')}")
        else:
            materials = result.get("materials", [])
            if not materials:
                st.info("No materials available yet.")
            else:
                _render_material_list(materials, key_prefix="all", show_status=False)

    _render_selected_material_viewer()
